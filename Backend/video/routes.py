"""
video/routes.py
~~~~~~~~~~~~~~~
FastAPI router for the full video generation and intelligent video planning pipeline.

POST /video/plan
    Content → IntelligentVideoPlanner → scenes count, scene duration, visual importance,
    narration quota, transition timing, subtitle timing, and FFmpeg sync metadata.

POST /video/generate-video
    text → Intelligent Video Planning → Forge images → Edge TTS audio
         → FFmpeg scene videos → concat → SRT → subtitle burn
    Returns: VideoResponse with final MP4 path + intelligent video plan metadata.

GET /video/{filename}
    Stream / download a generated MP4 by filename.
"""

import asyncio
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from image.generator import ImageGenerationError
from text.qwen_service import QwenServiceError

from .renderer import (
    burn_subtitles,
    concatenate_scene_videos,
    fit_audio_to_duration,
    generate_srt,
    render_all_scene_videos,
)
from .scene_generator import generate_video_scenes
from .schemas import SceneSummary, VideoRequest, VideoResponse, VideoPlanRequest, IntelligentVideoPlan
from .service import generate_all_scene_audio, generate_all_scene_images
from .planner import IntelligentVideoPlanner, normalize_tone, seconds_to_srt_timestamp, tts_rate_for_tone
from .video_generator import VideoGenerator, generate_video_script


router = APIRouter(prefix="/video", tags=["Video Generation"])

VIDEO_DIR = Path(os.getenv("VIDEO_STORAGE", "generated_videos"))


# ── POST /video/plan ───────────────────────────────────────────────────────────

@router.post(
    "/plan",
    response_model=IntelligentVideoPlan,
    summary="Intelligent Video Planning Engine",
    description=(
        "Calculates optimal number of scenes, scene durations, visual importance tiers, "
        "narration word quotas, transition timing, and subtitle synchronization from source content."
    ),
)
async def plan_video_endpoint(request: VideoPlanRequest):
    """Calculates intelligent video timeline and synchronization metadata."""
    try:
        plan = IntelligentVideoPlanner.plan_video(
            content=request.text,
            target_duration=request.target_duration,
            pacing=request.pacing,
            language=request.language,
            tone=request.tone,
            audience=request.audience
        )
        return plan
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Intelligent video planning failed: {str(exc)}"
        )


# ── POST /video/generate-video ─────────────────────────────────────────────────

