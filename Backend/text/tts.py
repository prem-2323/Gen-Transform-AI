"""text/tts.py — narration audio generation for the video pipeline.

Wraps the existing backend TTS service (``app.services.audio.tts_service``) so
``video/tts.py`` gets Edge-TTS narration with local SAPI/gTTS/silent fallback
when the neural voice is unreachable.
"""

from __future__ import annotations

import os

from app.services.audio.tts_service import generate_audio as _backend_generate_audio


async def generate_audio(
    text: str,
    output_file: str,
    voice: str = "en-US-AriaNeural",
    rate: str = "+0%",
) -> str:
    """Generate narration MP3 at ``output_file`` and return the path.

    Never raises for TTS failure — falls back to local engines, and finally to
    a minimal valid silent MP3, so the video pipeline can always complete.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    return await _backend_generate_audio(text=text, output_file=output_file, voice=voice, rate=rate)

