"""
video/tts_generator.py
~~~~~~~~~~~~~~~~~~~~~~
Narration audio generation using Edge TTS for each video scene.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

AUDIO_DIR = Path("generated/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Minimal valid MP3 frame header for emergency offline fallback
_MINIMAL_MP3_BYTES = (
    b"\xff\xfb\x90d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    * 50
)


async def generate_voice(text: str, output_path: str):
    """Generate audio MP3 file from text using edge-tts with resilient fallbacks."""
    clean_text = (text or "").strip()
    if not clean_text:
        clean_text = "Scene narration."

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        import edge_tts

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice="en-US-AriaNeural",
            rate="+0%",
            volume="+0%",
        )
        await communicate.save(str(target))
        if target.exists() and target.stat().st_size > 0:
            return
    except Exception:
        pass

    # Secondary: local pyttsx3 or backend audio service fallback
    try:
        from text.tts import generate_audio as text_generate_audio

        await text_generate_audio(
            text=clean_text,
            output_file=str(target),
            voice="en-US-AriaNeural",
        )
        if target.exists() and target.stat().st_size > 0:
            return
    except Exception:
        pass

    # Tertiary: minimal silent fallback
    if not target.exists() or target.stat().st_size == 0:
        target.write_bytes(_MINIMAL_MP3_BYTES)


def create_voice(text: str, filename: str) -> str:
    """Generate voice audio and save into AUDIO_DIR/filename."""
    target_path = Path(filename)
    if not target_path.is_absolute() and target_path.parent == Path("."):
        output_path = AUDIO_DIR / filename
    else:
        output_path = target_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        asyncio.run(generate_voice(text, str(output_path)))
    except RuntimeError:
        # If an event loop is already active in the current thread (e.g. inside FastAPI)
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio

            nest_asyncio.apply()
        loop.run_until_complete(generate_voice(text, str(output_path)))

    return str(output_path)


async def generate_scene_audio_files(scenes, output_dir=AUDIO_DIR, prefix="scene"):
    """Generate audio files for a list of scene dictionaries."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, sc in enumerate(scenes, 1):
        txt = sc.get("text") or sc.get("narration") or f"Scene {i}."
        fpath = out_dir / f"{prefix}_{i:02d}.mp3"
        await generate_voice(txt, str(fpath))
        paths.append(str(fpath))
    return paths


# Aliases for backward compatibility
generate_narration_audio = generate_voice
