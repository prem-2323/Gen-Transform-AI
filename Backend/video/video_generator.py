"""
video/video_generator.py
~~~~~~~~~~~~~~~~~~~~~~~~
Complete Video Generation Engine for ContentForge AI / Gen-Transform-AI.

Implements:
  - Step 2: Media organization and TTS audio pipeline via edge-tts.
  - Step 3: Video script generation using Qwen3 with fact-validation.
  - Step 4: Scene image generation (Forge txt2img with sample image fallback).
  - Video rendering: FFmpeg assembly (1080p landscape/vertical, H.264, 30 FPS, MP4).

Directory Structure:
  generated/
  ├── audio/   (scene_01.mp3, scene_02.mp3, ...)
  ├── scenes/  (scene_01.png, scene_02.png, ...)
  └── videos/  (final_video.mp4)
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from video.tts_generator import generate_scene_audio_files

log = logging.getLogger("gen-transform.video.video_generator")

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BASE_DIR / "generated"
AUDIO_DIR = GENERATED_DIR / "audio"
SCENES_DIR = GENERATED_DIR / "scenes"
VIDEOS_DIR = GENERATED_DIR / "videos"

# Ensure root bin is in PATH for ffmpeg
BIN_DIR = BASE_DIR.parent / "bin"
if BIN_DIR.is_dir() and str(BIN_DIR) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{BIN_DIR}{os.pathsep}{os.environ.get('PATH', '')}"

# ── Video Specifications ───────────────────────────────────────────────────────
RESOLUTIONS = {
    "landscape": (1920, 1080),
    "vertical": (1080, 1920),
}
DEFAULT_FPS = 30
VIDEO_CODEC = "libx264"
PIX_FMT = "yuv420p"

# ── Qwen3 Configuration ───────────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
QWEN_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
SD_FORGE_URL = os.getenv("IMAGE_MODEL_URL", "http://127.0.0.1:7860")


# ==============================================================================
# Step 3 — Generate Video Script using Qwen3 with Fact-Validation
# ==============================================================================

SCRIPT_GENERATION_PROMPT = """\
You are an expert educational video producer. Convert the source document into a structured video script.

SOURCE DOCUMENT:
{source_text}

TARGET SCENE COUNT: {scene_count}

CRITICAL RULES:
1. Every scene must be directly grounded in facts from the source document.
2. Do not introduce outside or unsupported claims.
3. "text": The narration that will be spoken aloud in the video for this scene.
4. "visual_prompt": A descriptive, photorealistic visual scene description for the image-generation model.

