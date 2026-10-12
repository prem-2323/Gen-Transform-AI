import json
import re
from typing import Any, Dict, List, Optional, Union

from text.qwen_service import QwenServiceError, generate_with_qwen


PROMPT_ENGINE_INSTRUCTIONS = """
You are an expert visual prompt engineer. Turn the supplied content into a concise
JSON array of cinematic image prompts. Return only JSON in this shape:
{"scenes":[{"scene":1,"prompt":"..."}]}
Create one scene for each storyboard scene when a storyboard is supplied, otherwise
create three distinct scenes. Each prompt must describe subject, setting, action,
composition, lighting, mood, and realistic visual style. Do not include readable text,
logos, watermarks, or camera metadata in the prompt.

CONTENT:
"""

# ── Image Prompt Enhancement Agent ──────────────────────────────────────
# Converts long / instructional source text into a single image-model-ready
# visual prompt. Uses existing Qwen/Ollama infrastructure; deterministic
# fallback preserves subject without inventing facts.

ENHANCE_INSTRUCTIONS = """You are an expert AI Visual Prompt Engineer for Stable Diffusion.
Convert the USER REQUEST below into ONE visually concrete, evocative scene prompt.

Core Rules:
- Describe a concrete, physical, photorealistic scene (foreground subject in action, physical environment, camera framing, lighting, high detail).
- If the request mentions abstract concepts like "Artificial intelligence", "data processing", "analytics", depict scientists or tech specialists working with luminous holographic neural network interfaces, glowing data streams, and high-tech lab equipment.
- NEVER describe empty conference rooms, vacant boardroom tables, plain office chairs, or blank sheets of paper.
- Remove all procedural/instructional phrases like "analyze the document", "extract key facts", "create a LinkedIn post", "summarize findings".
- Apply the STYLE CONSTRAINT as the visual rendering approach.
- Return ONLY the enhanced prompt as plain text (no JSON, no quotes, no conversational explanation). Max 100 words.

STYLE CONSTRAINT: {style_constraint}
ASPECT / USE: {aspect_hint}
USER REQUEST:
"""

STYLE_CONSTRAINTS = {
    "photorealistic 8k": "highly detailed photograph, 8k resolution, cinematic lighting, photorealistic, shot on 35mm lens",
    "cinematic 35mm": "cinematic still, 35mm film photography, anamorphic lens flare, moody color grading, masterpiece",
    "3d isometric": "3d isometric render, blender cycles, clean geometric forms, soft studio lighting, high poly count",
    "cyberpunk neon": "cyberpunk aesthetic, volumetric neon fog, glowing holographic UI, moody dark rainy atmosphere",
    "minimalist vector": "clean vector illustration, flat design, modern UI graphic style, bold palettes",
    "editorial magazine": "luxury editorial photography, studio lighting, award-winning composition",
    "digital oil": "digital oil painting, expressive brushwork, fine art texture, dramatic chiaroscuro",
    "anime concept": "anime concept keyframe, atmospheric lighting, vivid sky, detailed background art",
}

DEFAULT_STYLE_CONSTRAINT = "photorealistic, dynamic lighting, sharp focus, 8k, masterpiece"

# Phrases that indicate procedural / transformation instructions, not visual content.
_PROCEDURAL_PATTERNS = [
    r"\bgenerate\b.*\b(linkedin|twitter|x|post|summary|presentation|video|advisory|infographic|script)\b",
    r"\bcreate\b.*\b(post|summary|deck|slides|thread|campaign|outline|report)\b",
    r"\btransform\b.*\b(document|content|source|information)\b",
    r"\banalyze\b.*\b(document|content|text|data|report|following)\b",
    r"\bextract\b.*\b(key\s+facts|objectives|findings|insights)\b",
    r"\bsummarize\b.*\b(findings|information|points)\b",
    r"\bensure\b.*\b(outputs|factual\s+accuracy|original\s+meaning|consistency)\b",
    r"\borganize\b.*\b(information|clearly|tone)\b",
    r"\bstep\s*\d+\b",
    r"\bdeliverable\b",
    r"\bclick\b.*\bgenerate\b",
    r"\bctrl\s*\+\s*enter\b",
]


def _style_constraint(style: Optional[str]) -> str:
    if not style:
        return DEFAULT_STYLE_CONSTRAINT
    key = style.strip().lower()
    for name, constraint in STYLE_CONSTRAINTS.items():
        if name in key or key in name:
            return constraint
    # Unknown label: treat the raw style text as the constraint (truncated).
    return style.strip()[:200] if style.strip() else DEFAULT_STYLE_CONSTRAINT


