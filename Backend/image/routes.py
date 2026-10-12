import os
import time
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from text.document_extractor import extract_docx, extract_pdf, extract_txt
from text.qwen_service import QwenServiceError

from .generator import ImageGenerationError, get_forge_base_url, is_last_synthetic
from .prompt_engine import enhance_image_prompt, generate_scene_prompts
from .schemas import (
    EnhancePromptRequest,
    EnhancePromptResponse,
    ImageRequest,
    ImageResponse,
    InfographicRenderRequest,
    SceneImageRequest,
    SceneImageResponse,
)
from .service import generate_and_save_image, image_path


router = APIRouter(tags=["Image Generation"])


FORGE_OFFLINE_WARNING = (
    "Stable Diffusion Forge is offline — this is a labeled UI preview, not AI-generated imagery. "
    "Start Forge (run start.bat, or in the Forge folder: set COMMANDLINE_ARGS=--skip-python-version-check "
    "--api --listen --port 7860 && call webui-user.bat), then regenerate."
)

VALID_MODES = ("fast", "balanced", "quality")


def _check_forge_health() -> dict:
    """Probe the Forge WebUI API to report whether real image generation is available.

    Performs a real HTTP health check against /sdapi/v1/options on every call —
    never cached, never assumed. Only reports online=True after an HTTP 200.
    Also queries /sdapi/v1/sd-models so a running-but-model-less Forge is
    reported as online-without-model instead of misleadingly "ready".
    """
    import requests

    base_url = get_forge_base_url()
    start = time.perf_counter()
    try:
        response = requests.get(f"{base_url}/sdapi/v1/options", timeout=3.0)
        online = response.status_code == 200
    except Exception:
        online = False
        response = None
    # Detect "Forge running but no checkpoint installed" state.
    has_model: bool | None = None
    model_count = 0
    selected_model: str | None = None
    if online:
        try:
            models_resp = requests.get(f"{base_url}/sdapi/v1/sd-models", timeout=3.0)
            if models_resp.status_code == 200:
                try:
                    models = models_resp.json()
                except Exception:
                    models = None
                if isinstance(models, list):
                    model_count = len(models)
                    has_model = model_count > 0
                # Non-list (e.g. mocked) -> leave has_model=None = unknown, don't alarm.
            if response is not None:
                try:
                    opts = response.json()
                    if isinstance(opts, dict):
                        selected_model = opts.get("sd_model_checkpoint")
                except Exception:
                    pass
        except Exception:
            pass
    latency_ms = round((time.perf_counter() - start) * 1000)
    if online and has_model is False:
        message = (
            "Forge is running but has NO checkpoint model installed — txt2img will fail with "
            "'You do not have any model!'. Download a .safetensors file into "
            "Forge/models/Stable-diffusion, press ↻ Refresh in Forge, select it, then regenerate."
        )
    else:
        message = (
            "Forge is online — real Stable Diffusion generation enabled."
            if online
            else "Forge is offline — image requests will return labeled previews (or HTTP 503 with allow_placeholder=false). "
            "Run start.bat to start Forge with --api --port 7860."
        )
    return {
        "forge_url": base_url,
        "online": online,
        "has_model": has_model,
        "model_count": model_count,
        "selected_model": selected_model,
        "ready": bool(online and has_model),
        "latency_ms": latency_ms,
        "message": message,
    }


@router.get("/status", summary="Forge image-generation status")
def image_studio_status():
    """Report whether Stable Diffusion Forge is reachable at IMAGE_MODEL_URL.

    Always performs a live probe; 'online' is True only on HTTP 200.
    """
    return _check_forge_health()


def _validate_mode(mode: str) -> str:
    normalized = (mode or "fast").strip().lower()
    if normalized not in VALID_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported mode '{mode}'. Use one of: fast, balanced, quality.",
        )
    return normalized


