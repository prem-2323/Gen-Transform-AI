"""
ContentForge AI — Full Pipeline: Case File CF-2026-014
Produces: Summary, Key Facts, Timeline, Risk Assessment, Recommendations,
          Video Script, Voice-Over Audio, and Final MP4 Video with Subtitles.
"""
import json
import os
import sys
import asyncio
from pathlib import Path

# Ensure bin/ is in PATH for ffmpeg/ffprobe
_bin = Path(__file__).resolve().parent.parent / "bin"
if _bin.is_dir():
    os.environ["PATH"] = f"{_bin}{os.pathsep}{os.environ.get('PATH', '')}"

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

# ── 1. ANALYSIS: Summary, Key Facts, Timeline, Risk, Recommendations ──────────

SUMMARY = """
On 14 September 2026, Northbridge Community Services experienced unauthorized
access to one staff account after a phishing email impersonated a known vendor.
The attacker gained access for approximately 24 minutes, viewed a staff
directory and six service records, but was blocked from exporting bulk data
by an existing approval policy. The incident was contained by 13:45 the same
day. No bulk download occurred, but limited record exposure remains unconfirmed.
The case is classified as Medium severity with monitoring ongoing.
""".strip()

KEY_FACTS = {
    "Case Reference": "CF-2026-014",
    "Organization": "Northbridge Community Services",
    "Incident Date": "14 September 2026",
    "Severity": "Medium — preliminary assessment",
    "Root Cause": "Credential phishing via vendor impersonation email",
    "Accounts Targeted": "3 accounts (1 compromised, 1 failed attempts, 1 unaffected)",
    "Unauthorized Access Window": "09:07 – 09:31 (24 minutes)",
    "Records Accessed": "Staff directory + 6 service records (2 with contact details)",
    "Bulk Export": "Attempted but blocked by approval policy",
    "Data Exfiltration": "Not confirmed; classified as limited but unresolved",
    "Phishing Recipients": "4 staff (only 1 compromised)",
    "Portal Compromise": "None — portal infrastructure was not affected",
    "Status": "Contained; monitoring continues",
}

TIMELINE = [
    ("~09:00", "Phishing email received", "Employee receives email impersonating a known vendor with a fake invoice link"),
    ("09:07", "Unauthorized access begins", "Attacker signs in to the compromised coordinator account from an unfamiliar device"),
    ("09:07–09:31", "Malicious activity window", "Account views staff directory, opens 6 service records, attempts bulk export (blocked)"),
    ("09:20", "Alert reviewed", "Security coordinator reviews automated alert showing repeated login attempts against 3 accounts"),
    ("09:31", "Unauthorized access ends", "Last recorded unauthorized action in audit logs"),
    ("09:20–10:00", "Initial response", "Incident team opens CF-2026-014, preserves email evidence, instructs employee to stop using account"),
    ("10:00–12:00", "Containment actions", "Sessions disabled, password reset via trusted process, MFA enforced, device restrictions applied"),
    ("12:00–13:00", "Email investigation", "Gateway scan finds 4 recipients; 3 confirm no interaction; 4th device checked clean"),
    ("13:45", "Containment confirmed", "Portal, scheduling, and referral workflows verified operational; immediate risk contained"),
    ("13:45+", "Notification review begins", "Privacy lead and service director begin formal assessment of notification obligations"),
    ("Ongoing", "30-day review scheduled", "Follow-up actions assigned with owners and due dates; case marked 'contained, monitoring continues'"),
]

RISK_ASSESSMENT = """
POTENTIAL EXPOSURE:
• Six service records were viewed, two containing contact details and
  appointment notes. No names, addresses, medical data, or passwords
  are included in this case file.
• The bulk export was blocked; audit logs confirm no completed download.
• Whether viewed data was copied externally cannot be confirmed from
  available logs — exposure is classified as limited but unresolved.

REMAINING UNCERTAINTY:
• The identity of the attacker has not been established.
• External data exfiltration cannot be ruled out despite no direct evidence.
• The privacy and notification assessment remains pending formal review.
• Log review is still in progress and may reveal additional findings.

MITIGATING FACTORS:
• Export approval policy prevented bulk data download.
• Employee self-reported promptly after noticing unusual notifications.
• Only 1 of 4 phishing recipients interacted with the email.
• Portal infrastructure was not compromised.
""".strip()