Return ONLY a valid JSON object matching this exact schema:
{{
  "title": "Short descriptive video title",
  "scenes": [
    {{
      "text": "Spoken narration for scene 1",
      "visual_prompt": "A professional, photorealistic description of scene 1 visuals"
    }}
  ]
}}
"""


def _clean_json_output(raw: str) -> str:
    """Strip markdown code blocks, <think> tags, and extraneous text."""
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL)
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.IGNORECASE)
    match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def _deterministic_script_fallback(source_text: str, scene_count: int = 3) -> Dict[str, Any]:
    """Extractive fallback that partitions source text into grounded factual scenes."""
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", source_text)
        if len(s.strip()) > 15
    ]
    if not sentences:
        sentences = [source_text.strip() or "Overview of the subject."]

    step = max(1, len(sentences) // scene_count)
    chosen_sentences = sentences[::step][:scene_count]
    while len(chosen_sentences) < scene_count and len(chosen_sentences) < len(sentences):
        chosen_sentences.append(sentences[len(chosen_sentences)])

    scenes = []
    for idx, s in enumerate(chosen_sentences, 1):
        clean_s = s.rstrip(".!?")
        scenes.append({
            "text": f"{clean_s}.",
            "visual_prompt": f"A clean, photorealistic, cinematic illustration representing {clean_s.lower()[:80]}, high resolution, 8k",
        })

    title = sentences[0][:50].rstrip(" ,;.") if sentences else "Knowledge Summary"
    return {"title": title, "scenes": scenes}


def validate_script_against_source(script: Dict[str, Any], source_text: str) -> Tuple[bool, List[str]]:
    """Fact-validation pipeline checking that generated script is grounded in source text."""
    issues = []
    source_lower = source_text.lower()
    source_words = set(re.findall(r"\b\w{4,}\b", source_lower))

    scenes = script.get("scenes", [])
    if not scenes:
        issues.append("Script contains no scenes.")
        return False, issues

    for i, scene in enumerate(scenes, 1):
        narration = scene.get("text", "")
        if not narration.strip():
            issues.append(f"Scene {i} narration text is empty.")
            continue

        narration_words = set(re.findall(r"\b\w{4,}\b", narration.lower()))
        if source_words and narration_words:
            overlap = narration_words.intersection(source_words)
            overlap_ratio = len(overlap) / max(1, len(narration_words))
            # If less than 10% lexical support exists, flag for potential hallucination
            if overlap_ratio < 0.10:
                issues.append(
                    f"Scene {i} may contain unsupported claims (factual overlap: {overlap_ratio:.0%})."
                )

    is_valid = len(issues) == 0
    return is_valid, issues


def generate_video_script(
    source_content: str,
    scene_count: int = 3,
    enforce_fact_validation: bool = True,
) -> Dict[str, Any]:
    """Generate structured video script using Qwen3, with fact validation and fallback.

    Args:
        source_content: Source text/document to transform.
        scene_count: Target number of scenes.
        enforce_fact_validation: Check script against source facts.

    Returns:
        Dict matching {"title": str, "scenes": [{"text": str, "visual_prompt": str}]}
    """
    prompt = SCRIPT_GENERATION_PROMPT.format(
        source_text=source_content.strip(),
        scene_count=scene_count,
    )

    script_data = None

    # 1. Attempt LLM generation via Ollama / Qwen3
    try:
        import requests

        payload = {
            "model": QWEN_MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.2, "num_predict": 1024},
        }
        res = requests.post(OLLAMA_URL, json=payload, timeout=(3.0, 45.0))
        if res.status_code == 200:
            raw_text = res.json().get("response", "")
            cleaned = _clean_json_output(raw_text)
            parsed = json.loads(cleaned)
            if "scenes" in parsed and isinstance(parsed["scenes"], list) and len(parsed["scenes"]) > 0:
                script_data = parsed
    except Exception as exc:
        log.warning("Qwen3 Ollama generation unavailable (%s). Using factual fallback.", exc)

    # 2. Fallback to extractive factual generation if Ollama fails or output is malformed
    if not script_data:
        script_data = _deterministic_script_fallback(source_content, scene_count=scene_count)

    # Normalize fields (ensure each scene has 'text' and 'visual_prompt')
    normalized_scenes = []
    for sc in script_data.get("scenes", []):
        text_val = sc.get("text") or sc.get("narration") or "Factual concept."
        visual_val = sc.get("visual_prompt") or sc.get("visual") or "Cinematic scene representation"
        normalized_scenes.append({
            "text": text_val.strip(),
            "visual_prompt": visual_val.strip(),
        })
    script_data["scenes"] = normalized_scenes

    # 3. Fact Validation
    if enforce_fact_validation:
        is_valid, validation_issues = validate_script_against_source(script_data, source_content)
        script_data["fact_validation"] = {
            "is_grounded": is_valid,
            "issues": validation_issues,
        }

    return script_data


# ==============================================================================
# Step 4 — Generate Images for Each Scene (Forge with Sample Fallback)
# ==============================================================================

def create_sample_scene_image(
    scene_index: int,
    total_scenes: int,
    scene_data: Dict[str, Any],
    output_path: Path,
    resolution: Tuple[int, int] = (1920, 1080),
) -> str:
    """Generate a clean, high-resolution sample image using Pillow for testing."""
    width, height = resolution
    img = Image.new("RGB", (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Draw modern grid background
    grid_size = 80
    for x in range(0, width, grid_size):
        draw.line([(x, 0), (x, height)], fill=(30, 41, 59), width=1)
    for y in range(0, height, grid_size):
        draw.line([(0, y), (width, y)], fill=(30, 41, 59), width=1)

    # Outer Neon Border
    draw.rectangle([(24, 24), (width - 24, height - 24)], outline=(59, 130, 246), width=3)
    draw.rectangle([(32, 32), (width - 32, height - 32)], outline=(30, 41, 59), width=1)

    # Header Badge: Scene indicator
    badge_text = f"SCENE {scene_index:02d} / {total_scenes:02d}"
    draw.rectangle([(64, 64), (320, 114)], fill=(30, 58, 138), outline=(59, 130, 246), width=2)
    draw.text((84, 76), badge_text, fill=(219, 234, 254))

    # Center Visual Card
    card_margin = 120
    draw.rectangle(
        [(card_margin, 180), (width - card_margin, height - 160)],
        fill=(24, 24, 27),
        outline=(59, 130, 246),
        width=2,
    )

    # Card Content: Visual Prompt
    prompt_title = "VISUAL PROMPT (Stable Diffusion Target):"
    draw.text((card_margin + 40, 220), prompt_title, fill=(96, 165, 250))

    prompt_text = scene_data.get("visual_prompt", "High quality cinematic visual")
    # Simple word wrapping
    wrapped_lines = []
    words = prompt_text.split()
    current_line = []
    for word in words:
        current_line.append(word)
        if len(" ".join(current_line)) > 70:
            wrapped_lines.append(" ".join(current_line))
            current_line = []
    if current_line:
        wrapped_lines.append(" ".join(current_line))

    y_offset = 270
    for line in wrapped_lines[:4]:
        draw.text((card_margin + 40, y_offset), f"  {line}", fill=(243, 244, 246))
        y_offset += 36

    # Narration Box
    narration_title = "SCENE NARRATION:"
    draw.text((card_margin + 40, y_offset + 30), narration_title, fill=(52, 211, 153))

    narr_text = scene_data.get("text") or scene_data.get("narration", "")
    draw.text((card_margin + 40, y_offset + 70), f'"{narr_text[:140]}"', fill=(209, 213, 219))

    # Footer Status
    draw.text(
        (card_margin + 40, height - 210),
        f"Resolution: {width}x{height} | Format: MP4 / H.264 | FPS: {DEFAULT_FPS}",
        fill=(156, 163, 175),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return str(output_path.resolve())


def generate_scene_image(
    scene_data: Dict[str, Any],
    scene_index: int,
    total_scenes: int,
    output_path: Path,
    resolution: Tuple[int, int] = (1920, 1080),
    use_forge: bool = True,
) -> str:
    """Generate image using Stable Diffusion Forge API, falling back to sample image."""
    width, height = resolution
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if use_forge:
        try:
            import requests

            prompt = f"{scene_data.get('visual_prompt', '')}, cinematic, photorealistic, 8k, masterpiece"
            payload = {
                "prompt": prompt,
                "negative_prompt": "blurry, low quality, distorted, watermark, logo, text",
                "width": min(1024, width),
                "height": min(1024, height),
                "steps": 15,
                "cfg_scale": 7,
                "batch_size": 1,
            }
            res = requests.post(
                f"{SD_FORGE_URL.rstrip('/')}/sdapi/v1/txt2img",
                json=payload,
                timeout=(2.0, 60.0),
            )
            if res.status_code == 200:
                import base64
                images = res.json().get("images", [])
                if images:
                    raw_bytes = base64.b64decode(images[0].split(",", 1)[-1])
                    img = Image.open(BytesIO(raw_bytes))
                    # Resize to requested canvas if needed
                    if img.size != (width, height):
                        img = img.resize((width, height), Image.Resampling.LANCZOS)
                    img.save(output_path, format="PNG")
                    return str(output_path.resolve())
        except Exception as exc:
            log.info("Forge not reachable (%s); generating sample image.", exc)

    # Fallback to sample image for testing
    return create_sample_scene_image(
        scene_index=scene_index,
        total_scenes=total_scenes,
        scene_data=scene_data,
        output_path=output_path,
        resolution=resolution,
    )


def generate_scene_images(
    scenes: List[Dict[str, Any]],
    output_dir: Path | str = SCENES_DIR,
    orientation: str = "landscape",
    use_forge: bool = True,
    prefix: str = "scene",
) -> List[str]:
    """Generate one image per scene and save to generated/scenes/scene_XX.png.

    Args:
        scenes: List of scene dicts with 'visual_prompt'.
        output_dir: Target output directory (default: generated/scenes).
        orientation: 'landscape' (1920x1080) or 'vertical' (1080x1920).
        use_forge: Attempt Forge before sample fallback.
        prefix: Filename prefix.

    Returns:
        List of absolute paths to generated PNG images.
    """
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    resolution = RESOLUTIONS.get(orientation, RESOLUTIONS["landscape"])

    image_paths: List[str] = []
    total = len(scenes)
    for idx, scene in enumerate(scenes, 1):
        filename = f"{prefix}_{idx:02d}.png"
        out_file = target_dir / filename
        saved = generate_scene_image(
            scene_data=scene,
            scene_index=idx,
            total_scenes=total,
            output_path=out_file,
            resolution=resolution,
            use_forge=use_forge,
        )
        image_paths.append(saved)

    return image_paths


# ==============================================================================
# FFmpeg Video Assembly Pipeline (H.264, 30 FPS, Concat demuxer)
# ==============================================================================

def get_media_duration(file_path: str) -> float:
    """Return media file duration using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return max(1.0, float(res.stdout.strip()))
    except Exception:
        # Default minimum scene duration
        return 4.0