def _is_instructional_or_unstructured(prompt: str) -> bool:
    """Detect if a prompt is an instructional request or unformatted document rather than a diffusion scene description."""
    lowered = prompt.lower()
    triggers = [
        "analyze the following", "analyze this", "extract its key", "extract the",
        "summarize the", "transform the information", "transform this", "multiple formats",
        "executive summary", "linkedin post", "ensure that all", "preserve the original meaning",
        "maintain factual accuracy", "avoid unsupported claims", "suitable for technical",
        "actionable points", "generate a", "create a script"
    ]
    if any(t in lowered for t in triggers):
        return True
    if len(prompt) > 120 and (prompt.count(".") >= 2 or prompt.count(",") >= 3):
        visual_keywords = ["shot", "photo", "cinematic", "lighting", "render", "illustration", "camera", "portrait", "landscape"]
        if not any(vk in lowered for vk in visual_keywords):
            return True
    return False


def _generate(request: ImageRequest, prefix: str = "image") -> ImageResponse:
    mode = _validate_mode(request.mode)
    prompt_to_use = request.prompt.strip()
    # Auto-enhance if the user provided instructional or raw document text
    if _is_instructional_or_unstructured(prompt_to_use):
        try:
            enh = enhance_image_prompt(prompt_to_use, negative_prompt=request.negative_prompt)
            if enh and enh.get("enhanced_prompt"):
                prompt_to_use = enh["enhanced_prompt"]
        except Exception:
            pass

    try:
        filename, generation_time, device = generate_and_save_image(
            prompt=prompt_to_use,
            negative_prompt=request.negative_prompt,
            width=request.width,
            height=request.height,
            steps=request.steps,
            mode=mode,
            prefix=prefix,
            allow_placeholder=request.allow_placeholder,
        )
    except ImageGenerationError as error:
        # 503 with actionable message; never a stack trace or internal path.
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    synthetic = is_last_synthetic()

    return ImageResponse(
        status="success",
        filename=filename,
        image_path=f"generated_images/{filename}",
        image_url=f"/api/image-studio/image/{filename}",
        generation_time=generation_time,
        device=device,
        steps=request.steps,
        width=request.width,
        height=request.height,
        synthetic=synthetic,
        warning=FORGE_OFFLINE_WARNING if synthetic else None,
    )


@router.post("/generate-image", response_model=ImageResponse)
def generate_image(request: ImageRequest):
    """Generate one image directly from a user-supplied prompt with performance tracking."""
    return _generate(request)


