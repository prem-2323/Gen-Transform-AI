"""
video/scene_generator.py
~~~~~~~~~~~~~~~~~~~~~~~~
Uses Qwen3 (via Ollama) to convert source text into a structured JSON
video scene plan.

Key improvements over v1:
  - Ultra-strict prompt: no explanations, no markdown, JSON only.
  - Robust JSON extraction: strips <think> tags, fences, leading text.
  - Full scene validation with clear error messages.
"""

import json
import re

import requests

from text.qwen_service import QwenServiceError


# ── Ollama config (mirrors qwen_service.py but with higher token limit) ────────

OLLAMA_URL            = "http://localhost:11434/api/generate"
MODEL_NAME            = "qwen3:4b"
REQUEST_TIMEOUT_SECS  = 240   # scenes need more tokens than a regular transform
DEFAULT_SCENE_COUNT   = 6


# ── Ultra-strict prompt ────────────────────────────────────────────────────────

VIDEO_SCENE_SYSTEM_PROMPT = """\
You are a STRICT source-grounded AI video storyboard generator.

Your primary responsibility is CONTENT FAITHFULNESS.

The generated video MUST represent the user's source content.
Do NOT invent unrelated topics, technologies, products, companies,
people, locations, or concepts.

CORE RULES:

1. Read and understand the complete source content first.

2. Extract the important factual concepts from the source.

3. Create scenes ONLY from those extracted concepts.

4. Every scene MUST contain at least one source_fact.

5. The visual_prompt MUST visually represent the source_fact.

6. The narration MUST explain the same source_fact.

7. The on_screen_text MUST describe the actual subject of the scene.

8. NEVER introduce an unrelated concept simply because it looks
   visually interesting or futuristic.

9. Do not hallucinate AI, servers, data centers, autonomous agents,
   enterprise systems, robots, or other technology unless they are
   explicitly supported by the source.

10. Preserve the meaning of the original source.

11. Cover all major concepts from the source across the scenes.

12. Maintain logical progression:
    introduction -> key concepts -> Impact or real-world example -> conclusion.

13. Create exactly {scene_count} scenes covering the source concepts.

13. If the source contains 3 major concepts, prefer creating scenes
    around those 3 concepts instead of inventing additional concepts.

14. The source content has higher priority than visual creativity.

SOURCE CONTENT:
{source_text}

TARGET DURATION:
{target_duration}

PACING:
{pacing}

Return ONLY valid JSON matching this schema:
{{
  "title": "Video title here",
  "scenes": [
    {{
      "scene_number": 1,
      "source_fact": "Exact factual concept from source text",
      "duration": 5,
      "narration": "Narration text here explaining the source fact.",
      "visual_prompt": "Cinematic detailed visual description representing the source fact, photorealistic, 8k.",
      "on_screen_text": "Short punchy headline"
    }}
  ]
}}
"""

SCENE_PROMPT_TEMPLATE = VIDEO_SCENE_SYSTEM_PROMPT

# Required keys that every scene dict must contain
REQUIRED_SCENE_FIELDS = [
    "scene_number",
    "duration",
    "narration",
    "visual_prompt",
    "on_screen_text",
]


# ── JSON extraction ────────────────────────────────────────────────────────────

def _extract_json_object(raw: str) -> dict:
    """Robustly extract a JSON object from Qwen's raw output.

    Handles:
      - <think>...</think> tags (Qwen3 extended thinking)
      - Markdown code fences (```json ... ```)
      - Leading / trailing prose before / after the JSON block
    """
    # 1. Strip <think>...</think> blocks
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # 2. Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"\s*```$",           "", raw, flags=re.IGNORECASE).strip()

    # 3. Try direct parse first (ideal case — Qwen obeyed the prompt)
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 4. Find the outermost {...} block (handles leading prose)
    start = raw.find("{")
    end   = raw.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = raw[start : end + 1]
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Qwen did not return a valid JSON object.\n"
        f"Raw output (first 600 chars):\n{raw[:600]}"
    )


# ── Scene validation ───────────────────────────────────────────────────────────