def render_scene_video(
    image_path: str,
    audio_path: str,
    output_path: str,
    fps: int = DEFAULT_FPS,
) -> str:
    """Combine one scene image + MP3 into an MP4 using FFmpeg."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        image_path,
        "-i",
        audio_path,
        "-c:v",
        VIDEO_CODEC,
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        PIX_FMT,
        "-r",
        str(fps),
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def concatenate_videos(
    scene_video_paths: List[str],
    output_video_path: str,
) -> str:
    """Concatenate scene MP4s using FFmpeg concat demuxer."""
    out_file = Path(output_video_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    concat_list_file = out_file.parent / "concat_list.txt"
    with open(concat_list_file, "w", encoding="utf-8") as f:
        for p in scene_video_paths:
            f.write(f"file '{Path(p).resolve().as_posix()}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_file),
        "-c",
        "copy",
        str(out_file),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    finally:
        if concat_list_file.exists():
            concat_list_file.unlink()

    return str(out_file.resolve())


# ==============================================================================
# End-to-End Video Generation Pipeline
# ==============================================================================

class VideoGenerator:
    """Master controller integrating Steps 1-4 for complete AI video generation."""

    def __init__(
        self,
        orientation: str = "landscape",
        output_dir: Path | str = GENERATED_DIR,
    ):
        self.orientation = orientation
        self.output_dir = Path(output_dir)
        self.audio_dir = self.output_dir / "audio"
        self.scenes_dir = self.output_dir / "scenes"
        self.videos_dir = self.output_dir / "videos"

        for d in (self.audio_dir, self.scenes_dir, self.videos_dir):
            d.mkdir(parents=True, exist_ok=True)

    async def generate_video_from_text(
        self,
        source_text: str,
        scene_count: int = 3,
        voice: str = "en-US-AriaNeural",
        use_forge: bool = True,
    ) -> Dict[str, Any]:
        """Execute full end-to-end pipeline: Script -> Audio -> Images -> MP4 Video."""
        start_time = time.perf_counter()

        # Step 3: Generate Script
        script = generate_video_script(source_text, scene_count=scene_count)
        scenes = script["scenes"]

        # Step 2: Generate Audio for each scene
        audio_files = await generate_scene_audio_files(
            scenes=scenes,
            output_dir=self.audio_dir,
            voice=voice,
        )

        # Step 4: Generate Images for each scene
        image_files = generate_scene_images(
            scenes=scenes,
            output_dir=self.scenes_dir,
            orientation=self.orientation,
            use_forge=use_forge,
        )

        # FFmpeg: Render individual scene clips
        scene_clips = []
        for i, (img, aud) in enumerate(zip(image_files, audio_files), 1):
            clip_path = self.videos_dir / f"clip_{i:02d}.mp4"
            render_scene_video(img, aud, str(clip_path))
            scene_clips.append(str(clip_path))

        # FFmpeg: Concatenate into final video
        final_video = self.videos_dir / "final_video.mp4"
        concatenate_videos(scene_clips, str(final_video))

        duration = sum(get_media_duration(a) for a in audio_files)
        total_time = round(time.perf_counter() - start_time, 2)

        return {
            "title": script.get("title", "Generated Video"),
            "video_path": str(final_video),
            "duration": round(duration, 2),
            "generation_time": total_time,
            "scene_count": len(scenes),
            "scenes": scenes,
            "audio_files": audio_files,
            "image_files": image_files,
            "fact_validation": script.get("fact_validation", {}),
        }


# ==============================================================================
# Standalone CLI / Verification Runner
# ==============================================================================

if __name__ == "__main__":
    import asyncio

    sample_doc = (
        "Cybersecurity protects sensitive digital information and networks from malicious attacks. "
        "Organizations use strong authentication, access control, and continuous monitoring to stay safe. "
        "Security awareness training educates users to avoid suspicious links and prevent phishing incidents."
    )

    print("=" * 70)
    print("Testing Video Generator Pipeline (Steps 2, 3, 4 + FFmpeg Render)")
    print("=" * 70)

    vg = VideoGenerator(orientation="landscape")
    result = asyncio.run(vg.generate_video_from_text(sample_doc, scene_count=3, use_forge=False))

    print(f"[OK] Title: {result['title']}")
    print(f"[OK] Video Output: {result['video_path']}")
    print(f"[OK] Total Scenes: {result['scene_count']}")
    print(f"[OK] Duration: {result['duration']}s | Render Time: {result['generation_time']}s")
    print(f"[OK] Fact Validation: {result['fact_validation']}")
    print("=" * 70)