@router.post("/generate-infographic", response_model=ImageResponse)
def generate_infographic(request: InfographicRenderRequest):
    """Render a data-driven infographic PNG with matplotlib (no Forge/GPU required).

    Takes structured infographic content (headline, stats, points, CTA) plus
    layout/style and returns a persisted PNG served via /image/{filename}.
    Used by the Infographic Workspace and LinkedIn visual cards to replace
    the 'Waiting for Backend' placeholder with a real visualization.
    """
    start = time.perf_counter()
    try:
        from .infographic_renderer import render_infographic, save_infographic
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Matplotlib is not installed on the backend. Run: pip install matplotlib>=3.8.0",
        ) from exc

    # Normalize layout / style (renderer falls back to Corporate on unknown).
    layout = (request.layout or "Vertical").strip().capitalize()
    if layout not in ("Vertical", "Horizontal", "Timeline", "Process", "Comparison"):
        layout = "Vertical"
    style = (request.visual_style or "Corporate").strip().capitalize()
    if style not in ("Corporate", "Minimal", "Editorial", "Technology"):
        style = "Corporate"

    stats = [s.model_dump() for s in (request.key_statistics or [])][:6]
    points = [p.model_dump() for p in (request.supporting_points or [])][:6]
    # Guarantee non-empty canvas sections so matplotlib never renders blank.
    if not stats:
        stats = [{"value": "—", "label": "No metrics", "subtext": "extracted"}]
    if not points:
        points = [{"title": "Summary", "description": request.key_message[:120]}]

    try:
        png_bytes = render_infographic(
            key_message=request.key_message,
            key_statistics=stats,
            supporting_points=points,
            call_to_action=request.call_to_action or "Share this insight with your team.",
            layout=layout,
            visual_style=style,
            width_px=request.width,
            height_px=request.height,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Infographic rendering failed: {exc}") from exc

    try:
        filename = save_infographic(png_bytes, prefix="infographic")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not persist infographic PNG: {exc}") from exc

    elapsed = round(time.perf_counter() - start, 3)
    return ImageResponse(
        status="success",
        filename=filename,
        image_path=f"generated_images/{filename}",
        image_url=f"/api/image-studio/image/{filename}",
        generation_time=elapsed,
        device="cpu-matplotlib",
        steps=0,
        width=request.width,
        height=request.height,
        synthetic=False,
        warning=None,
    )


@router.post("/enhance-prompt", response_model=EnhancePromptResponse)
def enhance_prompt(request: EnhancePromptRequest):
    """Run the Image Prompt Enhancement Agent on long / instructional text.

    Returns an image-model-ready visual prompt without calling Forge.
    Uses Qwen/Ollama when available, deterministic fallback otherwise.
    """
    try:
        result = enhance_image_prompt(
            text=request.text,
            style=request.style,
            negative_prompt=request.negative_prompt,
            aspect_ratio=request.aspect_ratio,
        )
    except QwenServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    negative = result.get("negative_prompt") or (request.negative_prompt or "").strip()
    return EnhancePromptResponse(
        enhanced_prompt=result["enhanced_prompt"],
        negative_prompt=negative or "blurry, low quality, distorted, watermark, text, logo",
        subject=result.get("subject", ""),
        llm_used=bool(result.get("llm_used", False)),
        warning=None if result.get("llm_used") else "LLM unavailable — deterministic enhancement used.",
    )


@router.post("/generate-scene-images", response_model=SceneImageResponse)
def generate_scene_images(request: SceneImageRequest):
    """Turn a video script into engineered prompts and generate one image per scene."""
    mode = _validate_mode(request.mode)
    try:
        scenes = generate_scene_prompts(request.script)
    except QwenServiceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if not scenes:
        raise HTTPException(status_code=400, detail="No scenes could be extracted from the script.")

    images = []
    for index, scene in enumerate(scenes, 1):
        image_request = ImageRequest(
            prompt=scene["prompt"],
            negative_prompt=request.negative_prompt,
            mode=mode,
            width=request.width,
            height=request.height,
            steps=request.steps,
            allow_placeholder=request.allow_placeholder,
        )
        images.append(_generate(image_request, prefix=f"scene_{index:02d}"))
    return SceneImageResponse(images=images, scenes=scenes)


def _extract_uploaded_text(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix == ".txt":
        return extract_txt(upload)
    if suffix == ".pdf":
        return extract_pdf(upload)
    if suffix == ".docx":
        return extract_docx(upload)
    raise HTTPException(status_code=400, detail="Only TXT, PDF and DOCX files are supported.")


@router.post("/generate-scene-images-from-file", response_model=SceneImageResponse)
async def generate_scene_images_from_file(file: UploadFile = File(...)):
    """Extract a document, have the agent create a storyboard, then generate its scene images."""
    content = _extract_uploaded_text(file)
    if not content.strip():
        raise HTTPException(status_code=400, detail="The uploaded document contains no text.")
    return generate_scene_images(SceneImageRequest(script=content))


@router.get("/image/{filename}", response_class=FileResponse)
def get_image(filename: str, download: bool = False):
    """Retrieve a generated PNG by filename (inline for <img>, or forced download)."""
    path = image_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    if download:
        return FileResponse(path, media_type="image/png", filename=path.name)
    return FileResponse(path, media_type="image/png")