@router.post(
    "/generate-video",
    response_model=VideoResponse,
    summary="Generate a complete AI video from text",
    description=(
        "Full pipeline: Intelligent Video Planning → Forge images → Edge TTS narration "
        "→ FFmpeg scene videos → concat → SRT subtitles → final subtitled MP4."
    ),
)
async def generate_video(request: VideoRequest):
    """End-to-end video generation endpoint with Intelligent Video Planning."""

    # ── 1. Intelligent Video Planning (Scene count, duration, importance, transitions) ──
    try:
        video_plan = IntelligentVideoPlanner.plan_video(
            content=request.text,
            target_duration=request.target_duration,
            pacing=request.pacing,
            language=request.language,
            tone=request.tone,
            audience=request.audience
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Video planning failed: {exc}"
        )

    planned_scenes = video_plan.scenes
    if not planned_scenes:
        raise HTTPException(status_code=502, detail="Video planner produced zero scenes.")

    # Unique identifier for this video run
    video_uid = uuid.uuid4().hex[:10]
    prefix = f"scene_{video_uid}"
    planned_durations = [float(s.duration) for s in planned_scenes]

    # Convert to scene dicts for image/audio generators
    scenes = [
        {
            "scene_number": s.scene_number,
            "duration": s.duration,
            "visual_importance": s.visual_importance,
            "visual_tier": s.visual_tier,
            "narration": s.narration,
            "visual_prompt": s.visual_prompt,
            "on_screen_text": s.on_screen_text,
            "transition_type": s.transition_type,
            "transition_duration": s.transition_duration,
            "subtitle_start": s.subtitle_start,
            "subtitle_end": s.subtitle_end
        }
        for s in planned_scenes
    ]

    # ── 2. Forge → scene images (sequential) ──────────────────────────────────
    try:
        image_paths = generate_all_scene_images(
            scenes=scenes,
            width=request.width,
            height=request.height,
            steps=request.steps,
            prefix=prefix,
        )
    except ImageGenerationError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Forge / Stable Diffusion is unavailable: {exc}",
        ) from exc

    # ── 3. Edge TTS → narration MP3s (concurrent, tone sets prosody rate) ─────
    tts_rate = tts_rate_for_tone(request.tone)
    audio_paths = await generate_all_scene_audio(
        scenes=scenes,
        voice=request.voice,
        prefix=prefix,
        rate=tts_rate,
    )

    # ── 3.5 Conform audio to planned scene durations ──────────────────────────
    # The planner budgets narration words per scene, but real TTS speech rates
    # vary by voice/language. Previously any overrun stretched the scene
    # (max(planned, audio)), so a 10s target routinely rendered as ~12.7s.
    # Now narration within a natural time-stretch range is fitted to the plan
    # with FFmpeg atempo, so the final video honors the target duration.
    # Only extreme overruns extend the scene (reported in the plan metadata).
    actual_scene_durations = []
    fitted_audio_paths = []
    fitted_scene_count = 0
    extended_scene_count = 0
    for i, planned in enumerate(planned_durations):
        fitted_path, actual = fit_audio_to_duration(audio_paths[i], planned)
        fitted_audio_paths.append(fitted_path)
        actual_scene_durations.append(actual)
        if fitted_path != audio_paths[i]:
            fitted_scene_count += 1
        if actual > planned + 0.05:
            extended_scene_count += 1
    audio_paths = fitted_audio_paths
    total_duration = round(sum(actual_scene_durations), 2)

    # Recompute cumulative timestamps perfectly synchronized with rendered audio
    actual_start_times = []
    actual_end_times = []
    actual_sub_starts = []
    actual_sub_ends = []
    cumulative_t = 0.0

    for dur in actual_scene_durations:
        st = round(cumulative_t, 2)
        et = round(cumulative_t + dur, 2)
        cumulative_t = et
        actual_start_times.append(st)
        actual_end_times.append(et)
        actual_sub_starts.append(seconds_to_srt_timestamp(st))
        actual_sub_ends.append(seconds_to_srt_timestamp(et))

    # ── 4. FFmpeg → per-scene MP4s ────────────────────────────────────────────
    try:
        scene_video_paths = render_all_scene_videos(
            image_paths=image_paths,
            audio_paths=audio_paths,
            durations=actual_scene_durations,
            width=request.width,
            height=request.height,
            prefix=prefix,
        )
    except (RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"FFmpeg scene render failed: {exc}",
        ) from exc

    # ── 5. SRT subtitle file with synchronized timings ────────────────────────
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    srt_path = generate_srt(
        scenes=scenes,
        audio_paths=audio_paths,
        durations=actual_scene_durations,
        output_path=str(VIDEO_DIR / f"subtitles_{video_uid}.srt"),
    )

    # ── 6. Concatenate scene MP4s → final_video.mp4 ───────────────────────────
    raw_video_path = str(VIDEO_DIR / f"video_{video_uid}_raw.mp4")

    try:
        concatenate_scene_videos(
            scene_video_paths=scene_video_paths,
            output_path=raw_video_path,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"FFmpeg concat failed: {exc}",
        ) from exc

    # ── 7. Burn subtitles → final_video_subtitled.mp4 ────────────────────────
    final_video_path = str(VIDEO_DIR / f"video_{video_uid}.mp4")
    font_size = max(18, min(32, int(request.width / 32)))

    try:
        burn_subtitles(
            video_path=raw_video_path,
            srt_path=srt_path,
            output_path=final_video_path,
            font_size=font_size,
        )
    except (RuntimeError, FileNotFoundError) as exc:
        # Subtitle burn fallback
        final_video_path = raw_video_path

    # Clean up raw (un-subtitled) intermediate video if different from final
    raw = Path(raw_video_path)
    if raw.exists() and raw_video_path != final_video_path:
        raw.unlink(missing_ok=True)

    # Clean up individual scene mp4s to conserve disk
    for p in scene_video_paths:
        Path(p).unlink(missing_ok=True)

    # ── 8. Build synchronized scene summary ───────────────────────────────────
    scene_details = [
        SceneSummary(
            scene_number=scene.get("scene_number", i + 1),
            duration=actual_scene_durations[i],
            visual_importance=scene.get("visual_importance", 0.8),
            visual_tier=scene.get("visual_tier", "MEDIUM"),
            narration=scene.get("narration", ""),
            visual_prompt=scene.get("visual_prompt", ""),
            on_screen_text=scene.get("on_screen_text", ""),
            start_time=actual_start_times[i],
            end_time=actual_end_times[i],
            transition_type=scene.get("transition_type", "crossfade"),
            subtitle_start=actual_sub_starts[i],
            subtitle_end=actual_sub_ends[i],
            image_file=Path(image_paths[i]).name,
            audio_file=Path(audio_paths[i]).name,
        )
        for i, scene in enumerate(scenes)
    ]

    # Update video_plan with synchronized timings
    video_plan.total_calculated_duration = total_duration
    for i, s in enumerate(video_plan.scenes):
        if i < len(actual_scene_durations):
            s.duration = actual_scene_durations[i]
            s.start_time = actual_start_times[i]
            s.end_time = actual_end_times[i]
            s.subtitle_start = actual_sub_starts[i]
            s.subtitle_end = actual_sub_ends[i]

    # Echo the actually-applied render settings so the studio UI can show
    # exactly which duration / pacing / tone / voice / resolution / steps
    # produced this video (previously these were fire-and-forget).
    video_plan.ffmpeg_sync_metadata = {
        **(video_plan.ffmpeg_sync_metadata or {}),
        "render_settings": {
            "target_duration": video_plan.target_duration,
            "actual_duration": total_duration,
            "pacing": video_plan.pacing,
            "tone": normalize_tone(request.tone),
            "tts_rate": tts_rate,
            "voice": request.voice,
            "language": request.language,
            "width": request.width,
            "height": request.height,
            "steps": request.steps,
            "tempo_fitted_scenes": fitted_scene_count,
            "extended_scenes": extended_scene_count,
        },
    }

    return VideoResponse(
        status="success",
        message="Video generated successfully with intelligent planning",
        video_file=final_video_path,
        subtitle_file=srt_path,
        scenes=len(scenes),
        duration=total_duration,
        video_plan=video_plan,
        scene_details=scene_details,
    )


