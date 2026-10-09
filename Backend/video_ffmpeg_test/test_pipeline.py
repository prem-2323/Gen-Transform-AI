import os
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw

bin_dir = Path(__file__).resolve().parent.parent.parent / "bin"
if bin_dir.is_dir() and str(bin_dir) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"

out = Path("output")
out.mkdir(exist_ok=True)

# 1. Create a sample image
img = Image.new("RGB", (1280, 720), "#183153")
draw = ImageDraw.Draw(img)
draw.text((100, 250), "SIH 26154", fill="white")
draw.text((100, 320), "FFmpeg Video Pipeline Test", fill="white")
img.save(out / "scene.png")

# 2. Create a 5-second video with test audio
cmd = [
    "ffmpeg", "-y",
    "-loop", "1",
    "-framerate", "25",
    "-i", str(out / "scene.png"),
    "-f", "lavfi",
    "-i", "sine=frequency=440:duration=5",
    "-t", "5",
    "-vf", "format=yuv420p",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-c:a", "aac",
    "-shortest",
    str(out / "test_video.mp4"),
]

subprocess.run(cmd, check=True)

# 3. Verify the MP4
subprocess.run([
    "ffprobe", "-v", "error",
    "-show_entries", "format=duration",
    "-show_entries", "stream=codec_name,width,height",
    "-of", "json",
    str(out / "test_video.mp4"),
], check=True)

print("SUCCESS: Test video created at output/test_video.mp4")

