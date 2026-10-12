#!/usr/bin/env python3
"""Generate GreenTech Solutions (2025) video WITHOUT requiring SD Forge.

Pipeline (Forge-free by design):
  1. Script: Qwen2.5:3b via Ollama (deterministic fallback if offline).
  2. Scene images: Pillow cinematic cards (no diffusion needed).
  3. Voice-over: Edge TTS (offline fallbacks chain in tts_generator).
  4. Assembly: bin/ffmpeg + ffprobe (project bin/ added to PATH).

Output: output/GreenTech-2025/ (report, scenes, audio, subtitles, video, ai_logs).
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
_bin = PROJECT_ROOT / "bin"
if _bin.is_dir() and str(_bin) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_bin}{os.pathsep}{os.environ.get('PATH', '')}"

os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:3b")
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

OUTPUT_DIR = PROJECT_ROOT / "output" / "GreenTech-2025"
for d in ["report", "scenes", "audio", "video", "subtitles", "ai_logs"]:
    (OUTPUT_DIR / d).mkdir(parents=True, exist_ok=True)

SOURCE_TEXT = """In 2025, a fictional technology company called GreenTech Solutions launched a renewable energy
initiative to reduce electricity consumption across its offices. The company installed 120 solar panels
across three buildings and introduced an energy monitoring system to track daily usage. During the first
six months, electricity consumption decreased from 50,000 kWh to 38,000 kWh per month, representing a 24%
reduction. The project cost Rs. 18 lakh, and the company estimates that it could recover the investment
within four years if the current savings continue. However, the results may vary depending on weather
conditions, maintenance costs, and future electricity prices. The company plans to expand the initiative
to two additional buildings in 2027, subject to budget approval and an evaluation of the pilot results.
Management recommends monitoring energy consumption monthly, publishing quarterly progress reports, and
comparing actual savings against the original targets before approving further expansion. All figures in
this example are fictional and are provided solely for testing document summarization, factual consistency,
and multi-format content transformation."""

print("=" * 72)
print("  GreenTech Solutions (2025) — Forge-free Video Pipeline")
print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 72)

# ── STEP 1: script (Qwen, deterministic fallback) ──────────────────────────
print("\n[STEP 1/5] Generating 6-scene script (Qwen2.5:3b, fallback-safe) ...")
from video.video_generator import generate_video_script

script_data = generate_video_script(SOURCE_TEXT, scene_count=6)
scenes = script_data.get("scenes", [])
print(f"  Title: {script_data.get('title', 'N/A')}")
print(f"  Scenes: {len(scenes)}")
fv = script_data.get("fact_validation", {})
print(f"  Grounded: {fv.get('is_grounded')} issues={fv.get('issues', [])}")
(OUTPUT_DIR / "ai_logs" / "video_script.json").write_text(
    json.dumps(script_data, indent=2, ensure_ascii=False), encoding="utf-8"
)

# ── STEP 2: Pillow scene cards (Forge-free) ────────────────────────────────
print("\n[STEP 2/5] Rendering Pillow scene cards ...")
from PIL import Image, ImageDraw

GEN_SCENES = BACKEND_DIR / "generated" / "scenes"
GEN_SCENES.mkdir(parents=True, exist_ok=True)

HEADINGS = [
    "GREENTECH 2025",
    "SOLAR ROLLOUT",
    "ENERGY SAVINGS",
    "COST & PAYBACK",
    "EXPANSION PLAN",
    "RECOMMENDATIONS",
]
SUBTITLES = [
    "Renewable Energy Initiative",
    "120 Panels - 3 Buildings",
    "50,000 to 38,000 kWh (-24%)",
    "Rs.18 Lakh - 4-Year Payback",
    "2 More Buildings in 2027",
    "Monitor, Report, Compare",
]
COLORS = [
    ("#0F2A1D", "#22C55E", "#86EFAC"),
    ("#0C1E35", "#F59E0B", "#06B6D4"),
    ("#1A0A2E", "#E11D48", "#8B5CF6"),
    ("#1C1917", "#EF4444", "#22C55E"),
    ("#0F172A", "#6366F1", "#14B8A6"),
    ("#18181B", "#F97316", "#3B82F6"),
]

for idx, scene in enumerate(scenes):
    n = idx + 1
    bg, a1, a2 = COLORS[idx % len(COLORS)]
    heading = HEADINGS[idx] if idx < len(HEADINGS) else f"SCENE {n}"
    subtitle = SUBTITLES[idx] if idx < len(SUBTITLES) else (scene.get("text", "")[:55])

    img = Image.new("RGB", (1920, 1080), bg)
    draw = ImageDraw.Draw(img)
    for x in range(0, 1920, 80):
        draw.line([(x, 0), (x, 1080)], fill="#1A2744", width=1)
    for y in range(0, 1080, 80):
        draw.line([(0, y), (1920, y)], fill="#1A2744", width=1)
    draw.rectangle([(30, 30), (1890, 1050)], outline=a1, width=3)
    draw.rounded_rectangle((120, 280, 1800, 800), radius=30, fill="#1E293B", outline=a2, width=3)
    draw.rectangle([(140, 100), (420, 150)], fill="#14532D", outline=a1, width=2)
    draw.text((160, 110), f"SCENE {n:02d} / {len(scenes):02d}", fill="#BBF7D0", font_size=28)
    draw.text((460, 110), "GREENTECH-2025", fill="#94A3B8", font_size=28)
    draw.rectangle([(1500, 100), (1780, 150)], fill="#1E3A5F", outline=a2, width=2)
    draw.text((1520, 110), "Qwen2.5 + TTS", fill="#93C5FD", font_size=22)
    draw.text((200, 400), heading, fill="white", font_size=72)
    draw.text((200, 540), subtitle[:55], fill="#BBF7D0", font_size=44)
    vp = scene.get("visual_prompt", "")[:90]
    if vp:
        draw.text((200, 640), f"Visual: {vp}...", fill="#64748B", font_size=20)
    draw.text((200, 720), "GreenTech Solutions - Renewable Energy Initiative (fictional test data)", fill="#64748B", font_size=24)

    out_gen = GEN_SCENES / f"scene_{n:02}.png"
    out_pub = OUTPUT_DIR / "scenes" / f"scene_{n:02}.png"
    img.save(out_gen)
    img.save(out_pub)
    print(f"  Scene {n:02d}: {heading} — {subtitle}")

# ── STEP 3: voice-over ─────────────────────────────────────────────────────
print("\n[STEP 3/5] Generating narration (Edge TTS + fallbacks) ...")
from video.tts_generator import create_voice

GEN_AUDIO = BACKEND_DIR / "generated" / "audio"
GEN_AUDIO.mkdir(parents=True, exist_ok=True)
for i, scene in enumerate(scenes, 1):
    create_voice(scene.get("text", f"Scene {i}"), f"scene_{i:02}.mp3")
    src = GEN_AUDIO / f"scene_{i:02}.mp3"
    dst = OUTPUT_DIR / "audio" / f"scene_{i:02}.mp3"
    if src.exists():
        shutil.copy2(src, dst)
        print(f"  Scene {i:02d}: scene_{i:02d}.mp3 ({src.stat().st_size // 1024} KB)")

# ── STEP 4: assemble ───────────────────────────────────────────────────────
print("\n[STEP 4/5] Assembling MP4 with FFmpeg ...")
from video.video_generator import generate_video

final_local = generate_video(scenes, title=script_data.get("title", "GreenTech 2025"))
print(f"  Local video: {final_local}")
shutil.copy2(final_local, OUTPUT_DIR / "video" / "final_video.mp4")
for name in ["subtitles.srt"]:
    src = BACKEND_DIR / "generated" / "videos" / name
    if src.exists():
        shutil.copy2(src, OUTPUT_DIR / "subtitles" / name)

# ── STEP 5: verify ─────────────────────────────────────────────────────────
print("\n[STEP 5/5] Verifying with ffprobe ...")
final_video = OUTPUT_DIR / "video" / "final_video.mp4"
res = subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(final_video)],
    capture_output=True, text=True,
)
probe = json.loads(res.stdout)
fmt = probe.get("format", {})
print(f"  Duration: {float(fmt.get('duration', 0)):.1f}s")
print(f"  Size: {int(fmt.get('size', 0)) / 1024 / 1024:.2f} MB")
for s in probe.get("streams", []):
    if s.get("codec_type") == "video":
        print(f"  Video: {s.get('codec_name')} {s.get('width')}x{s.get('height')}")
    elif s.get("codec_type") == "audio":
        print(f"  Audio: {s.get('codec_name')} {s.get('sample_rate')}Hz")
    elif s.get("codec_type") == "subtitle":
        print(f"  Subtitles: {s.get('codec_name')}")

report = [
    "GREENTECH SOLUTIONS (2025) — VIDEO BUILD REPORT (fictional test data)",
    f"Built: {datetime.now().isoformat()}",
    f"Title: {script_data.get('title')}",
    f"Scenes: {len(scenes)} | Duration: {float(fmt.get('duration', 0)):.1f}s",
    f"Script model: Qwen2.5:3b (fallback-safe) | Images: Pillow (Forge-free) | Audio: Edge TTS",
    "",
    "SCENES:",
]
for i, sc in enumerate(scenes, 1):
    report.append(f"  {i}. {sc.get('text', '')[:120]}")
(OUTPUT_DIR / "report" / "greentech_video_report.txt").write_text("\n".join(report), encoding="utf-8")

print("\n" + "=" * 72)
print("  VIDEO COMPLETE (Forge-free)")
print(f"  Video:     {OUTPUT_DIR / 'video' / 'final_video.mp4'}")
print(f"  Subtitles: {OUTPUT_DIR / 'subtitles' / 'subtitles.srt'}")
print(f"  Script:    {OUTPUT_DIR / 'ai_logs' / 'video_script.json'}")
print("=" * 72)
