"""
video/video_generator.py
~~~~~~~~~~~~~~~~~~~~~~~~
Complete Video Generation Engine for ContentForge AI / Gen-Transform-AI (SIH 26154).

Steps implemented:
  - Step 3: Script generation using Qwen3 with fact-consistency validation.
  - Step 4: Scene image generation (Forge or sample visuals).
  - Step 5: AI voice-over generation via edge-tts.
  - Step 6: FFmpeg scene clip creation, concatenation, and SRT subtitle muxing.
  - Step 7: Sample scene cards generator via Pillow.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from video.tts_generator import create_voice

# Ensure local bin directory is in PATH for ffmpeg and ffprobe
for candidate in [
    Path(__file__).resolve().parent.parent.parent / "bin",
    Path(__file__).resolve().parent.parent / "bin",
]:
    if candidate.is_dir() and str(candidate) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{candidate}{os.pathsep}{os.environ.get('PATH', '')}"

BASE = Path("generated")
SCENES = BASE / "scenes"
AUDIO = BASE / "audio"
VIDEOS = BASE / "videos"

for folder in (SCENES, AUDIO, VIDEOS):
    folder.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# Step 6 — FFmpeg Helpers
# ==============================================================================

def run_command(command):
    """Execute a shell command with subprocess.run(check=True)."""
    subprocess.run(command, check=True)


def get_duration(file_path):
    """Calculate exact audio duration using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def make_scene_clip(image_path, audio_path, output_path):
    """Combine one scene image + narration audio into an individual MP4 scene clip."""
    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-framerate",
        "30",
        "-i",
        str(image_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        (
            "scale=1920:1080:"
            "force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
            "setsar=1,format=yuv420p"
        ),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    run_command(command)


def create_srt(scenes, durations, output_path):
    """Generate an SRT subtitle file from scene narration texts and audio durations."""

    def timestamp(seconds):
        milliseconds = round(seconds * 1000)
        hours, milliseconds = divmod(milliseconds, 3_600_000)
        minutes, milliseconds = divmod(milliseconds, 60_000)
        seconds, milliseconds = divmod(milliseconds, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    current_time = 0.0

    with open(output_path, "w", encoding="utf-8") as file:
        for index, (scene, duration) in enumerate(zip(scenes, durations), start=1):
            start = current_time
            end = current_time + duration
            text = scene.get("text") or scene.get("narration", "")

            file.write(
                f"{index}\n"
                f"{timestamp(start)} --> {timestamp(end)}\n"
                f"{text}\n\n"
            )
            current_time = end


# ==============================================================================
# Step 7 — Sample Scene Image Cards (Pillow)
# ==============================================================================

def create_sample_scene_card(heading: str, subtitle: str, output_path: Path):
    """Create a sample 1920x1080 aesthetic card using Pillow."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1920, 1080), "#14243A")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (120, 260, 1800, 820),
        radius=40,
        fill="#203D5C",
        outline="#7DB5FF",
        width=4,
    )

    clean_heading = heading.strip().upper()[:28]
    clean_subtitle = subtitle.strip()[:65]

    try:
        draw.text((200, 410), clean_heading, fill="white", font_size=100)
        draw.text((205, 570), clean_subtitle, fill="#B9D7FF", font_size=52)
    except Exception:
        draw.text((200, 410), clean_heading, fill="white")
        draw.text((205, 570), clean_subtitle, fill="#B9D7FF")

    image.save(output_path)
    return str(output_path)


def create_sample_scene_images(output_dir: Path = SCENES) -> List[str]:
    """Generate default sample scene images (scene_01.png, scene_02.png, scene_03.png)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    scenes_data = [
        ("CYBERSECURITY", "Protect your digital world"),
        ("STRONG PASSWORDS", "Secure every account"),
        ("STAY ALERT", "Recognize suspicious links"),
    ]

    created = []
    for index, (heading, subtitle) in enumerate(scenes_data, start=1):
        target = output_dir / f"scene_{index:02}.png"
        create_sample_scene_card(heading, subtitle, target)
        created.append(str(target))
    return created


# ==============================================================================
# Master generate_video() Function (Step 6)
# ==============================================================================

def generate_video(scenes: List[Dict[str, Any]], title: str = "SIH Video") -> str:
    """End-to-end video synthesis: TTS -> Scene clips -> Concat -> SRT Subtitles -> MP4."""
    clip_paths = []
    durations = []

    for index, scene in enumerate(scenes, start=1):
        image_path = SCENES / f"scene_{index:02}.png"
        audio_path = AUDIO / f"scene_{index:02}.mp3"
        clip_path = VIDEOS / f"clip_{index:02}.mp4"

        # If sample image does not exist yet, auto-generate aesthetic card
        if not image_path.exists():
            text = scene.get("text", f"Scene {index}")
            create_sample_scene_card(f"SCENE {index}", text, image_path)

        # Generate voice-over
        create_voice(scene["text"], audio_path.name)

        # Measure narration duration
        duration = get_duration(audio_path)
        durations.append(duration)

        # Image + narration -> scene video
        make_scene_clip(image_path, audio_path, clip_path)
        clip_paths.append(clip_path)

    # Create concat list
    concat_file = VIDEOS / "concat.txt"
    with open(concat_file, "w", encoding="utf-8") as file:
        for clip in clip_paths:
            absolute_path = clip.resolve()
            safe_path = str(absolute_path).replace("'", "'\\''")
            file.write(f"file '{safe_path}'\n")

    # Combine every scene
    silent_subtitle_video = VIDEOS / "combined.mp4"
    run_command([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(silent_subtitle_video),
    ])

    # Create subtitle file
    subtitle_file = VIDEOS / "subtitles.srt"
    create_srt(scenes, durations, subtitle_file)

    # Add subtitles as a selectable subtitle track (mov_text)
    final_video = VIDEOS / "final_video.mp4"

    try:
        run_command([
            "ffmpeg",
            "-y",
            "-i",
            str(silent_subtitle_video),
            "-i",
            str(subtitle_file),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-map",
            "1:0",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata",
            f"title={title}",
            "-movflags",
            "+faststart",
            str(final_video),
        ])
    except subprocess.CalledProcessError:
        # Fallback if container/ffmpeg build omits mov_text muxing
        run_command([
            "ffmpeg",
            "-y",
            "-i",
            str(silent_subtitle_video),
            "-c",
            "copy",
            "-metadata",
            f"title={title}",
            "-movflags",
            "+faststart",
            str(final_video),
        ])

    return str(final_video.resolve())


# Backward-compatible function aliases
render_scene_video = make_scene_clip
concatenate_videos = lambda clips, out: generate_video([{"text": ""} for _ in clips])


def generate_scene_images(scenes, output_dir=SCENES, **kwargs):
    """Generate sample scene images for the given scenes."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for index, sc in enumerate(scenes, 1):
        target = output_dir / f"scene_{index:02}.png"
        heading = f"SCENE {index}"
        subtitle = sc.get("visual_prompt") or sc.get("text") or "Factual Scene"
        create_sample_scene_card(heading, subtitle, target)
        created.append(str(target))
    return created


# ==============================================================================
# Step 3 — Qwen3 Script Generator with Fact Validation
# ==============================================================================

def validate_script_against_source(script: Dict[str, Any], source_text: str) -> Tuple[bool, List[str]]:
    """Validate that script claims, entities, and statistics are grounded in source document."""
    issues = []
    source_lower = source_text.lower()
    source_words = set(re.findall(r"\b\w{4,}\b", source_lower))

    scenes = script.get("scenes", [])
    if not scenes:
        return False, ["Script contains no scenes."]

    # Check for hallucinated numbers/statistics
    source_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", source_text))

    for i, scene in enumerate(scenes, 1):
        text = scene.get("text", "")
        scene_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
        unsupported_nums = scene_numbers - source_numbers
        if unsupported_nums:
            issues.append(
                f"Scene {i} introduces unverified statistics/numbers: {', '.join(unsupported_nums)}"
            )

        words = set(re.findall(r"\b\w{4,}\b", text.lower()))
        if source_words and words:
            overlap = words.intersection(source_words)
            ratio = len(overlap) / max(1, len(words))
            if ratio < 0.12:
                issues.append(
                    f"Scene {i} may deviate from source document (factual overlap: {ratio:.0%})"
                )

    return len(issues) == 0, issues


def generate_video_script(
    source_content: str,
    scene_count: int = 3,
    enforce_fact_validation: bool = True,
) -> Dict[str, Any]:
    """Generate structured video script using Qwen3 via Ollama with factual grounding."""
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    qwen_model = os.getenv("OLLAMA_MODEL", "qwen3:4b")

    prompt = (
        "You are an expert educational video storyboard producer. "
        "Convert the following source document into a structured video script.\n\n"
        f"SOURCE DOCUMENT:\n{source_content.strip()}\n\n"
        f"TARGET SCENE COUNT: {scene_count}\n\n"
        "RULES:\n"
        "1. Every scene must be grounded in facts from the source document.\n"
        "2. Do not introduce unsupported claims, outside technologies, or hallucinated numbers.\n"
        "3. 'text': The spoken narration voice-over.\n"
        "4. 'visual_prompt': The visual description for the image generation model.\n\n"
        "Return ONLY a valid JSON object matching:\n"
        "{\n"
        '  "title": "Short title",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "text": "Spoken narration for scene 1",\n'
        '      "visual_prompt": "A professional visual description of scene 1"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )

    script_data = None
    try:
        import requests

        res = requests.post(
            ollama_url,
            json={
                "model": qwen_model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.2, "num_predict": 1024},
            },
            timeout=(3.0, 45.0),
        )
        if res.status_code == 200:
            raw = res.json().get("response", "")
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw.strip(), flags=re.IGNORECASE)
            match = re.search(r"(\{.*\})", raw, flags=re.DOTALL)
            if match:
                parsed = json.loads(match.group(1))
                if "scenes" in parsed and len(parsed["scenes"]) > 0:
                    script_data = parsed
    except Exception:
        pass

    # Deterministic factual fallback if Qwen is offline
    if not script_data:
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", source_content)
            if len(s.strip()) > 15
        ]
        if not sentences:
            sentences = [source_content.strip() or "Introduction to the topic."]

        step = max(1, len(sentences) // scene_count)
        chosen = sentences[::step][:scene_count]
        scenes = []
        for s in chosen:
            clean = s.rstrip(".!?")
            scenes.append({
                "text": f"{clean}.",
                "visual_prompt": f"A clean, photorealistic visual representing {clean.lower()[:70]}",
            })
        title = sentences[0][:50].rstrip(" ,;.")
        script_data = {"title": title, "scenes": scenes}

    if enforce_fact_validation:
        is_valid, issues = validate_script_against_source(script_data, source_content)
        script_data["fact_validation"] = {
            "is_grounded": is_valid,
            "issues": issues,
        }

    return script_data


# Backward-compatible VideoGenerator class
class VideoGenerator:
    """Wrapper class integrating script generation and video synthesis."""

    def __init__(self, orientation: str = "landscape", output_dir: Path | str = BASE):
        self.orientation = orientation
        self.output_dir = Path(output_dir)

    async def generate_video_from_text(
        self,
        source_text: str,
        scene_count: int = 3,
        voice: str = "en-US-AriaNeural",
        use_forge: bool = True,
    ) -> Dict[str, Any]:
        script = generate_video_script(source_text, scene_count=scene_count)
        scenes = script["scenes"]
        output = generate_video(scenes, title=script.get("title", "Generated Video"))
        duration = sum(get_duration(AUDIO / f"scene_{i:02}.mp3") for i in range(1, len(scenes) + 1))
        return {
            "title": script.get("title", "Generated Video"),
            "video_path": output,
            "duration": round(duration, 2),
            "scene_count": len(scenes),
            "scenes": scenes,
            "fact_validation": script.get("fact_validation", {}),
        }


# ==============================================================================
# CLI Entrypoint for Direct Testing (Step 6)
# ==============================================================================

if __name__ == "__main__":
    demo_scenes = [
        {"text": "Welcome to our cybersecurity awareness video."},
        {
            "text": (
                "Protect your accounts with strong passwords "
                "and multi-factor authentication."
            )
        },
        {
            "text": (
                "Stay alert, identify suspicious links, "
                "and protect confidential information."
            )
        },
    ]

    output = generate_video(
        demo_scenes,
        title="SIH 26154 Content Transformation",
    )

    print("Video generated successfully:", output)
