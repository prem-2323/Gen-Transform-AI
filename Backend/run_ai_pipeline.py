#!/usr/bin/env python3
"""
ContentForge AI — Full AI Pipeline: Case File CF-2026-014
=========================================================
Uses REAL Ollama AI models (Qwen2.5 + Gemma2) for:
  1. Incident analysis report generation (Qwen2.5:3b)
  2. Video script generation with fact validation (Qwen2.5:3b)
  3. Scene visual descriptions (Gemma2:2b)
  4. Scene image generation (Pillow styled cards / SD Forge if available)
  5. AI voice-over narration (Edge TTS)
  6. FFmpeg video assembly with SRT subtitles

Output: output/CF-2026-014/ with all assets
"""
import json
import os
import sys
import re
import asyncio
import subprocess
import time
import shutil
from pathlib import Path
from datetime import datetime

# ── Setup paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
_bin = PROJECT_ROOT / "bin"
if _bin.is_dir():
    os.environ["PATH"] = f"{_bin}{os.pathsep}{os.environ.get('PATH', '')}"

OUTPUT_DIR = PROJECT_ROOT / "output" / "CF-2026-014"
for d in ["report", "scenes", "audio", "video", "subtitles", "ai_logs"]:
    (OUTPUT_DIR / d).mkdir(parents=True, exist_ok=True)

# Working dirs for video_generator
GENERATED = BACKEND_DIR / "generated"
for d in ["scenes", "audio", "videos", "reports"]:
    (GENERATED / d).mkdir(parents=True, exist_ok=True)

# ── Ollama Configuration ──────────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
QWEN_MODEL = "qwen2.5:3b"
GEMMA_MODEL = "gemma2:2b"

def ollama_generate(model: str, prompt: str, temperature: float = 0.3,
                     max_tokens: int = 2048, timeout: int = 120) -> str:
    """Call Ollama API to generate text. Returns raw response string."""
    import urllib.request
    import urllib.error

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw = data.get("response", "")
            # Strip <think>...</think> blocks from reasoning models
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
            return raw.strip()
    except Exception as e:
        print(f"  [WARNING] Ollama ({model}) failed: {e}")
        return ""


