"""
video/renderer.py
~~~~~~~~~~~~~~~~~
Step 9  - Determine scene duration from actual MP3 duration (via ffprobe).
Step 10 - Combine scene_XX.png + scene_XX.mp3 -> scene_XX.mp4  (via FFmpeg).
Step 11 - Generate a .srt subtitle file from scene narrations + durations.
Step 12 - Concatenate all scene MP4s into final_video.mp4.
Step 13 - Burn subtitles into the final video -> final_video_subtitled.mp4.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

# Ensure project bin directory is in PATH for ffmpeg and ffprobe
_project_bin = Path(__file__).resolve().parent.parent.parent / "bin"
if _project_bin.is_dir() and str(_project_bin) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_project_bin}{os.pathsep}{os.environ.get('PATH', '')}"



# -- Paths ----------------------------------------------------------------------

IMAGES_DIR = Path(os.getenv("IMAGE_STORAGE",  "generated_images"))
AUDIO_DIR  = Path(os.getenv("AUDIO_STORAGE",  "generated_audio"))
VIDEO_DIR  = Path(os.getenv("VIDEO_STORAGE",  "generated_videos"))

# Padding added after the narration ends (seconds) so the last frame
# doesn't cut off abruptly.
TAIL_PADDING = 0.5


# -- Step 9: Get real MP3 duration via ffprobe ----------------------------------

def get_audio_duration(audio_path: str) -> float:
    """Return the duration of an audio file in seconds using ffprobe.

    Args:
        audio_path: Absolute or relative path to an MP3 (or any audio) file.

    Returns:
        Duration in seconds (float), e.g. 7.234.

    Raises:
        RuntimeError: If ffprobe is missing or returns unexpected output.
        FileNotFoundError: If audio_path does not exist.
    """
    if not Path(audio_path).is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        audio_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffprobe not found. Make sure FFmpeg is installed and on PATH."
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ffprobe failed for {audio_path}:\n{exc.stderr}"
        ) from exc

    data = json.loads(result.stdout)
    streams = data.get("streams", [])

    for stream in streams:
        duration = stream.get("duration")
        if duration is not None:
            return float(duration)

    # Fallback: try top-level format duration
    fmt_duration = data.get("format", {}).get("duration")
    if fmt_duration:
        return float(fmt_duration)

    raise RuntimeError(f"Could not read duration from {audio_path}")


def get_scene_duration(audio_path: str, padding: float = TAIL_PADDING) -> float:
    """Return scene duration = MP3 duration + tail padding.

    Args:
        audio_path: Path to the scene's MP3 file.
        padding:    Extra seconds to hold the last frame after narration ends.

    Returns:
        Scene duration in seconds (rounded to 2 decimal places).
    """
    return round(get_audio_duration(audio_path) + padding, 2)


# -- Step 9b: Conform narration audio to the planned scene duration ----------

# Maximum natural-sounding time-stretch. Beyond this the voice sounds rushed,
# so the scene is extended instead and the overrun is reported.
MAX_TEMPO_FIT = 1.4


def fit_audio_to_duration(
    audio_path: str,
    target_duration: float,
    output_path: str | None = None,
    padding: float = TAIL_PADDING,
    max_tempo: float = MAX_TEMPO_FIT,
) -> tuple[str, float]:
    """Conform a scene narration MP3 to the planned scene duration.

    The planner budgets narration words per scene, but real TTS speech rates
    vary by voice/language, so audio routinely overruns short scenes and the
    final video drifts past the requested target duration. This fits the
    audio instead of stretching the video:

    - Audio shorter than plan: returned untouched (FFmpeg pads the tail with
      silence via apad during scene rendering).
    - Overrun within ``max_tempo`` (default 1.4x): time-stretched with the
      FFmpeg ``atempo`` filter to fit exactly; output stays MP3 so the
      existing ``/audio/{filename}`` endpoint keeps serving it.
    - Overrun beyond ``max_tempo``: returned untouched and the scene is
      extended (better a slightly longer video than chipmunk audio).

    Returns:
        (audio_path_to_use, scene_duration_seconds). The duration always
        includes tail padding.
    """
    try:
        raw_duration = get_audio_duration(audio_path)
    except (RuntimeError, FileNotFoundError):
        return audio_path, round(float(target_duration), 2)

    target_audio = max(0.5, float(target_duration) - padding)

    if raw_duration <= target_audio + 0.05:
        return audio_path, round(float(target_duration), 2)

    tempo = raw_duration / target_audio
    if tempo > max_tempo:
        return audio_path, round(raw_duration + padding, 2)

    if output_path is None:
        stem = Path(audio_path).stem
        output_path = str(Path(audio_path).parent / f"{stem}_fit.mp3")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel", "error",
        "-i", audio_path,
        "-filter:a", f"atempo={tempo:.4f}",
        "-c:a", "libmp3lame",
        "-q:a", "4",
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return audio_path, round(raw_duration + padding, 2)

    try:
        fitted_duration = get_audio_duration(output_path)
    except (RuntimeError, FileNotFoundError):
        return audio_path, round(raw_duration + padding, 2)

    if fitted_duration > float(target_duration):
        return audio_path, round(raw_duration + padding, 2)
    return output_path, round(float(target_duration), 2)


# -- Step 10: PNG + MP3 -> MP4 via FFmpeg ---------------------------------------

def render_scene_video(
    image_path: str,
    audio_path: str,
    output_path: str,
    duration: float | None = None,
    width: int = 512,
    height: int = 512,
) -> str:
    """Combine one scene image + one narration MP3 into a scene MP4.

    Uses:
        - libx264 (stillimage tune) for the video stream
        - aac for the audio stream with apad padding to sustain full planned duration
        - yuv420p pixel format for maximum player compatibility
        - Configured width x height resolution

    Args:
        image_path:  Path to the scene PNG file.
        audio_path:  Path to the scene MP3 file.
        output_path: Destination path for the output MP4 file.
        duration:    Target duration in seconds.
        width:       Target video width in pixels.
        height:      Target video height in pixels.

    Returns:
        The output_path on success.
    """
    if not Path(image_path).is_file():
        raise FileNotFoundError(f"Scene image not found: {image_path}")
    if not Path(audio_path).is_file():
        raise FileNotFoundError(f"Scene audio not found: {audio_path}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Determine duration from actual MP3 if not supplied
    audio_dur = get_scene_duration(audio_path)
    if duration is None or duration <= 0:
        duration = audio_dur
    else:
        # Never cut off narration if speech is longer than planned duration
        duration = max(float(duration), audio_dur)

    # Ensure width & height are even numbers (required by libx264)
    w = width if width % 2 == 0 else width + 1
    h = height if height % 2 == 0 else height + 1

    cmd = [
        "ffmpeg",
        "-y",                         # overwrite without asking
        "-loop", "1",                 # loop the still image
        "-t", str(duration),          # input 0 duration
        "-i", image_path,             # input 0: image
        "-i", audio_path,             # input 1: audio
        "-c:v", "libx264",
        "-tune", "stillimage",        # optimise encoder for still images
        "-af", "apad",                # pad audio with silence if narration is shorter than video duration
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", str(duration),          # exact total duration
        "-pix_fmt", "yuv420p",        # broad device compatibility
        "-movflags", "+faststart",    # web-optimised MP4
        "-vf", f"scale={w}:{h}",      # calibrated resolution
        output_path,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg not found. Make sure FFmpeg is installed and on PATH."
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"FFmpeg failed for scene {output_path}:\n{exc.stderr[-1000:]}"
        ) from exc

    return output_path


def render_all_scene_videos(
    image_paths: list[str],
    audio_paths: list[str],
    output_dir: str | None = None,
    prefix: str = "scene",
    durations: list[float] | None = None,
    width: int = 512,
    height: int = 512,
) -> list[str]:
    """Render one MP4 per scene and return ordered list of output paths.

    Args:
        image_paths: Ordered list of scene PNG paths (from service.py Step 7).
        audio_paths: Ordered list of scene MP3 paths (from service.py Step 8).
        output_dir:  Directory to write scene MP4s (defaults to VIDEO_DIR).
        prefix:      Filename prefix (e.g. "scene" -> scene_01.mp4).
        durations:   Planned durations for each scene in seconds.
        width:       Target video width.
        height:      Target video height.

    Returns:
        Ordered list of scene MP4 file paths.
    """
    if len(image_paths) != len(audio_paths):
        raise ValueError(
            f"Mismatch: {len(image_paths)} images vs {len(audio_paths)} audio files."
        )

    out_dir = Path(output_dir) if output_dir else VIDEO_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    scene_video_paths = []

    for i, (img, audio) in enumerate(zip(image_paths, audio_paths), start=1):
        target_dur = None
        if durations and i - 1 < len(durations):
            target_dur = durations[i - 1]

        output_path = str(out_dir / f"{prefix}_{i:02d}.mp4")
        render_scene_video(
            image_path=img,
            audio_path=audio,
            output_path=output_path,
            duration=target_dur,
            width=width,
            height=height,
        )
        scene_video_paths.append(output_path)

    return scene_video_paths


# -- Step 11: Generate SRT subtitle file ----------------------------------------

def _seconds_to_srt_timestamp(seconds: float) -> str:
    """Convert a float seconds value to SRT timestamp format HH:MM:SS,mmm."""
    hours   = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs    = int(seconds % 60)
    millis  = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(
    scenes: list,
    audio_paths: list[str],
    output_path: str | None = None,
    durations: list[float] | None = None,
) -> str:
    """Build an SRT subtitle file driven by actual scene durations and audio timings.

    Each subtitle block is synchronized to the scene timeline.

    Args:
        scenes:      Ordered list of scene dicts (must have 'narration' key).
        audio_paths: Ordered list of MP3 paths matching the scenes.
        output_path: Where to write the .srt file.
        durations:   Optional explicit scene durations in seconds.

    Returns:
        The output path of the written .srt file.
    """
    if output_path is None:
        subs_dir = Path("subtitles")
        subs_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(subs_dir / "video.srt")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    blocks = []
    cursor = 0.0  # running timecode in seconds

    for i, (scene, audio) in enumerate(zip(scenes, audio_paths), start=1):
        audio_dur = get_scene_duration(audio)
        if durations and i - 1 < len(durations):
            duration = max(float(durations[i - 1]), audio_dur)
        else:
            duration = audio_dur

        start_time = _seconds_to_srt_timestamp(cursor)
        end_time   = _seconds_to_srt_timestamp(cursor + duration)
        narration  = scene.get("narration", "").strip() or f"Scene {i}."

        blocks.append(
            f"{i}\n"
            f"{start_time} --> {end_time}\n"
            f"{narration}\n"
        )
        cursor += duration

    srt_content = "\n".join(blocks)
    Path(output_path).write_text(srt_content, encoding="utf-8")
    return output_path


# -- Step 12: Concatenate scene MP4s -> final_video.mp4 --------------------------

def concatenate_scene_videos(
    scene_video_paths: list[str],
    output_path: str | None = None,
) -> str:
    """Join all scene MP4s into one final video using FFmpeg concat demuxer.

    Args:
        scene_video_paths: Ordered list of scene MP4 paths.
        output_path:       Destination for the final concatenated MP4.

    Returns:
        The output_path on success.
    """
    if output_path is None:
        VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(VIDEO_DIR / "final_video.mp4")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Write a temporary concat list file
    concat_list_path = Path(output_path).parent / f"_concat_list_{Path(output_path).stem}.txt"
    lines = [f"file '{Path(p).resolve().as_posix()}'" for p in scene_video_paths]
    concat_list_path.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c", "copy",               # stream copy - no re-encoding, fast
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Ensure FFmpeg is installed and on PATH.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"FFmpeg concat failed:\n{exc.stderr[-1000:]}"
        ) from exc
    finally:
        concat_list_path.unlink(missing_ok=True)  # clean up temp file

    return output_path


# -- Step 13: Burn subtitles into final video -----------------------------------

def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str | None = None,
    font_size: int = 22,
) -> str:
    """Hard-burn SRT subtitles into the video using FFmpeg subtitles filter.

    The subtitles are rendered with a legible style:
        - White text with a semi-transparent black outline
        - Positioned at the bottom-centre
        - Dynamically sized font based on video resolution

    Args:
        video_path:  Path to the raw final_video.mp4.
        srt_path:    Path to the .srt subtitle file.
        output_path: Destination for the subtitled MP4.
        font_size:   Subtitle font size in points.

    Returns:
        The output_path on success.
    """
    if not Path(video_path).is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not Path(srt_path).is_file():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    if output_path is None:
        VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(VIDEO_DIR / "final_video_subtitled.mp4")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # FFmpeg subtitles filter requires forward slashes and escaped colons on Windows
    srt_escaped = Path(srt_path).resolve().as_posix().replace(":", "\\\\:")

    subtitle_style = (
        "FontName=Arial,"
        f"FontSize={font_size},"
        "PrimaryColour=&H00FFFFFF,"   # white text
        "OutlineColour=&H80000000,"   # semi-transparent black outline
        "BorderStyle=3,"
        "Outline=1.5,"
        "Shadow=0,"
        "Alignment=2"                 # bottom-centre
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", f"subtitles='{srt_escaped}':force_style='{subtitle_style}'",
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "fast",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Ensure FFmpeg is installed and on PATH.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"FFmpeg subtitle burn failed:\n{exc.stderr[-1000:]}"
        ) from exc

    return output_path
