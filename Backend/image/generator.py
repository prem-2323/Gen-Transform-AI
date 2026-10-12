import base64
import os
import threading
import time
from io import BytesIO
from typing import Tuple

import requests

# Try importing torch if available in environment
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

IMAGE_MODEL_URL_DEFAULT = "http://127.0.0.1:7860"


def get_forge_base_url() -> str:
    """Resolve Forge base URL at request time (env-overridable).

    Supports IMAGE_MODEL_URL and FORGE_URL. Strips trailing slashes.
    Defaults to local Forge at http://127.0.0.1:7860 (same host deployment).
    When the backend runs in Docker / on another server, set IMAGE_MODEL_URL
    to the host-visible address (e.g. http://host.docker.internal:7860).
    """
    return (
        os.getenv("IMAGE_MODEL_URL")
        or os.getenv("FORGE_URL")
        or IMAGE_MODEL_URL_DEFAULT
    ).rstrip("/")


# Back-compat module constant (resolved once at import; prefer get_forge_base_url()).
IMAGE_MODEL_URL = os.getenv("IMAGE_MODEL_URL", IMAGE_MODEL_URL_DEFAULT)
IMAGE_MODEL_TIMEOUT_SECONDS = int(os.getenv("IMAGE_MODEL_TIMEOUT_SECONDS", "180"))

# Default constants for pipeline backwards compatibility
DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
DEFAULT_STEPS = 20
DEFAULT_CFG_SCALE = 7
DEFAULT_SAMPLER = "Euler a"
DEFAULT_NEGATIVE_PROMPT = (
    "blurry, low quality, low resolution, distorted, deformed, bad anatomy, "
    "malformed hands, extra fingers, extra limbs, duplicate people, unnatural faces, "
    "distorted faces, cartoon, anime, illustration, watermark, logo, text, letters, "
    "empty room, empty office, vacant boardroom, conference table, empty chairs, blank screen, "
    "oversaturated, unrealistic, poor composition, cropped subjects"
)

# Default mode configurations for rapid preview and high quality output
MODE_CONFIGS = {
    "fast": {"width": 512, "height": 512, "steps": 18},
    "balanced": {"width": 512, "height": 512, "steps": 22},
    "quality": {"width": 768, "height": 768, "steps": 28},
}


class ImageGenerationError(Exception):
    """Raised when the image model cannot generate an image."""


# Thread-local flag recording whether the most recent generation on this
# thread fell back to the synthetic placeholder (Forge offline). FastAPI runs
# sync routes in a threadpool, so thread-local storage keeps concurrent
# requests from misattributing each other's fallback status.
_generation_state = threading.local()


def is_last_synthetic() -> bool:
    """True if the last image generated on this thread was a placeholder."""
    return bool(getattr(_generation_state, "synthetic", False))