def _strip_procedural(text: str) -> str:
    """Remove procedural instruction sentences, keep descriptive content."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(re.search(pat, lowered) for pat in _PROCEDURAL_PATTERNS):
            continue
        if len(sentence.strip()) < 3:
            continue
        kept.append(sentence.strip())
    return " ".join(kept).strip()


def _extract_subject(text: str) -> str:
    """Conservative subject: first descriptive sentence, truncated."""
    cleaned = _strip_procedural(text) or text.strip()[:500]
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    subject = sentences[0].strip() if sentences else cleaned[:200]
    # Drop leading imperatives like "Describe...", "Explain...".
    subject = re.sub(r"^(please\s+)?(describe|explain|summarize|generate|create|write|show)\b[:\s]*", "", subject, flags=re.IGNORECASE)
    return subject[:220].rstrip(" .,;:") or "abstract concept visualization"


def _output_budget(name: str, fallback: int) -> int:
    try:
        import sys
        from pathlib import Path as _P

        _b = _P(__file__).resolve().parent.parent
        if str(_b) not in sys.path:
            sys.path.insert(0, str(_b))
        from app.core.token_budgets import resolve_output_budget

        return int(resolve_output_budget(name, None))
    except Exception:
        return int(fallback)


def _budgeted_source(text: str, max_tokens: int = 3000) -> str:
    try:
        import sys
        from pathlib import Path as _P

        _b = _P(__file__).resolve().parent.parent
        if str(_b) not in sys.path:
            sys.path.insert(0, str(_b))
        from app.core.token_budgets import truncate_to_token_budget

        out, _ = truncate_to_token_budget(text or "", max_tokens, model="qwen", stage="image_prompt")
        return out
    except Exception:
        return (text or "")[:12000]


def _qwen_enhance(prompt: str) -> Optional[str]:
    """Try available Ollama models in order; return None if all unavailable."""
    import os
    preferred = os.getenv("TEXT_MODEL") or "qwen2.5:3b"
    models = [preferred]
    for fallback in ("qwen2.5:3b", "gemma2:2b"):
        if fallback not in models:
            models.append(fallback)
    for model in models:
        try:
            return generate_with_qwen(
                prompt,
                model=model,
                num_predict=_output_budget("image_prompt", 300),
                timeout=30.0,
                temperature=0.4,
            )
        except QwenServiceError:
            continue
    return None


def _deterministic_enhance(text: str, style: Optional[str], aspect_ratio: Optional[str]) -> Dict[str, str]:
    subject = _extract_subject(text)
    constraint = _style_constraint(style)
    aspect_hint = f" Optimized for {aspect_ratio} composition." if aspect_ratio else ""
    # Map common tech concepts to rich visual subjects
    subj_lower = subject.lower()
    if "intelligence" in subj_lower or "ai" in subj_lower or "transform" in subj_lower:
        rich_subject = "artificial intelligence neural networks visualizing luminous data streams in modern research laboratory"
    elif "data" in subj_lower or "analytics" in subj_lower or "analysis" in subj_lower:
        rich_subject = "high-tech holographic data visualization matrix with glowing metrics and analytics"
    else:
        rich_subject = subject

    enhanced = (
        f"Cinematic photorealistic shot of {rich_subject}. "
        f"Dynamic focal composition, volumetric lighting, rich color palette, sharp focus, 8k resolution, "
        f"{constraint}, masterpiece.{aspect_hint} no text, no watermark, no empty room."
    )
    return {"enhanced_prompt": enhanced[:1500], "subject": subject, "llm_used": False}


def enhance_image_prompt(
    text: str,
    style: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
) -> Dict[str, Any]:
    """Enhance a long / instructional request into an image-ready visual prompt.

    Returns dict with enhanced_prompt, negative_prompt, subject, llm_used.
    Never raises for LLM outage — falls back to deterministic enhancement.
    """
    source = (text or "").strip()
    if not source:
        raise QwenServiceError("No text provided for prompt enhancement.")
    source = _budgeted_source(source)
    constraint = _style_constraint(style)
    aspect_hint = aspect_ratio or "general use"

    llm_text = _qwen_enhance(ENHANCE_INSTRUCTIONS.format(style_constraint=constraint, aspect_hint=aspect_hint) + source)
    if llm_text:
        cleaned = llm_text.strip().strip('"').strip()
        # Guard: LLM must describe a scene, not echo instructions.
        if len(cleaned) >= 20 and "generate a linkedin" not in cleaned.lower():
            return {
                "enhanced_prompt": cleaned[:1500],
                "negative_prompt": (negative_prompt or "").strip() or None,
                "subject": _extract_subject(source),
                "llm_used": True,
            }
    fallback = _deterministic_enhance(source, style, aspect_ratio)
    if negative_prompt and negative_prompt.strip():
        fallback["negative_prompt"] = negative_prompt.strip()
    else:
        fallback["negative_prompt"] = None
    return fallback


def _parse_json(candidate: str) -> Dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", candidate or "", flags=re.IGNORECASE | re.DOTALL).strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise QwenServiceError("Qwen returned an invalid image-scene response.")
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise QwenServiceError("Qwen returned an invalid image-scene response.") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("scenes"), list):
        raise QwenServiceError("Qwen returned no image scenes.")
    return payload


def _split_text_scenes(text: str, max_scenes: int = 6) -> List[Dict[str, Any]]:
    """Deterministically split a script into ordered scene prompts.

    Never returns the entire script as a single prompt when it clearly
    contains multiple scenes / sentences — splits on scene markers first,
    then sentences, capped at max_scenes.
    """
    cleaned = text.strip()
    # Split on explicit scene markers.
    parts = re.split(r"(?:^|\n)\s*(?:scene\s*\d+[:.\-]\s*|#{1,3}\s+|\d+\.\s+)", cleaned, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        if len(sentences) > 1:
            # Group sentences into up to max_scenes chunks.
            chunk_size = max(1, (len(sentences) + max_scenes - 1) // max_scenes)
            parts = [" ".join(sentences[i:i + chunk_size]) for i in range(0, len(sentences), chunk_size)]
        else:
            parts = [cleaned] if cleaned else []
    scenes = []
    for index, part in enumerate(parts[:max_scenes], 1):
        # Skip purely procedural parts (e.g. "Generate a LinkedIn post...").
        descriptive = _strip_procedural(part)
        if not descriptive:
            continue
        subject = _extract_subject(part)
        scenes.append({
            "scene": len(scenes) + 1,
            "prompt": f"Cinematic scene {len(scenes) + 1}: {subject}, detailed environment, expressive composition, professional lighting, high-quality digital illustration, no text, no watermark.",
        })
    return scenes or [{"scene": 1, "prompt": _extract_subject(cleaned)[:500]}]


def _fallback_scenes(script: Union[Dict[str, Any], str]) -> List[Dict[str, Any]]:
    if isinstance(script, dict):
        storyboard = script.get("storyboard", [])
        if isinstance(storyboard, list) and storyboard:
            scenes = [
                {"scene": item.get("scene", index), "prompt": item.get("visuals", "")}
                for index, item in enumerate(storyboard, 1)
                if isinstance(item, dict) and item.get("visuals")
            ]
            if scenes:
                return scenes
        # Dict without storyboard: use any text fields as separate scenes.
        text_bits = [str(v) for v in script.values() if isinstance(v, str) and len(v.strip()) > 20]
        if text_bits:
            return _split_text_scenes(" ".join(text_bits))
    return _split_text_scenes(str(script))


def _qwen_scenes(source: str) -> Optional[List[Dict[str, Any]]]:
    for model in ("qwen3:4b", "qwen2.5:3b", "gemma2:2b"):
        try:
            response = generate_with_qwen(
                PROMPT_ENGINE_INSTRUCTIONS + _budgeted_source(source),
                model=model,
                deliverable="image_prompt",
            )
            scenes = _parse_json(response).get("scenes", [])
            valid = [
                {"scene": item.get("scene", index), "prompt": str(item.get("prompt", "")).strip()}
                for index, item in enumerate(scenes, 1)
                if isinstance(item, dict) and str(item.get("prompt", "")).strip()
            ]
            if valid:
                return valid
        except Exception:
            continue
    return None


def generate_scene_prompts(script: Union[Dict[str, Any], str]) -> List[Dict[str, Any]]:
    try:
        source = json.dumps(script, ensure_ascii=True) if isinstance(script, dict) else script
        scenes = _qwen_scenes(source)
        if scenes:
            return scenes
    except Exception as err:
        print(f"[Prompt Engine Fallback] Qwen prompt engineering offline/failed ({err}). Using fallback storyboard scenes.")

    return _fallback_scenes(script)
