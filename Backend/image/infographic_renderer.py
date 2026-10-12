"""
Matplotlib-based Infographic Renderer.

Generates publication-quality infographic PNG images from structured data,
without requiring Stable Diffusion Forge or any GPU. Uses matplotlib with
a custom dark-theme corporate style.

Supports layout modes: Vertical, Horizontal, Timeline, Process, Comparison
Supports visual styles: Corporate, Minimal, Editorial, Technology
"""

import io
import textwrap
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server use

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as path_effects
import numpy as np


# ── Style Palettes ───────────────────────────────────────────────────────────

STYLE_PALETTES = {
    "Corporate": {
        "bg": "#0b0f1a",
        "card_bg": "#111827",
        "card_border": "#1e293b",
        "title": "#ffffff",
        "subtitle": "#94a3b8",
        "accent": "#3b82f6",
        "accent2": "#8b5cf6",
        "accent3": "#06b6d4",
        "stat_value": "#a78bfa",
        "stat_label": "#e2e8f0",
        "stat_subtext": "#94a3b8",
        "point_title": "#38bdf8",
        "point_desc": "#cbd5e1",
        "cta_bg_start": "#7e22ce",
        "cta_bg_end": "#2563eb",
        "cta_text": "#ffffff",
        "badge_bg": "#f59e0b",
        "badge_text": "#fbbf24",
        "grid": "#1e293b",
        "divider": "#334155",
        "bullet": "#38bdf8",
    },
    "Minimal": {
        "bg": "#0e1117",
        "card_bg": "#161b22",
        "card_border": "#21262d",
        "title": "#f0f6fc",
        "subtitle": "#8b949e",
        "accent": "#58a6ff",
        "accent2": "#bc8cff",
        "accent3": "#79c0ff",
        "stat_value": "#bc8cff",
        "stat_label": "#f0f6fc",
        "stat_subtext": "#8b949e",
        "point_title": "#58a6ff",
        "point_desc": "#c9d1d9",
        "cta_bg_start": "#238636",
        "cta_bg_end": "#1f6feb",
        "cta_text": "#ffffff",
        "badge_bg": "#da3633",
        "badge_text": "#ff7b72",
        "grid": "#21262d",
        "divider": "#30363d",
        "bullet": "#58a6ff",
    },
    "Editorial": {
        "bg": "#0c0c14",
        "card_bg": "#14142b",
        "card_border": "#252547",
        "title": "#ffffff",
        "subtitle": "#9898b8",
        "accent": "#e040fb",
        "accent2": "#7c4dff",
        "accent3": "#00e5ff",
        "stat_value": "#e040fb",
        "stat_label": "#e8e8f0",
        "stat_subtext": "#9898b8",
        "point_title": "#00e5ff",
        "point_desc": "#c8c8e0",
        "cta_bg_start": "#e040fb",
        "cta_bg_end": "#7c4dff",
        "cta_text": "#ffffff",
        "badge_bg": "#ff6d00",
        "badge_text": "#ffab40",
        "grid": "#1a1a35",
        "divider": "#303060",
        "bullet": "#00e5ff",
    },
    "Technology": {
        "bg": "#020617",
        "card_bg": "#0f172a",
        "card_border": "#1e293b",
        "title": "#f1f5f9",
        "subtitle": "#64748b",
        "accent": "#06b6d4",
        "accent2": "#22d3ee",
        "accent3": "#a855f7",
        "stat_value": "#22d3ee",
        "stat_label": "#e2e8f0",
        "stat_subtext": "#64748b",
        "point_title": "#06b6d4",
        "point_desc": "#cbd5e1",
        "cta_bg_start": "#0891b2",
        "cta_bg_end": "#7c3aed",
        "cta_text": "#ffffff",
        "badge_bg": "#f59e0b",
        "badge_text": "#fbbf24",
        "grid": "#0f172a",
        "divider": "#1e293b",
        "bullet": "#22d3ee",
    },
}


