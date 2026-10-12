"""Phase 7 QLoRA Student Inference Service.

Loads Qwen/Qwen2.5-0.5B-Instruct base model and PEFT adapter from
Backend/outputs/distillation/student with CUDA/CPU support and singleton model reuse.
"""
from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import torch

log = logging.getLogger("gen-transform.services.student_service")

DEFAULT_BASE_MODEL = os.getenv("STUDENT_MODEL_BASE", "Qwen/Qwen2.5-0.5B-Instruct")
DEFAULT_ADAPTER_PATH = os.getenv(
    "STUDENT_ADAPTER_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "outputs" / "distillation" / "student")
)
DEFAULT_DEVICE_SETTING = os.getenv("STUDENT_DEVICE", "auto")


def _central_default_max_tokens() -> int:
    try:
        import sys as _sys

        _backend = Path(__file__).resolve().parent.parent.parent.parent
        if str(_backend) not in _sys.path:
            _sys.path.insert(0, str(_backend))
        from app.core.token_budgets import get_token_budget_config

        return int(get_token_budget_config().student_max_new_tokens)
    except Exception:
        try:
            return int(os.getenv("STUDENT_MAX_NEW_TOKENS", "2048"))
        except (TypeError, ValueError):
            return 2048


DEFAULT_MAX_NEW_TOKENS = _central_default_max_tokens()
DEFAULT_TEMPERATURE = float(os.getenv("STUDENT_TEMPERATURE", "0.1"))
DEFAULT_TOP_P = float(os.getenv("STUDENT_TOP_P", "0.9"))


class StudentInferenceService:
    """Singleton service for QLoRA Student Model inference."""

    def __init__(
        self,
        base_model_name: str = DEFAULT_BASE_MODEL,
        adapter_path: str = DEFAULT_ADAPTER_PATH,
        device_setting: str = DEFAULT_DEVICE_SETTING,
    ) -> None:
        self.base_model_name = base_model_name
        self.adapter_path = adapter_path
        self.device_setting = device_setting.lower()

        self._tokenizer = None
        self._model = None
        self._device_str = "cpu"
        self._is_loaded = False

    def load_model(self) -> None:
        """Lazy load base model and PEFT adapter into memory."""
        if self._is_loaded and self._model is not None:
            return

        t_start = time.time()
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel

        # 1. Determine target device
        cuda_avail = torch.cuda.is_available()
        if self.device_setting == "cuda" or (self.device_setting == "auto" and cuda_avail):
            self._device_str = "cuda"
            dtype = torch.float16
        else:
            self._device_str = "cpu"
            dtype = torch.float32

        log.info("Loading QLoRA student: base='%s', adapter='%s' on device='%s'", self.base_model_name, self.adapter_path, self._device_str)

        # 2. Load tokenizer
        if os.path.exists(self.adapter_path):
            self._tokenizer = AutoTokenizer.from_pretrained(self.adapter_path, trust_remote_code=True)
        else:
            self._tokenizer = AutoTokenizer.from_pretrained(self.base_model_name, trust_remote_code=True)

        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        # 3. Load base model
        base_model = AutoModelForCausalLM.from_pretrained(
            self.base_model_name,
            torch_dtype=dtype,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )

        # 4. Load PEFT adapter if path exists
        adapter_abs = Path(self.adapter_path).resolve()
        if adapter_abs.exists():
            self._model = PeftModel.from_pretrained(base_model, str(adapter_abs))
            log.info("Loaded PEFT adapter from %s", adapter_abs)
        else:
            log.warning("Adapter path '%s' not found; using un-adapted base model.", self.adapter_path)
            self._model = base_model

        # 5. Move to target device & set to evaluation mode
        self._model.to(self._device_str)
        self._model.eval()
        self._is_loaded = True

        load_time = round((time.time() - t_start) * 1000, 2)
        log.info("QLoRA student model loaded successfully in %sms on %s", load_time, self._device_str)

    def generate_grounded_answer(
        self,
        prompt: str,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generate grounded answer using fine-tuned student model."""
        self.load_model()
        t_start = time.time()

        max_tokens = max_new_tokens or DEFAULT_MAX_NEW_TOKENS
        try:
            max_tokens = max(16, int(max_tokens))
        except (TypeError, ValueError):
            max_tokens = int(DEFAULT_MAX_NEW_TOKENS)
        temp = temperature if temperature is not None else DEFAULT_TEMPERATURE
        top_p_val = top_p if top_p is not None else DEFAULT_TOP_P
        try:
            from ...core.token_budgets import estimate_tokens as _est

            _in_est = int(_est(prompt or ""))
        except Exception:
            _in_est = len(prompt or "") // 4
        log.info(
            "student_generate model=%s prompt_tokens~%d max_new_tokens=%d temp=%s",
            self.base_model_name,
            _in_est,
            max_tokens,
            temp,
        )

        # Format chat template or raw prompt
        messages = [
            {"role": "system", "content": "You are a grounded document question-answering assistant. Use only supplied evidence."},
            {"role": "user", "content": prompt},
        ]
        try:
            formatted_prompt = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:
            formatted_prompt = f"System: You are a grounded QA assistant.\nUser: {prompt}\nAnswer:"

        inputs = self._tokenizer(formatted_prompt, return_tensors="pt").to(self._device_str)
        input_len = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temp if temp > 0.0 else 0.01,
                do_sample=temp > 0.0,
                top_p=top_p_val,
                pad_token_id=self._tokenizer.pad_token_id,
                eos_token_id=self._tokenizer.eos_token_id,
            )

        generated_tokens = outputs[0][input_len:]
        answer_text = self._tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

        latency_ms = round((time.time() - t_start) * 1000, 2)

        return {
            "text": answer_text,
            "latency_ms": latency_ms,
            "device": self._device_str,
            "base_model": self.base_model_name,
            "adapter_path": self.adapter_path,
            "tokens_generated": len(generated_tokens),
        }

    def get_status(self) -> Dict[str, Any]:
        """Return operational status of student model service."""
        adapter_exists = Path(self.adapter_path).resolve().exists()
        cuda_avail = torch.cuda.is_available()
        return {
            "available": True,
            "base_model": self.base_model_name,
            "adapter": self.adapter_path,
            "adapter_exists": adapter_exists,
            "adapter_loaded": self._is_loaded,
            "device": self._device_str,
            "cuda_available": cuda_avail,
        }


_STUDENT_SERVICE_INSTANCE: Optional[StudentInferenceService] = None


def get_student_service() -> StudentInferenceService:
    """Return singleton instance of StudentInferenceService."""
    global _STUDENT_SERVICE_INSTANCE
    if _STUDENT_SERVICE_INSTANCE is None:
        _STUDENT_SERVICE_INSTANCE = StudentInferenceService()
    return _STUDENT_SERVICE_INSTANCE


def reset_student_service() -> None:
    """Reset singleton instance for testing."""
    global _STUDENT_SERVICE_INSTANCE
    _STUDENT_SERVICE_INSTANCE = None


__all__ = [
    "StudentInferenceService",
    "get_student_service",
    "reset_student_service",
]