class ImagePipelineSingleton:
    """
    Singleton Image Generation Pipeline.
    Delegates diffusion inference to Stable Diffusion Forge WebUI
    (SDAPI /sdapi/v1/txt2img). No local diffusion weights are loaded here;
    device reporting reflects verified local CUDA capability, never a
    claim about remote Forge GPU unless Forge confirms it.
    """
    _instance = None
    _device = "cpu"
    _gpu_name = ""
    _torch_dtype = None
    _http_session = None
    # Limit concurrent Forge inference requests so the GPU backend is not overloaded.
    _forge_semaphore = threading.Semaphore(2)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Device detection reflects LOCAL torch capability only. Remote Forge
        # GPU status cannot be inferred from here; per-request device strings
        # are labeled accordingly (see _execute_request).
        if TORCH_AVAILABLE and torch.cuda.is_available():
            self._device = "cuda"
            try:
                self._gpu_name = torch.cuda.get_device_name(0)
            except Exception:
                self._gpu_name = "CUDA device"
            self._torch_dtype = torch.float16
            print(f"[Image Studio Pipeline] Local device: CUDA | GPU: {self._gpu_name} | Precision: FP16 | Forge: {get_forge_base_url()}")
        else:
            self._device = "cpu"
            self._gpu_name = "CPU"
            print(f"[Image Studio Pipeline] Local device: CPU | Forge backend: {get_forge_base_url()} (txt2img API)")

        # 2. Persist HTTP session for connection pooling
        self._http_session = requests.Session()

    @property
    def device(self) -> str:
        return self._device

    def generate(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        steps: int = DEFAULT_STEPS,
        mode: str = "fast",
        cfg_scale: int = DEFAULT_CFG_SCALE,
        allow_placeholder: bool = True,
        **kwargs,
    ) -> Tuple[bytes, float, str]:
        """
        Execute image generation with exact performance measurement.
        Returns: (image_bytes, generation_time_in_seconds, device_name)

        When Forge is unreachable and allow_placeholder is True, a clearly
        labeled synthetic preview is returned with _generation_state.synthetic=True.
        When allow_placeholder is False, ImageGenerationError is raised instead
        so callers can surface a real unavailable state.
        """
        # Use caller-supplied width, height, and steps directly
        steps = max(1, min(50, int(steps)))
        width = max(256, min(1536, int(width)))
        height = max(256, min(1536, int(height)))

        _generation_state.synthetic = False
        start_time = time.perf_counter()

        # Execute using PyTorch inference mode if torch is present
        if TORCH_AVAILABLE and torch is not None:
            with torch.inference_mode():
                image_bytes = self._execute_request(
                    prompt, negative_prompt, width, height, steps,
                    allow_placeholder=allow_placeholder,
                )
        else:
            image_bytes = self._execute_request(
                prompt, negative_prompt, width, height, steps,
                allow_placeholder=allow_placeholder,
            )

        generation_time = round(time.perf_counter() - start_time, 2)
        # Device string reflects verified local capability only for real
        # diffusion; placeholders always report preview-cpu (never GPU).
        if is_last_synthetic():
            return image_bytes, generation_time, "cpu-preview"
        return image_bytes, generation_time, self._device

    def _execute_request(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        allow_placeholder: bool = True,
    ) -> bytes:
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": DEFAULT_CFG_SCALE,
            "sampler_name": DEFAULT_SAMPLER,
            "scheduler": "karras",
            "batch_size": 1,
        }
        base_url = get_forge_base_url()
        timeout_secs = int(os.getenv("IMAGE_MODEL_TIMEOUT_SECONDS", str(IMAGE_MODEL_TIMEOUT_SECONDS)))
        # Serialize Forge inference to avoid overloading the GPU backend.
        acquired = self._forge_semaphore.acquire(blocking=False)
        if not acquired:
            raise ImageGenerationError(
                "An image generation is already in progress. Please wait for it to finish and try again."
            )
        try:
            try:
                response = self._http_session.post(
                    f"{base_url}/sdapi/v1/txt2img",
                    json=payload,
                    timeout=(3.0, timeout_secs),
                )
                response.raise_for_status()
                try:
                    data = response.json()
                except Exception as error:
                    raise ImageGenerationError(
                        "The image service returned an invalid response."
                    ) from error
                images = data.get("images", []) if isinstance(data, dict) else []
                if not images:
                    raise ImageGenerationError("The image model returned no image data.")
                encoded_image = images[0].split(",", 1)[-1]
                try:
                    decoded = base64.b64decode(encoded_image)
                except Exception as error:
                    raise ImageGenerationError(
                        "The image service returned undecodable image data."
                    ) from error
                if len(decoded) < 1024:
                    raise ImageGenerationError(
                        "The image service returned an unexpectedly small image."
                    )
                _generation_state.synthetic = False
                return decoded
            except ImageGenerationError:
                raise
            except requests.exceptions.ConnectTimeout as error:
                raise ImageGenerationError(
                    f"Could not connect to the image service at {base_url} (connection timed out). "
                    "Start SD Forge with --api --port 7860, then retry."
                ) from error
            except requests.exceptions.ConnectionError as error:
                raise ImageGenerationError(
                    f"Could not reach the image service at {base_url}. "
                    "Start SD Forge with --api --port 7860, then retry."
                ) from error
            except requests.exceptions.ReadTimeout as error:
                raise ImageGenerationError(
                    "Image generation timed out. Try fewer steps or a smaller resolution."
                ) from error
            except requests.exceptions.HTTPError as error:
                status = getattr(error.response, "status_code", "?")
                detail = ""
                try:
                    body = error.response.json() if error.response is not None else None
                    if isinstance(body, dict):
                        # Forge returns {"errors": "...", "detail": ..., "error": ...}
                        detail = str(body.get("errors") or body.get("detail") or body.get("error") or body)[:500]
                    elif error.response is not None:
                        detail = (error.response.text or "")[:500]
                except Exception:
                    detail = ""
                if "do not have any model" in detail.lower():
                    raise ImageGenerationError(
                        "Forge has no checkpoint loaded. Download at least one .safetensors model into "
                        "Forge/models/Stable-diffusion, refresh Forge (blue ↻ icon) and select it, then retry."
                    ) from error
                if detail:
                    raise ImageGenerationError(
                        f"The image service returned HTTP {status}: {detail}"
                    ) from error
                raise ImageGenerationError(
                    f"The image service returned HTTP {status}. Check Forge logs for details."
                ) from error
            except Exception as error:
                # Unknown failure during the Forge call itself.
                raise ImageGenerationError(
                    f"Image generation failed: {error}"
                ) from error
        except ImageGenerationError as error:
            if not allow_placeholder:
                raise
            print(f"[Image Studio Pipeline Fallback] Forge unavailable ({error}). Generating labeled preview.")
            _generation_state.synthetic = True
            try:
                from PIL import Image, ImageDraw
                img = Image.new("RGB", (width, height), color=(15, 23, 42))
                draw = ImageDraw.Draw(img)

                # Decorative grid
                grid_step = 64
                for x in range(0, width, grid_step):
                    draw.line([(x, 0), (x, height)], fill=(30, 41, 59), width=1)
                for y in range(0, height, grid_step):
                    draw.line([(0, y), (width, y)], fill=(30, 41, 59), width=1)

                # Amber accent border marks this as a UI preview, not diffusion output.
                draw.rectangle([(16, 16), (width - 16, height - 16)], outline=(245, 158, 11), width=3)
                draw.rectangle([(24, 24), (width - 24, height - 24)], outline=(51, 65, 85), width=1)

                # Center Card
                card_w, card_h = min(width - 80, 520), 160
                cx, cy = width // 2, height // 2
                draw.rectangle([(cx - card_w//2, cy - card_h//2), (cx + card_w//2, cy + card_h//2)], fill=(24, 24, 27), outline=(245, 158, 11), width=2)

                # Explicit preview labels — never claim AI generation.
                draw.text((cx - card_w//2 + 24, cy - 48), "UI PREVIEW - NOT AI-GENERATED", fill=(245, 158, 11))
                clean_p = (prompt[:55] + "...") if len(prompt) > 55 else prompt
                draw.text((cx - card_w//2 + 24, cy - 12), f'"{clean_p}"', fill=(241, 245, 249))
                draw.text((cx - card_w//2 + 24, cy + 24), f"Preview: {width}x{height} | CPU preview renderer", fill=(148, 163, 184))

                buf = BytesIO()
                img.save(buf, format="PNG", optimize=True)
                return buf.getvalue()
            except Exception:
                raise ImageGenerationError("The image model is unavailable.") from error
        finally:
            self._forge_semaphore.release()


def generate_image_bytes(
    prompt: str,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    steps: int = DEFAULT_STEPS,
    mode: str = "fast",
    cfg_scale: int = DEFAULT_CFG_SCALE,
    **kwargs,
) -> Tuple[bytes, float, str]:
    """Module function delegating to singleton pipeline."""
    pipeline = ImagePipelineSingleton.get_instance()
    return pipeline.generate(prompt, negative_prompt, width, height, steps, mode, cfg_scale=cfg_scale, **kwargs)