def _hex_to_rgb(hex_color: str):
    """Convert hex color to normalized RGB tuple."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _add_rounded_rect(ax, x, y, w, h, color, border_color=None, radius=0.02, alpha=1.0, linewidth=1.0):
    """Add a rounded rectangle patch to an axes."""
    fancy = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        facecolor=color,
        edgecolor=border_color or "none",
        linewidth=linewidth,
        alpha=alpha,
        zorder=2,
    )
    ax.add_patch(fancy)
    return fancy


def _wrap_text(text: str, max_chars: int = 45) -> str:
    """Wrap long text into multiple lines."""
    return "\n".join(textwrap.wrap(text, width=max_chars))


def render_infographic(
    key_message: str,
    key_statistics: List[Dict[str, str]],
    supporting_points: List[Dict[str, str]],
    call_to_action: str,
    layout: str = "Vertical",
    visual_style: str = "Corporate",
    width_px: int = 1200,
    height_px: int = 800,
) -> bytes:
    """
    Render a professional infographic as a PNG image using matplotlib.

    Args:
        key_message: Main headline of the infographic.
        key_statistics: List of dicts with 'value', 'label', 'subtext'.
        supporting_points: List of dicts with 'title', 'description'.
        call_to_action: CTA text at the bottom.
        layout: Layout mode (Vertical, Horizontal, Timeline, Process, Comparison).
        visual_style: Visual theme (Corporate, Minimal, Editorial, Technology).
        width_px: Width in pixels.
        height_px: Height in pixels.

    Returns:
        PNG image bytes.
    """
    palette = STYLE_PALETTES.get(visual_style, STYLE_PALETTES["Corporate"])
    dpi = 150
    fig_w = width_px / dpi
    fig_h = height_px / dpi

    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), dpi=dpi)
    fig.patch.set_facecolor(palette["bg"])
    ax.set_facecolor(palette["bg"])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ── Background Grid ──────────────────────────────────────────────────
    grid_color = _hex_to_rgb(palette["grid"])
    for gx in np.arange(0, 1.01, 0.04):
        ax.axvline(gx, color=grid_color, linewidth=0.3, alpha=0.3, zorder=0)
    for gy in np.arange(0, 1.01, 0.04):
        ax.axhline(gy, color=grid_color, linewidth=0.3, alpha=0.3, zorder=0)

    # ── Outer Border ─────────────────────────────────────────────────────
    _add_rounded_rect(ax, 0.01, 0.01, 0.98, 0.98,
                       color="none", border_color=palette["divider"],
                       radius=0.015, linewidth=1.5)

    # ── Badge ────────────────────────────────────────────────────────────
    badge_text = f"{visual_style.upper()} INFOGRAPHIC · {layout.upper()}"
    _add_rounded_rect(ax, 0.04, 0.92, 0.28, 0.04,
                       color=_hex_to_rgb(palette["badge_bg"]) + (0.15,),
                       border_color=_hex_to_rgb(palette["badge_bg"]) + (0.4,),
                       radius=0.005, linewidth=0.8)
    ax.text(0.05, 0.938, badge_text,
            fontsize=6.5, fontweight="bold", color=palette["badge_text"],
            fontfamily="monospace", va="center", zorder=5)

    # ── Title ────────────────────────────────────────────────────────────
    title_display = key_message if len(key_message) <= 70 else key_message[:67] + "..."
    ax.text(0.04, 0.885, title_display,
            fontsize=14, fontweight="bold", color=palette["title"],
            fontfamily="sans-serif", va="center", zorder=5)

    # ── Divider ──────────────────────────────────────────────────────────
    ax.plot([0.04, 0.96], [0.86, 0.86], color=palette["divider"],
            linewidth=0.8, zorder=3)

    # ── Statistics Cards ─────────────────────────────────────────────────
    stats = key_statistics[:4]
    num_stats = len(stats) if stats else 1
    stat_width = 0.92 / num_stats - 0.01
    stat_y = 0.67
    stat_h = 0.16

    for i, stat in enumerate(stats):
        sx = 0.04 + i * (stat_width + 0.01)

        # Card background
        _add_rounded_rect(ax, sx, stat_y, stat_width, stat_h,
                           color=palette["card_bg"],
                           border_color=palette["card_border"],
                           radius=0.01, linewidth=0.8)

        # Accent top bar
        accent_colors = [palette["accent"], palette["accent2"], palette["accent3"], palette["accent"]]
        bar_color = accent_colors[i % len(accent_colors)]
        ax.plot([sx + 0.005, sx + stat_width - 0.005],
                [stat_y + stat_h - 0.003, stat_y + stat_h - 0.003],
                color=bar_color, linewidth=2.5, solid_capstyle="round", zorder=4)

        # Value
        value_text = str(stat.get("value", "N/A"))
        ax.text(sx + 0.015, stat_y + stat_h - 0.05, value_text,
                fontsize=16, fontweight="bold", color=palette["stat_value"],
                fontfamily="monospace", va="center", zorder=5)

        # Label
        label_text = stat.get("label", "")
        if len(label_text) > 22:
            label_text = label_text[:20] + "..."
        ax.text(sx + 0.015, stat_y + 0.055, label_text,
                fontsize=7.5, fontweight="bold", color=palette["stat_label"],
                fontfamily="sans-serif", va="center", zorder=5)

        # Subtext
        subtext = stat.get("subtext", "")
        if len(subtext) > 28:
            subtext = subtext[:26] + "..."
        ax.text(sx + 0.015, stat_y + 0.02, subtext,
                fontsize=6, color=palette["stat_subtext"],
                fontfamily="sans-serif", va="center", zorder=5)

    # ── Supporting Points Section ────────────────────────────────────────
    points = supporting_points[:6]
    section_y = 0.62
    ax.text(0.04, section_y, "CORE OBSERVATIONS & KEY INSIGHTS",
            fontsize=7, fontweight="bold", color=palette["subtitle"],
            fontfamily="sans-serif", va="center", zorder=5)

    if layout in ("Horizontal", "Comparison"):
        # Side by side layout
        cols = 2
        rows = (len(points) + 1) // 2
        pt_w = 0.44
        pt_h = 0.09
        for idx, pt in enumerate(points):
            col = idx % cols
            row = idx // cols
            px = 0.04 + col * 0.48
            py = section_y - 0.06 - row * (pt_h + 0.015)
            _render_point_card(ax, px, py, pt_w, pt_h, pt, palette)
    elif layout == "Timeline":
        # Timeline layout with connecting line
        pt_w = 0.88
        pt_h = 0.065
        timeline_x = 0.06
        for idx, pt in enumerate(points[:4]):
            py = section_y - 0.06 - idx * (pt_h + 0.015)
            # Timeline connector dot
            ax.plot(timeline_x, py + pt_h / 2, "o",
                    color=palette["bullet"], markersize=6, zorder=6)
            if idx < min(len(points), 4) - 1:
                next_py = section_y - 0.06 - (idx + 1) * (pt_h + 0.015)
                ax.plot([timeline_x, timeline_x],
                        [py + pt_h / 2 - 0.01, next_py + pt_h / 2 + 0.01],
                        color=palette["divider"], linewidth=1.5, zorder=3)
            _render_point_card(ax, 0.09, py, pt_w - 0.05, pt_h, pt, palette)
    elif layout == "Process":
        # Process flow with arrows
        pt_w = 0.88
        pt_h = 0.065
        for idx, pt in enumerate(points[:4]):
            py = section_y - 0.06 - idx * (pt_h + 0.02)
            step_label = f"STEP {idx + 1}"
            ax.text(0.05, py + pt_h - 0.005, step_label,
                    fontsize=5.5, fontweight="bold", color=palette["accent"],
                    fontfamily="monospace", va="center", zorder=6)
            _render_point_card(ax, 0.04, py, pt_w, pt_h - 0.012, pt, palette)
            if idx < min(len(points), 4) - 1:
                ax.annotate("", xy=(0.48, py - 0.005),
                            xytext=(0.48, py + 0.003),
                            arrowprops=dict(arrowstyle="->", color=palette["accent"],
                                            lw=1.2), zorder=6)
    else:
        # Default Vertical layout
        cols = 2
        rows = (len(points) + 1) // 2
        pt_w = 0.44
        pt_h = 0.08
        for idx, pt in enumerate(points):
            col = idx % cols
            row = idx // cols
            px = 0.04 + col * 0.48
            py = section_y - 0.06 - row * (pt_h + 0.015)
            _render_point_card(ax, px, py, pt_w, pt_h, pt, palette)

    # ── Call to Action Banner ────────────────────────────────────────────
    cta_y = 0.03
    cta_h = 0.06
    # Gradient-like CTA using overlapping rects
    _add_rounded_rect(ax, 0.04, cta_y, 0.92, cta_h,
                       color=palette["cta_bg_start"],
                       border_color="none",
                       radius=0.008, alpha=0.85)
    # Secondary gradient overlay
    _add_rounded_rect(ax, 0.50, cta_y, 0.46, cta_h,
                       color=palette["cta_bg_end"],
                       border_color="none",
                       radius=0.008, alpha=0.5)

    cta_display = call_to_action if len(call_to_action) <= 80 else call_to_action[:77] + "..."
    cta_label = f"\u2192 {cta_display}"
    ax.text(0.50, cta_y + cta_h / 2, cta_label,
            fontsize=8, fontweight="bold", color=palette["cta_text"],
            fontfamily="sans-serif", ha="center", va="center", zorder=5)

    # ── Render to bytes ──────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                pad_inches=0.05, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _render_point_card(ax, x, y, w, h, point: Dict[str, str], palette: Dict[str, str]):
    """Render a single supporting-point card."""
    _add_rounded_rect(ax, x, y, w, h,
                       color=palette["card_bg"],
                       border_color=palette["card_border"],
                       radius=0.008, linewidth=0.6)

    # Bullet dot
    ax.plot(x + 0.015, y + h - 0.02, "o",
            color=palette["bullet"], markersize=4, zorder=6)

    # Title
    title = point.get("title", "")
    if len(title) > 40:
        title = title[:38] + "..."
    ax.text(x + 0.03, y + h - 0.022, title,
            fontsize=7, fontweight="bold", color=palette["point_title"],
            fontfamily="sans-serif", va="center", zorder=5)

    # Description
    desc = point.get("description", "")
    if len(desc) > 70:
        desc = desc[:68] + "..."
    ax.text(x + 0.015, y + 0.015, desc,
            fontsize=5.5, color=palette["point_desc"],
            fontfamily="sans-serif", va="center", zorder=5,
            wrap=True)


def save_infographic(image_bytes: bytes, prefix: str = "infographic") -> str:
    """Save infographic PNG bytes to the generated_images directory."""
    from .service import IMAGE_STORAGE
    IMAGE_STORAGE.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex[:12]}.png"
    output_path = IMAGE_STORAGE / filename
    output_path.write_bytes(image_bytes)
    return filename