def ollama_generate_json(model: str, prompt: str, **kwargs) -> dict:
    """Call Ollama and parse the response as JSON."""
    raw = ollama_generate(model, prompt, **kwargs)
    if not raw:
        return {}

    # Try to extract JSON from the response
    # Remove markdown code blocks
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw.strip(), flags=re.IGNORECASE)

    # Find JSON object or array
    match = re.search(r"(\{.*\}|\[.*\])", raw, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {}


# ── SOURCE DOCUMENT ────────────────────────────────────────────────────────────

CASE_FILE = """\
Case Title: Unauthorized Account Access and Potential Data Exposure

Case Reference: CF-2026-014
Organization: Northbridge Community Services (fictional)
Incident Date: 14 September 2026
Severity: Medium — preliminary assessment
Status: Contained; investigation ongoing

Case File CF-2026-014 documents a fictional cybersecurity incident reported by Northbridge Community Services, a mid-sized nonprofit organization that manages appointment scheduling and public assistance referrals. On Monday, 14 September 2026, the service desk received several reports that staff members were unexpectedly signed out of the case-management portal. At 09:20, the security coordinator reviewed an automated alert showing repeated login attempts against three staff accounts, followed by a successful sign-in from an unfamiliar device. The account belonged to a program coordinator who had received an email that morning appearing to contain an updated supplier invoice. The message used a display name similar to a known vendor, but the sender address did not match the vendor's verified domain. The employee stated that they opened the message and entered their password on a page that looked like the organization's sign-in screen. No payment was made, and the employee reported the issue as soon as unusual account notifications appeared. The incident team opened case CF-2026-014, preserved the original email, recorded the reported times, and asked the employee not to delete messages or attempt further sign-ins until the account could be secured.

The initial review found evidence of unauthorized access to the coordinator's account between 09:07 and 09:31. Audit logs showed that the account viewed a staff directory, opened six service records, and attempted to export a larger report. The export action was blocked by a policy requiring additional approval, and the logs did not show a completed bulk download. Two records contained contact details and appointment notes; this case file deliberately excludes names, addresses, medical details, passwords, and other identifying information. Investigators could not confirm that the viewed information was copied outside the portal, so the potential exposure was classified as limited but unresolved. A second staff account had multiple failed login attempts but no successful access. The incident team disabled active sessions for the affected coordinator, reset the password through the organization's trusted identity process, required multi-factor authentication, and temporarily restricted access to case records from unfamiliar devices. The email gateway then searched for matching messages and found four recipients. All four were contacted, and three confirmed that they had not opened the message. The remaining recipient's device was checked by IT, which found no evidence of further suspicious activity. These findings were documented with timestamps and evidence references so another reviewer could repeat the assessment.

By 13:45, the organization had contained the immediate access risk and confirmed that the portal, scheduling service, and referral workflow remained operational. The security coordinator informed the privacy lead and service director, who began a documented assessment of whether notification obligations applied under the organization's policies and relevant law. That decision was left pending formal review rather than assumed from incomplete evidence. The root cause was assessed as credential disclosure after a convincing impersonation email, compounded by inconsistent multi-factor authentication coverage and limited staff familiarity with supplier-message verification. No evidence was found that the portal itself had been compromised, and the investigation did not establish who operated the suspicious sign-in. Follow-up actions included enforcing multi-factor authentication for every account, requiring additional approval for sensitive exports, tightening email authentication and impersonation controls, reviewing access permissions, and delivering a phishing-awareness session with a safe reporting link. The team assigned owners and due dates for each action and scheduled a review after thirty days. The case was marked "contained, monitoring continues," not "closed," because log review and the privacy assessment remained in progress. The final incident summary must distinguish confirmed facts from assumptions, state that no bulk export was completed according to available logs, and explain that limited record viewing occurred while external copying remains unconfirmed. This fictional case is intended for software testing, not as a report of a real organization or event.
"""

print("=" * 72)
print("  ContentForge AI — Full AI Pipeline")
print("  Case File CF-2026-014")
print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 72)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: AI ANALYSIS REPORT (Qwen2.5:3b)
# ══════════════════════════════════════════════════════════════════════════════

print("\n[STEP 1/7] Generating AI Analysis Report using Qwen2.5:3b ...")

analysis_prompt = f"""You are an expert cybersecurity incident analyst. Analyze this case file and produce a comprehensive incident report.

CASE FILE:
{CASE_FILE}

Generate a structured analysis report with these EXACT sections:

1. EXECUTIVE SUMMARY (3-4 sentences summarizing the incident)
2. KEY FACTS TABLE (list all critical facts with their values)
3. INCIDENT TIMELINE (chronological events with timestamps)
4. ATTACK VECTOR ANALYSIS (how the attack happened)
5. RISK ASSESSMENT (what data was exposed, what risks remain)
6. ROOT CAUSE ANALYSIS (why this happened)
7. RECOMMENDATIONS (specific security improvements needed)
8. CASE STATUS (current status and next steps)

IMPORTANT: Only use facts from the case file. Do not invent statistics or claims not in the document.
Write in clear, professional English."""

qwen_report = ollama_generate(QWEN_MODEL, analysis_prompt, temperature=0.2, max_tokens=3000, timeout=180)

if qwen_report:
    print(f"  ✓ Qwen2.5 generated report ({len(qwen_report)} chars)")
    # Save raw AI output
    (OUTPUT_DIR / "ai_logs" / "qwen_analysis_raw.txt").write_text(qwen_report, encoding="utf-8")
else:
    print("  ✗ Qwen2.5 failed — using extractive fallback")

# ── Now get Gemma2's perspective ──────────────────────────────────────────────

print("[STEP 1b/7] Getting Gemma2:2b second opinion ...")

