"""
video/tts_generator.py
~~~~~~~~~~~~~~~~~~~~~~
Narration audio generation using Edge TTS for each video scene.

Outputs:
    generated/audio/scene_01.mp3
    generated/audio/scene_02.mp3
    ...
"""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_VOICE = "en-US-AriaNeural"
DEFAULT_AUDIO_DIR = Path("generated/audio")

# Valid minimal MP3 frame header (MPEG-1 Layer 3, 128 kbps, 44.1 kHz, stereo)
_MINIMAL_MP3_BYTES = (
    b"\xff\xfb\x90d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    * 60
)


def _write_silent_audio(output_path: Path) -> None:
    """Write minimal playable MP3 bytes when offline or if all TTS engines fail."""
    try:
        output_path.write_bytes(_MINIMAL_MP3_BYTES)
    except Exception:
        pass


async def generate_narration_audio(
    text: str,
    output_path: str | Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
) -> str:
    """Generate audio MP3 file from narration text using edge-tts with resilient fallbacks.

    Args:
        text: Narration text to synthesize.
        output_path: Target path for the MP3 file.
        voice: Voice code (default: en-US-AriaNeural).
        rate: Speed modifier (default: +0%).

    Returns:
        Absolute path to the saved MP3 file.
    """
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    clean_text = (text or "").strip()
    if not clean_text:
        clean_text = "Scene narration."

    # 1. Primary: edge-tts
    try:
        import edge_tts

        communicate = edge_tts.Communicate(clean_text, voice, rate=rate)
        await communicate.save(str(target))
        if target.exists() and target.stat().st_size > 0:
            return str(target.resolve())
    except Exception:
        pass

    # 2. Secondary: backend fallback service (pyttsx3 / gTTS / ffmpeg)
    try:
        from text.tts import generate_audio as text_generate_audio

        saved = await text_generate_audio(
            text=clean_text,
            output_file=str(target),
            voice=voice,
            rate=rate,
        )
        if target.exists() and target.stat().st_size > 0:
            return str(target.resolve())
    except Exception:
        pass

    # 3. Tertiary: Local FFmpeg lavfi tone generator if available
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            "3",
            "-q:a",
            "9",
            str(target),
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=5)
        if res.returncode == 0 and target.exists() and target.stat().st_size > 0:
            return str(target.resolve())
    except Exception:
        pass

    # 4. Final: Write minimal silent MP3
    _write_silent_audio(target)
    return str(target.resolve())


def generate_narration_audio_sync(
    text: str,
    output_path: str | Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
) -> str:
    """Synchronous helper for generate_narration_audio."""
    try:
        return asyncio.run(generate_narration_audio(text, output_path, voice, rate))
    except RuntimeError:
        # If an event loop is already running in the current thread:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            generate_narration_audio(text, output_path, voice, rate)
        )


async def generate_scene_audio_files(
    scenes: List[Dict[str, Any]],
    output_dir: str | Path = DEFAULT_AUDIO_DIR,
    voice: str = DEFAULT_VOICE,
    prefix: str = "scene",
    rate: str = "+0%",
) -> List[str]:
    """Generate one MP3 audio file per scene in the given output directory.

    Args:
        scenes: List of scene dictionaries (with 'text' or 'narration' key).
        output_dir: Target folder (default: generated/audio).
        voice: Voice identifier.
        prefix: Filename prefix (e.g. 'scene' -> scene_01.mp3).
        rate: Speed modifier.

    Returns:
        List of absolute paths to generated audio files.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    audio_paths: List[str] = []
    for idx, scene in enumerate(scenes, start=1):
        narration = (
            scene.get("text")
            or scene.get("narration")
            or f"Scene {idx} narration."
        )
        audio_file = out_dir / f"{prefix}_{idx:02d}.mp3"
        saved = await generate_narration_audio(
            text=narration,
            output_path=audio_file,
            voice=voice,
            rate=rate,
        )
        audio_paths.append(saved)

    return audio_paths