# ── GET /video/download ────────────────────────────────────────────────────────

@router.get(
    "/download",
    summary="Step 9 — Download Generated Video",
    description="Serves the generated MP4 file as contentforge_video.mp4.",
)
def download_video_endpoint():
    """Download the final synthesized MP4 video."""
    candidates = [
        Path("generated/videos/final_video.mp4"),
        Path(__file__).resolve().parent.parent / "generated" / "videos" / "final_video.mp4",
        VIDEO_DIR / "final_video.mp4",
    ]
    target_file = None
    for c in candidates:
        if c.exists():
            target_file = c
            break

    if not target_file:
        raise HTTPException(
            status_code=404,
            detail="Video not generated yet",
        )

    return FileResponse(
        target_file,
        media_type="video/mp4",
        filename="contentforge_video.mp4",
    )


# ── GET /video/{filename} ──────────────────────────────────────────────────────

@router.get(
    "/{filename}",
    response_class=FileResponse,
    summary="Stream or download a generated video or subtitle file",
    description="Retrieve a generated MP4 or SRT by filename for playback or download.",
)
def get_video(filename: str, download: bool = Query(False, description="Force download instead of inline playback")):
    """Serve a generated MP4 or SRT file by filename."""
    candidate = (VIDEO_DIR / filename).resolve()
    storage_root = VIDEO_DIR.resolve()

    if candidate.parent != storage_root or candidate.suffix.lower() not in [".mp4", ".srt"]:
        raise HTTPException(status_code=400, detail="Invalid video or subtitle filename.")

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")

    media_type = "video/mp4" if candidate.suffix.lower() == ".mp4" else "text/plain"
    # No attachment filename header: lets the browser stream <video> inline
    # instead of forcing a download. Downloads happen via the ?download=1 flag.
    if download:
        return FileResponse(path=str(candidate), media_type=media_type, filename=candidate.name)
    return FileResponse(path=str(candidate), media_type=media_type)


# ── POST /video/script (Step 3) ────────────────────────────────────────────────

@router.post(
    "/script",
    summary="Generate Video Script with Fact Validation (Step 3)",
    description="Transforms source content into structured scenes (text + visual_prompt) with factual grounding validation.",
)
async def generate_script_endpoint(
    text: str = Query(..., description="Source document or topic content"),
    scene_count: int = Query(3, ge=1, le=10, description="Target number of scenes"),
):
    """Generate structured script with text, visual_prompt, and fact validation."""
    return generate_video_script(source_content=text, scene_count=scene_count)


# ── POST /video/pipeline (Steps 2-4) ──────────────────────────────────────────

@router.post(
    "/pipeline",
    summary="End-to-End Video Generation Pipeline (Steps 2-4)",
    description="Full automated workflow: Step 3 script -> Step 2 TTS -> Step 4 images -> FFmpeg MP4 assembly.",
)
async def generate_video_pipeline_endpoint(
    text: str = Query(..., description="Source content"),
    scene_count: int = Query(3, ge=1, le=10, description="Number of scenes"),
    orientation: str = Query("landscape", pattern="^(landscape|vertical)$"),
    use_forge: bool = Query(True, description="Attempt Stable Diffusion Forge image generation"),
):
    """Executes full video generation pipeline and outputs final MP4."""
    vg = VideoGenerator(orientation=orientation)
    return await vg.generate_video_from_text(
        source_text=text,
        scene_count=scene_count,
        use_forge=use_forge,
    )


# ── STEP 9 — Direct /video/generate and /video/download ───────────────────────

from typing import List
from pydantic import BaseModel
from .video_generator import generate_video


class SceneInput(BaseModel):
    text: str


class SimpleVideoRequest(BaseModel):
    title: str = "SIH 26154 Content Transformation"
    scenes: list[SceneInput]


@router.post(
    "/generate",
    summary="Step 9 — Generate Video from Scenes",
    description="Takes a list of scene texts, synthesizes voice-over with edge-tts, and renders MP4 via FFmpeg.",
)
def create_video_endpoint(request: SimpleVideoRequest):
    """Generates MP4 video from given scene texts."""
    try:
        scenes = [{"text": scene.text} for scene in request.scenes]
        output = generate_video(scenes, title=request.title)
        return {
            "status": "completed",
            "title": request.title,
            "video_path": output,
            "download_url": "/video/download",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Video generation failed: {exc}",
        )