RECOMMENDATIONS = [
    "Enforce multi-factor authentication (MFA) for every staff account without exception",
    "Require additional approval workflows for all sensitive data exports",
    "Tighten email authentication controls (SPF, DKIM, DMARC) and implement impersonation detection",
    "Review and minimize access permissions based on the principle of least privilege",
    "Deliver organization-wide phishing-awareness training with a safe internal reporting link",
    "Implement device trust policies to restrict portal access from unrecognized devices",
    "Schedule a 30-day follow-up review with assigned owners for each remediation action",
    "Complete the formal privacy assessment and document notification decisions with evidence",
]

# ── 2. VIDEO SCRIPT (6 scenes grounded in the case file) ──────────────────────

VIDEO_SCENES = [
    {
        "text": (
            "Case File CF-2026-014. On September 14th, 2026, Northbridge Community "
            "Services detected unauthorized access to a staff account after a phishing "
            "email impersonated a known vendor. This video summarizes the incident, "
            "the response timeline, and the recommended security improvements."
        ),
    },
    {
        "text": (
            "At approximately 9 AM, a program coordinator received an email that "
            "appeared to contain an updated supplier invoice. The sender's display "
            "name matched a known vendor, but the email address did not match the "
            "vendor's verified domain. The employee entered their password on a page "
            "designed to look like the organization's sign-in screen."
        ),
    },
    {
        "text": (
            "Between 9:07 and 9:31 AM, the compromised account was used to view a "
            "staff directory, open six service records, and attempt a bulk data export. "
            "The export was blocked by a policy requiring additional approval. Audit "
            "logs confirm no bulk download was completed during this window."
        ),
    },
    {
        "text": (
            "The security coordinator reviewed an automated alert at 9:20. The incident "
            "team disabled the compromised session, reset the password through a trusted "
            "identity process, and enforced multi-factor authentication. By 1:45 PM, the "
            "immediate access risk was contained and all services remained operational."
        ),
    },
    {
        "text": (
            "The root cause was credential disclosure through a convincing impersonation "
            "email, compounded by inconsistent multi-factor authentication and limited "
            "staff familiarity with verifying supplier messages. Two of the six accessed "
            "records contained contact details, but external data copying remains unconfirmed."
        ),
    },
    {
        "text": (
            "Recommended actions include enforcing multi-factor authentication for every "
            "account, tightening email authentication and impersonation controls, requiring "
            "approval for sensitive exports, and delivering phishing-awareness training. "
            "A thirty-day review has been scheduled. Case CF-2026-014 remains under monitoring."
        ),
    },
]

# ── 3. GENERATE REPORT ARTIFACT ───────────────────────────────────────────────