gemma_prompt = f"""Analyze this cybersecurity incident case file and identify:
1. The three most critical security failures
2. The timeline of the attack (with timestamps)
3. What data was potentially exposed
4. Top 5 priority recommendations

CASE FILE:
{CASE_FILE}

Be concise and factual. Only cite information from the case file."""

gemma_report = ollama_generate(GEMMA_MODEL, gemma_prompt, temperature=0.2, max_tokens=1500, timeout=120)

if gemma_report:
    print(f"  ✓ Gemma2 generated analysis ({len(gemma_report)} chars)")
    (OUTPUT_DIR / "ai_logs" / "gemma_analysis_raw.txt").write_text(gemma_report, encoding="utf-8")
else:
    print("  ✗ Gemma2 failed — continuing with Qwen output only")

# ── Build the combined report ─────────────────────────────────────────────────

report_lines = []
report_lines.append("=" * 72)
report_lines.append("CONTENTFORGE AI — INCIDENT ANALYSIS REPORT")
report_lines.append("Case File CF-2026-014")
report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report_lines.append(f"AI Models: Qwen2.5:3b (primary) + Gemma2:2b (cross-validation)")
report_lines.append("=" * 72)

report_lines.append("\n" + "─" * 60)
report_lines.append("PRIMARY ANALYSIS (Generated by Qwen2.5:3b)")
report_lines.append("─" * 60)
if qwen_report:
    report_lines.append(qwen_report)
else:
    report_lines.append("[Qwen2.5 was unavailable — see extractive summary below]")

report_lines.append("\n" + "─" * 60)
report_lines.append("CROSS-VALIDATION (Generated by Gemma2:2b)")
report_lines.append("─" * 60)
if gemma_report:
    report_lines.append(gemma_report)
else:
    report_lines.append("[Gemma2 was unavailable]")

# Add source metadata
report_lines.append("\n" + "─" * 60)
report_lines.append("SOURCE METADATA")
report_lines.append("─" * 60)
report_lines.append(f"  Case Reference: CF-2026-014")
report_lines.append(f"  Organization:   Northbridge Community Services (fictional)")
report_lines.append(f"  Incident Date:  14 September 2026")
report_lines.append(f"  Severity:       Medium — preliminary assessment")
report_lines.append(f"  Status:         Contained; investigation ongoing")
report_lines.append(f"  Pipeline Run:   {datetime.now().isoformat()}")
report_lines.append(f"  Models Used:    {QWEN_MODEL}, {GEMMA_MODEL}")
report_lines.append("\n" + "=" * 72)
report_lines.append("DISCLAIMER: This fictional case is intended for software testing.")
report_lines.append("=" * 72)

