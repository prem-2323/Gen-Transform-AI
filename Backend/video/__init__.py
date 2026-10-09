"""Video generation and multimodal synthesis package."""
from .tts_generator import generate_narration_audio, generate_scene_audio_files
from .video_generator import (
    VideoGenerator,
    generate_video_script,
    generate_scene_images,
    render_scene_video,
    concatenate_videos,
)

__all__ = [
    "VideoGenerator",
    "generate_video_script",
    "generate_scene_images",
    "render_scene_video",
    "concatenate_videos",
    "generate_narration_audio",
    "generate_scene_audio_files",
]