REPORT_DIR = Path("generated/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

report_lines = []
report_lines.append("=" * 72)
report_lines.append("CONTENTFORGE AI — INCIDENT ANALYSIS REPORT")
report_lines.append("Case File CF-2026-014")
report_lines.append("=" * 72)

report_lines.append("\n── SUMMARY ──────────────────────────────────────────────")
report_lines.append(SUMMARY)

report_lines.append("\n── KEY FACTS ────────────────────────────────────────────")
for k, v in KEY_FACTS.items():
    report_lines.append(f"  {k:.<40s} {v}")

report_lines.append("\n── TIMELINE ─────────────────────────────────────────────")
for time_val, event, detail in TIMELINE:
    report_lines.append(f"  [{time_val:>14s}]  {event}")
    report_lines.append(f"  {'':>16s}  → {detail}")

report_lines.append("\n── RISK ASSESSMENT ──────────────────────────────────────")
report_lines.append(RISK_ASSESSMENT)

report_lines.append("\n── RECOMMENDATIONS ─────────────────────────────────────")
for i, rec in enumerate(RECOMMENDATIONS, 1):
    report_lines.append(f"  {i}. {rec}")

report_lines.append("\n── VIDEO SCRIPT (6 Scenes) ─────────────────────────────")
for i, sc in enumerate(VIDEO_SCENES, 1):
    report_lines.append(f"\n  Scene {i}:")
    report_lines.append(f"    Narration: \"{sc['text']}\"")

report_lines.append("\n" + "=" * 72)

report_text = "\n".join(report_lines)
report_path = REPORT_DIR / "CF-2026-014_analysis.txt"
report_path.write_text(report_text, encoding="utf-8")
print(f"[1/4] Report saved: {report_path}")
print()
print(report_text)
print()

# ── 4. GENERATE SAMPLE SCENE IMAGES ───────────────────────────────────────────

from PIL import Image, ImageDraw

SCENES_DIR = Path("generated/scenes")
SCENES_DIR.mkdir(parents=True, exist_ok=True)

SCENE_CARDS = [
    ("CASE CF-2026-014", "Unauthorized Account Access"),
    ("PHISHING ATTACK", "Vendor Impersonation Email"),
    ("UNAUTHORIZED ACCESS", "09:07 – 09:31 Activity Window"),
    ("INCIDENT RESPONSE", "Contained by 13:45"),
    ("ROOT CAUSE ANALYSIS", "Credential Disclosure + Weak MFA"),
    ("RECOMMENDATIONS", "MFA, Email Security, Training"),
]

for idx, (heading, subtitle) in enumerate(SCENE_CARDS, 1):
    img = Image.new("RGB", (1920, 1080), "#0F1729")
    draw = ImageDraw.Draw(img)

    # Grid background
    for x in range(0, 1920, 80):
        draw.line([(x, 0), (x, 1080)], fill="#1A2744", width=1)
    for y in range(0, 1080, 80):
        draw.line([(0, y), (1920, y)], fill="#1A2744", width=1)

    # Border
    draw.rectangle([(30, 30), (1890, 1050)], outline="#DC2626", width=3)

    # Card
    draw.rounded_rectangle(
        (120, 280, 1800, 800),
        radius=30,
        fill="#1E293B",
        outline="#3B82F6",
        width=3,
    )

    # Badge
    badge = f"SCENE {idx:02d} / 06"
    draw.rectangle([(140, 100), (420, 150)], fill="#7F1D1D", outline="#DC2626", width=2)
    draw.text((160, 110), badge, fill="#FCA5A5", font_size=28)

    # CASE ID
    draw.text((460, 110), "CF-2026-014", fill="#94A3B8", font_size=28)

    # Heading
    draw.text((200, 400), heading, fill="white", font_size=72)

    # Subtitle
    draw.text((200, 540), subtitle, fill="#93C5FD", font_size=44)

    # Footer
    draw.text((200, 720), "ContentForge AI — Incident Analysis Pipeline", fill="#64748B", font_size=24)

    img.save(SCENES_DIR / f"scene_{idx:02}.png")

print(f"[2/4] Scene images generated: {SCENES_DIR}")

# ── 5. GENERATE VOICE-OVER + VIDEO ────────────────────────────────────────────

from video.video_generator import generate_video

print("[3/4] Generating voice-over and rendering video...")

output_path = generate_video(
    VIDEO_SCENES,
    title="CF-2026-014 — Unauthorized Account Access Incident Analysis",
)

print(f"[4/4] Final video: {output_path}")

# ── 6. VERIFY WITH FFPROBE ────────────────────────────────────────────────────

import subprocess

print("\n── FFPROBE VALIDATION ───────────────────────────────────")
subprocess.run([
    "ffprobe", "-v", "error",
    "-show_entries", "stream=codec_name,width,height",
    "-show_entries", "format=duration,size",
    "-of", "json",
    str(Path("generated/videos/final_video.mp4")),
])

print("\n" + "=" * 72)
print("PIPELINE COMPLETE")
print("=" * 72)
print(f"  Report:     {report_path.resolve()}")
print(f"  Scenes:     {SCENES_DIR.resolve()}/scene_01.png .. scene_06.png")
print(f"  Audio:      generated/audio/scene_01.mp3 .. scene_06.mp3")
print(f"  Subtitles:  generated/videos/subtitles.srt")
print(f"  Video:      {output_path}")
print("=" * 72)