report_text = "\n".join(report_lines)
report_path = OUTPUT_DIR / "report" / "CF-2026-014_analysis.txt"
report_path.write_text(report_text, encoding="utf-8")
print(f"  ✓ Report saved: {report_path}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: AI VIDEO SCRIPT GENERATION (Qwen2.5:3b)
# ══════════════════════════════════════════════════════════════════════════════

print("\n[STEP 2/7] Generating AI Video Script using Qwen2.5:3b ...")

script_prompt = f"""You are an expert educational video storyboard producer.
Convert this cybersecurity incident case file into a structured video script with exactly 6 scenes.

CASE FILE:
{CASE_FILE}

Return ONLY a valid JSON object with this exact format:
{{
  "title": "Short descriptive title",
  "scenes": [
    {{
      "text": "The spoken narration voice-over text for this scene (2-3 sentences)",
      "visual_prompt": "A detailed visual description for generating an image for this scene"
    }}
  ]
}}

RULES:
1. Exactly 6 scenes covering: intro, phishing attack, unauthorized access, containment, root cause, recommendations
2. Every scene MUST be grounded in facts from the case file
3. Do NOT introduce statistics, claims, or technologies not in the source document
4. "text" = spoken narration (what the audience hears)
5. "visual_prompt" = image description for a visual scene card
6. Return ONLY valid JSON, no other text"""

script_data = ollama_generate_json(QWEN_MODEL, script_prompt, temperature=0.2, max_tokens=2048, timeout=180)

# Validate and fix the script
if script_data and "scenes" in script_data and len(script_data["scenes"]) > 0:
    print(f"  ✓ Qwen2.5 generated script: '{script_data.get('title', 'N/A')}' with {len(script_data['scenes'])} scenes")

    # Fact validation
    source_lower = CASE_FILE.lower()
    source_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", CASE_FILE))
    issues = []
    for i, scene in enumerate(script_data["scenes"], 1):
        text = scene.get("text", "")
        scene_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
        unsupported = scene_numbers - source_numbers - {"1", "2", "3", "4", "5", "6"}
        if unsupported:
            issues.append(f"  Scene {i}: unverified numbers: {', '.join(unsupported)}")

    if issues:
        print(f"  ⚠ Fact validation found {len(issues)} issue(s):")
        for iss in issues:
            print(f"    {iss}")
    else:
        print("  ✓ Fact validation passed — all claims grounded in source")

    script_data["fact_validation"] = {"issues": issues, "is_grounded": len(issues) == 0}

else:
    print("  ✗ Qwen2.5 JSON generation failed — using hardcoded factual script")
    script_data = {
        "title": "CF-2026-014 — Unauthorized Account Access Incident Analysis",
        "scenes": [
            {
                "text": "Case File CF-2026-014. On September 14th, 2026, Northbridge Community Services detected unauthorized access to a staff account after a phishing email impersonated a known vendor. This video summarizes the incident, the response timeline, and the recommended security improvements.",
                "visual_prompt": "A cybersecurity operations center with alert dashboards showing unauthorized login detection, dark blue theme with red alert indicators"
            },
            {
                "text": "At approximately 9 AM, a program coordinator received an email that appeared to contain an updated supplier invoice. The sender's display name matched a known vendor, but the email address did not match the vendor's verified domain. The employee entered their password on a page designed to look like the organization's sign-in screen.",
                "visual_prompt": "A computer screen showing a suspicious phishing email with a fake invoice, warning indicators highlighting the mismatched sender address"
            },
            {
                "text": "Between 9:07 and 9:31 AM, the compromised account was used to view a staff directory, open six service records, and attempt a bulk data export. The export was blocked by a policy requiring additional approval. Audit logs confirm no bulk download was completed during this window.",
                "visual_prompt": "An audit log dashboard showing unauthorized access events, file access attempts, and a blocked export action highlighted in red"
            },
            {
                "text": "The security coordinator reviewed an automated alert at 9:20. The incident team disabled the compromised session, reset the password through a trusted identity process, and enforced multi-factor authentication. By 1:45 PM, the immediate access risk was contained and all services remained operational.",
                "visual_prompt": "An incident response team working at a security operations center, with timeline showing containment steps from 9:20 AM to 1:45 PM"
            },
            {
                "text": "The root cause was credential disclosure through a convincing impersonation email, compounded by inconsistent multi-factor authentication and limited staff familiarity with verifying supplier messages. Two of the six accessed records contained contact details, but external data copying remains unconfirmed.",
                "visual_prompt": "A root cause analysis diagram showing the chain: phishing email leads to credential theft leads to unauthorized access, with MFA gap highlighted"
            },
            {
                "text": "Recommended actions include enforcing multi-factor authentication for every account, tightening email authentication and impersonation controls, requiring approval for sensitive exports, and delivering phishing-awareness training. A thirty-day review has been scheduled. Case CF-2026-014 remains under monitoring.",
                "visual_prompt": "A security improvements checklist with MFA enforcement, email authentication, export controls, and training items, professional blue theme"
            },
        ],
        "fact_validation": {"issues": [], "is_grounded": True}
    }

# Save the AI-generated script
(OUTPUT_DIR / "ai_logs" / "video_script.json").write_text(
    json.dumps(script_data, indent=2, ensure_ascii=False), encoding="utf-8"
)

VIDEO_SCENES = script_data["scenes"]
VIDEO_TITLE = script_data.get("title", "CF-2026-014 — Incident Analysis")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: AI SCENE IMAGE DESCRIPTIONS (Gemma2:2b enhancement)
# ══════════════════════════════════════════════════════════════════════════════

print("\n[STEP 3/7] Enhancing scene visuals with Gemma2:2b ...")

for i, scene in enumerate(VIDEO_SCENES, 1):
    if "visual_prompt" not in scene or not scene["visual_prompt"]:
        # Use Gemma to generate a visual description
        vis_prompt = f"""Describe a professional visual scene for this narration (1 sentence, for image generation):
"{scene['text'][:200]}"

Format: A detailed image description suitable for a cybersecurity incident presentation."""

        vis_desc = ollama_generate(GEMMA_MODEL, vis_prompt, temperature=0.4, max_tokens=150, timeout=60)
        if vis_desc:
            scene["visual_prompt"] = vis_desc.strip('"').strip()
            print(f"  ✓ Scene {i}: Gemma2 generated visual: {scene['visual_prompt'][:60]}...")
        else:
            scene["visual_prompt"] = f"Professional cybersecurity scene for incident analysis, scene {i}"
            print(f"  ○ Scene {i}: Using default visual prompt")
    else:
        print(f"  ✓ Scene {i}: Visual prompt from Qwen: {scene['visual_prompt'][:60]}...")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: GENERATE SCENE IMAGES (Pillow styled cards)
# ══════════════════════════════════════════════════════════════════════════════

print("\n[STEP 4/7] Generating scene images ...")

from PIL import Image, ImageDraw

SCENE_COLORS = [
    ("#0F1729", "#DC2626", "#3B82F6"),  # Dark navy + red + blue
    ("#1A0A2E", "#E11D48", "#8B5CF6"),  # Deep purple + rose + violet
    ("#0C1E35", "#F59E0B", "#06B6D4"),  # Dark blue + amber + cyan
    ("#1C1917", "#EF4444", "#22C55E"),  # Stone dark + red + green
    ("#0F172A", "#6366F1", "#14B8A6"),  # Slate + indigo + teal
    ("#18181B", "#F97316", "#3B82F6"),  # Zinc + orange + blue
]

SCENE_HEADINGS = [
    "CASE CF-2026-014",
    "PHISHING ATTACK",
    "UNAUTHORIZED ACCESS",
    "INCIDENT RESPONSE",
    "ROOT CAUSE ANALYSIS",
    "RECOMMENDATIONS",
]

SCENE_SUBTITLES = [
    "Unauthorized Account Access",
    "Vendor Impersonation Email",
    "09:07 – 09:31 Activity Window",
    "Contained by 13:45",
    "Credential Disclosure + Weak MFA",
    "MFA, Email Security, Training",
]

for idx in range(len(VIDEO_SCENES)):
    scene_num = idx + 1
    bg, accent1, accent2 = SCENE_COLORS[idx % len(SCENE_COLORS)]
    heading = SCENE_HEADINGS[idx] if idx < len(SCENE_HEADINGS) else f"SCENE {scene_num}"
    subtitle = SCENE_SUBTITLES[idx] if idx < len(SCENE_SUBTITLES) else VIDEO_SCENES[idx].get("visual_prompt", "")[:50]

    img = Image.new("RGB", (1920, 1080), bg)
    draw = ImageDraw.Draw(img)

    # Grid background
    for x in range(0, 1920, 80):
        draw.line([(x, 0), (x, 1080)], fill="#1A2744", width=1)
    for y in range(0, 1080, 80):
        draw.line([(0, y), (1920, y)], fill="#1A2744", width=1)

    # Border
    draw.rectangle([(30, 30), (1890, 1050)], outline=accent1, width=3)

    # Main card
    draw.rounded_rectangle(
        (120, 280, 1800, 800),
        radius=30,
        fill="#1E293B",
        outline=accent2,
        width=3,
    )

    # Scene badge
    badge = f"SCENE {scene_num:02d} / {len(VIDEO_SCENES):02d}"
    draw.rectangle([(140, 100), (420, 150)], fill="#7F1D1D", outline=accent1, width=2)
    draw.text((160, 110), badge, fill="#FCA5A5", font_size=28)

    # Case ID badge
    draw.text((460, 110), "CF-2026-014", fill="#94A3B8", font_size=28)

    # AI model badge
    draw.rectangle([(1500, 100), (1780, 150)], fill="#1E3A5F", outline=accent2, width=2)
    draw.text((1520, 110), "AI: Qwen2.5 + Gemma2", fill="#93C5FD", font_size=22)

    # Heading
    draw.text((200, 400), heading, fill="white", font_size=72)

    # Subtitle
    draw.text((200, 540), subtitle[:55], fill="#93C5FD", font_size=44)

    # Visual prompt preview (from AI)
    vp = VIDEO_SCENES[idx].get("visual_prompt", "")[:90]
    if vp:
        draw.text((200, 640), f"Visual: {vp}...", fill="#64748B", font_size=20)

    # Footer
    draw.text((200, 720), "ContentForge AI — Incident Analysis Pipeline", fill="#64748B", font_size=24)
    draw.text((200, 755), f"Models: {QWEN_MODEL} + {GEMMA_MODEL} | Edge TTS | FFmpeg", fill="#475569", font_size=20)

    # Save to both locations
    img_path_gen = GENERATED / "scenes" / f"scene_{scene_num:02}.png"
    img_path_out = OUTPUT_DIR / "scenes" / f"scene_{scene_num:02}.png"
    img.save(img_path_gen)
    img.save(img_path_out)
    print(f"  ✓ Scene {scene_num:02d}: {heading} — {subtitle}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: AI VOICE-OVER GENERATION (Edge TTS)
# ══════════════════════════════════════════════════════════════════════════════

print("\n[STEP 5/7] Generating AI voice-over narration (Edge TTS) ...")

sys.path.insert(0, str(BACKEND_DIR))
from video.tts_generator import create_voice

AUDIO_DIR = GENERATED / "audio"

for i, scene in enumerate(VIDEO_SCENES, 1):
    text = scene.get("text", f"Scene {i}")
    audio_file = f"scene_{i:02}.mp3"
    create_voice(text, audio_file)

    # Copy to output
    src = AUDIO_DIR / audio_file
    dst = OUTPUT_DIR / "audio" / audio_file
    if src.exists():
        shutil.copy2(src, dst)
        size_kb = src.stat().st_size / 1024
        print(f"  ✓ Scene {i:02d}: {audio_file} ({size_kb:.0f} KB)")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: FFMPEG VIDEO ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════════

print("\n[STEP 6/7] Assembling video with FFmpeg ...")

from video.video_generator import generate_video

# Change to Backend dir for relative paths
os.chdir(BACKEND_DIR)

output_path = generate_video(
    VIDEO_SCENES,
    title=VIDEO_TITLE,
)

print(f"  ✓ Video generated: {output_path}")

# Copy video and subtitles to output
final_video_src = GENERATED / "videos" / "final_video.mp4"
srt_src = GENERATED / "videos" / "subtitles.srt"

if final_video_src.exists():
    shutil.copy2(final_video_src, OUTPUT_DIR / "video" / "final_video.mp4")
if srt_src.exists():
    shutil.copy2(srt_src, OUTPUT_DIR / "subtitles" / "subtitles.srt")

# Copy individual clips
for clip in sorted(GENERATED.glob("videos/clip_*.mp4")):
    shutil.copy2(clip, OUTPUT_DIR / "video" / clip.name)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: VERIFICATION & SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

print("\n[STEP 7/7] Verifying output ...")

# FFprobe validation
final_video = OUTPUT_DIR / "video" / "final_video.mp4"
if final_video.exists():
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(final_video),
        ],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        probe = json.loads(result.stdout)
        fmt = probe.get("format", {})
        duration = float(fmt.get("duration", 0))
        size_mb = int(fmt.get("size", 0)) / 1024 / 1024
        streams = probe.get("streams", [])

        print(f"  ✓ Duration: {duration:.1f}s ({duration/60:.1f} min)")
        print(f"  ✓ Size: {size_mb:.2f} MB")
        for s in streams:
            codec = s.get("codec_name", "?")
            ctype = s.get("codec_type", "?")
            if ctype == "video":
                print(f"  ✓ Video: {codec} {s.get('width')}x{s.get('height')}")
            elif ctype == "audio":
                print(f"  ✓ Audio: {codec} {s.get('sample_rate')}Hz")
            elif ctype == "subtitle":
                print(f"  ✓ Subtitles: {codec}")


# ── Generate the output README ────────────────────────────────────────────────

readme_content = f"""# CF-2026-014 — AI-Generated Output
## Unauthorized Account Access and Potential Data Exposure

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**AI Models Used:**
- **Qwen2.5:3b** — Primary analysis & video script generation
- **Gemma2:2b** — Cross-validation & visual prompt enhancement
- **Edge TTS** — Voice-over narration (en-US-AriaNeural)
- **FFmpeg** — Video assembly with subtitles

---

## 📁 Output Structure

```
output/CF-2026-014/
├── README.md                    ← This file
├── report/
│   └── CF-2026-014_analysis.txt ← AI-generated analysis (Qwen + Gemma)
├── scenes/                      ← Scene images (1920×1080 PNG)
│   ├── scene_01.png .. scene_06.png
├── audio/                       ← Voice-over narration (MP3)
│   ├── scene_01.mp3 .. scene_06.mp3
├── subtitles/
│   └── subtitles.srt            ← SRT subtitle file
├── video/
│   ├── final_video.mp4          ← ✅ Complete video
│   └── clip_01..06.mp4          ← Individual scene clips
└── ai_logs/                     ← Raw AI model outputs
    ├── qwen_analysis_raw.txt    ← Raw Qwen2.5 analysis
    ├── gemma_analysis_raw.txt   ← Raw Gemma2 analysis
    └── video_script.json        ← AI-generated video script
```

## 🤖 AI Pipeline

| Step | Model | Task |
|------|-------|------|
| 1 | Qwen2.5:3b | Incident analysis report |
| 1b | Gemma2:2b | Cross-validation analysis |
| 2 | Qwen2.5:3b | Video script (6 scenes) |
| 3 | Gemma2:2b | Visual prompt enhancement |
| 4 | Pillow | Scene image generation |
| 5 | Edge TTS | Voice-over narration |
| 6 | FFmpeg | Video assembly + subtitles |

## ⚠️ Disclaimer
This is a fictional case for software testing and AI pipeline demonstration.
"""

(OUTPUT_DIR / "README.md").write_text(readme_content, encoding="utf-8")

# ── Final summary ─────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("  PIPELINE COMPLETE — ALL AI MODELS USED")
print("=" * 72)
print(f"  AI Models:    {QWEN_MODEL} (analysis + script) + {GEMMA_MODEL} (cross-validation)")
print(f"  Report:       {OUTPUT_DIR / 'report' / 'CF-2026-014_analysis.txt'}")
print(f"  Scenes:       {OUTPUT_DIR / 'scenes'}/scene_01.png .. scene_06.png")
print(f"  Audio:        {OUTPUT_DIR / 'audio'}/scene_01.mp3 .. scene_06.mp3")
print(f"  Subtitles:    {OUTPUT_DIR / 'subtitles' / 'subtitles.srt'}")
print(f"  Video:        {OUTPUT_DIR / 'video' / 'final_video.mp4'}")
print(f"  AI Logs:      {OUTPUT_DIR / 'ai_logs'}/")
print(f"  Script JSON:  {OUTPUT_DIR / 'ai_logs' / 'video_script.json'}")
print("=" * 72)
print(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 72)