def _validate_scenes(data: dict) -> dict:
    """Validate and normalise the parsed scene plan dict.

    Raises ValueError with a clear message on any problem.
    Returns the (possibly normalised) dict on success.
    """
    if not isinstance(data, dict):
        raise ValueError("Scene data must be a JSON object (dict).")

    scenes = data.get("scenes")
    if not isinstance(scenes, list):
        raise ValueError("JSON is missing a 'scenes' array.")
    if len(scenes) < 5:
        raise ValueError(f"Qwen returned only {len(scenes)} scenes. Expected at least 5.")
    if len(scenes) > 8:
        scenes = scenes[:8]

    for i, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {i} is not a dict: {scene!r}")

        for field in REQUIRED_SCENE_FIELDS:
            if field not in scene:
                raise ValueError(f"Scene {i} missing field: {field}")

        if not isinstance(scene["scene_number"], int):
            raise ValueError(f"Scene {i} has a non-integer scene_number.")
        if not isinstance(scene["duration"], int) or not 4 <= scene["duration"] <= 8:
            raise ValueError(f"Scene {i} duration must be an integer between 4 and 8.")
        for field in ("narration", "visual_prompt", "on_screen_text"):
            if not isinstance(scene[field], str) or not scene[field].strip():
                raise ValueError(f"Scene {i} field '{field}' must be a non-empty string.")

    data["scenes"] = scenes
    data.setdefault("title", "AI Generated Video")
    data["total_duration"] = sum(s["duration"] for s in scenes)

    return data


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_video_scenes(
    content: str,
    language: str = "English",
    tone: str = "Professional",
    audience: str = "General public",
    target_duration: int = 30,
    pacing: str = "balanced",
) -> dict:
    """Call Qwen3 and return a validated video scene plan.

    Args:
        content:  Source text to convert into scenes.
        language: Narration language hint for the prompt.
        tone:     Tone hint (Professional, Casual, etc.).
        audience: Target audience hint.
        target_duration: Target video length in seconds (fills the template's
            TARGET DURATION slot).
        pacing: Narrative rhythm hint (fills the template's PACING slot).

    Returns:
        Dict with keys: title, total_duration, scenes (list of 5–8 dicts).

    Raises:
        QwenServiceError: If Ollama is unreachable or times out.
        ValueError:       If Qwen's output cannot be parsed / validated.
    """
    try:
        import sys as _sys
        from pathlib import Path as _P

        _b = _P(__file__).resolve().parent.parent
        if str(_b) not in _sys.path:
            _sys.path.insert(0, str(_b))
        from app.core.token_budgets import resolve_output_budget as _rob
        from app.core.token_budgets import truncate_to_token_budget as _trunc

        _np_scene = int(_rob("scene", None))
        _src, _info = _trunc((content or "").strip(), 3000, model=MODEL_NAME, stage="scene_gen")
        if _info.get("truncated"):
            import logging as _lg

            _lg.getLogger(__name__).warning(
                "scene_gen source truncated original=%s kept=%s",
                _info.get("original_tokens"),
                _info.get("kept_tokens"),
            )
    except Exception:
        _np_scene = 2000
        _src = (content or "").strip()
    prompt = SCENE_PROMPT_TEMPLATE.format(
        source_text=_src,
        target_duration=target_duration,
        pacing=pacing,
        scene_count=DEFAULT_SCENE_COUNT,
    )

    payload = {
        "model":  MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "think":  False,          # disable extended thinking → pure JSON output
        "format": "json",
        "options": {
            "num_predict": _np_scene,
            "temperature": 0.3,   # low temperature → less hallucination
        },
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=(5.0, REQUEST_TIMEOUT_SECS),
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise QwenServiceError(
            "Ollama timed out while generating video scenes."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise QwenServiceError(
            f"Ollama is unavailable: {exc}"
        ) from exc

    raw = response.json().get("response", "").strip()
    if not raw:
        raise ValueError("Qwen returned an empty response.")

    data = _extract_json_object(raw)
    return _validate_scenes(data)
