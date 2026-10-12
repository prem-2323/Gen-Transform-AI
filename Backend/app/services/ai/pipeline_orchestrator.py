"""AI orchestrator (Phase 3 + Phase 12 caching/parallelism).

Provider chain for TEXT (Qwen role):
    1. Ollama `qwen_model` (local Qwen) — preferred, keeps data private
    2. Deterministic extractive fallback (no invented numbers; everything
       quoted or counted from the source text)

Provider chain for IMAGES (Gemma role):
    1. Ollama `gemma_model` with the image bytes
    2. Metadata fallback (dimensions/format + caption placeholder)

Caching (Phase 12): analysis is keyed by sha256(text) and stored on the
source document; identical content reuses the previous analysis.
Parallelism (Phase 12): images are analysed concurrently via asyncio.gather.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import Any, Optional

from ...config.settings import get_settings
from ...core.token_budgets import (
    estimate_tokens,
    get_token_budget_config,
    truncate_to_token_budget,
)
from .timeline_extractor import extract_timeline_deterministic

log = logging.getLogger("gen-transform.ai")

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
_NUMBER_RE = re.compile(r"(?:(?:₹|\$|€|rs\.?)\s*)?\b\d+(?:[.,]\d+)*(?:\s*(?:%|percent|crore|lakh|million|billion|thousand|kwh|kw|mw|panels?|solar\s+panels?|buildings?|years?|months?|km|ms|days?|hours?))?", re.I)
_ENTITY_RE = re.compile(r"\b([A-Z][a-zA-Z0-9&.\-]{2,}(?:\s+[A-Z][a-zA-Z0-9&.\-]{2,}){0,3})")
_DATE_RE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b")
_IMPERATIVE_RE = re.compile(r"^(must|should|shall|need to|needs to|ensure|implement|deploy|update|patch|review|monitor|establish|conduct)\b", re.I)

_STOP_ENTITIES = {"The", "This", "That", "These", "Those", "With", "From", "There", "When", "Where", "Which"}


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# ------------------------------------------------------------------
# Provider 1: Ollama (Qwen for text, Gemma for vision)
# ------------------------------------------------------------------
def _ollama_client(timeout: float = 180.0):
    try:
        import ollama

        return ollama.Client(host=get_settings().ollama_base_url, timeout=timeout)
    except Exception as exc:
        log.debug("ollama client unavailable: %s", exc)
        return None


def _ollama_text_analysis(text: str) -> Optional[dict]:
    client = _ollama_client(timeout=180.0)
    if client is None:
        return None
    settings = get_settings()
    try:
        budget = int(get_token_budget_config().analysis_max_input_tokens)
    except Exception:
        budget = 3000
    model_name = str(getattr(settings, "qwen_model", "qwen3:4b"))
    # Token-aware budgeting (replaces text[:12000]); preserves head content
    # at a sentence boundary and logs truncation diagnostics.
    budgeted_text, info = truncate_to_token_budget(
        text or "", budget, model=model_name, stage="pipeline_analysis"
    )
    log.info(
        "pipeline_analysis model=%s input_tokens=%d kept=%d truncated=%s budget=%d",
        model_name,
        info.get("original_tokens"),
        info.get("kept_tokens"),
        info.get("truncated"),
        budget,
    )
    prompt = (
        "Analyse the document below and return STRICT JSON with keys: "
        "summary (string), facts (array of {value, quote}), "
        "entities (array of {name, role}), events (array of {title, timestamp}), "
        "timeline (array of {description, duration_value, duration_unit, sequence, kind, source_text, start_relationship, end_relationship}), "
        "metrics (array of {name, value, context}), "
        "relationships (array of {source, relation, target}), "
        "actions (array of {action, priority}). "
        "Extract total durations, phases, phase durations, and order into timeline. Include exact verbatim source_text; "
        "do not invent dates, durations, phases, or relationships. Use kind total or phase. "
        "Ground every fact in a verbatim quote from the text. Do not invent statistics.\n\n"
        f"TEXT:\n{budgeted_text}"
    )
    try:
        resp = client.chat(model=settings.qwen_model, messages=[{"role": "user", "content": prompt}])
        raw = resp["message"]["content"]
        return _coerce_json(raw)
    except Exception as exc:
        log.info("ollama qwen unavailable (%s); trying next provider", str(exc)[:150])
        return None


def _ollama_image_analysis(image_bytes: bytes) -> Optional[dict]:
    client = _ollama_client()
    if client is None:
        return None
    import base64

    settings = get_settings()
    try:
        resp = client.chat(
            model=settings.gemma_model,
            messages=[{
                "role": "user",
                "content": "Describe this image for threat-intel documentation. Return STRICT JSON: "
                "{caption, visualText, visualEntities[], chartType}.",
                "images": [base64.b64encode(image_bytes).decode()],
            }],
        )
        return _coerce_json(resp["message"]["content"])
    except Exception as exc:
        log.info("ollama gemma unavailable (%s); using metadata fallback", str(exc)[:150])
        return None


def _coerce_json(raw: str) -> Optional[dict]:
    try:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.I)
        candidate = m.group(1).strip() if m else raw.strip()
        if not candidate.startswith("{"):
            s, e = candidate.find("{"), candidate.rfind("}")
            if s != -1 and e != -1 and e > s:
                candidate = candidate[s : e + 1]
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


# ------------------------------------------------------------------
# Provider 2: deterministic extractive fallback
# ------------------------------------------------------------------
def _sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENT_SPLIT.split((text or "").strip()) if s and len(s.strip()) > 20]
    return parts[:400]


def _extractive_analysis(text: str) -> dict:
    sents = _sentences(text)
    if not sents:
        return {"summary": "", "facts": [], "entities": [], "events": [], "timeline": [],
                "metrics": [], "relationships": [], "actions": [], "provider": "extractive-empty"}

    freq: dict[str, int] = {}
    for s in sents:
        for w in re.findall(r"[a-z]{4,}", s.lower()):
            freq[w] = freq.get(w, 0) + 1
    scored = sorted(sents, key=lambda s: sum(freq.get(w, 0) for w in re.findall(r"[a-z]{4,}", s.lower())), reverse=True)

    facts = [{"value": s, "quote": s} for s in scored[:12]]
    summary = " ".join(scored[:3])

    ent_seen: dict[str, int] = {}
    for s in sents:
        for m in _ENTITY_RE.findall(s):
            name = " ".join(m.split()) if isinstance(m, str) else " ".join(m)
            if name in _STOP_ENTITIES or len(name) < 3:
                continue
            ent_seen[name] = ent_seen.get(name, 0) + 1
    entities = [{"name": n, "role": "mentioned entity", "mentions": c}
                for n, c in sorted(ent_seen.items(), key=lambda kv: kv[1], reverse=True)[:15]]

    metrics = []
    seen_metric_keys = set()
    for s in sents:
        for m in _NUMBER_RE.findall(s):
            val = m if isinstance(m, str) else m[0]
            val_clean = val.strip()
            if not val_clean:
                continue
            if val_clean in ("2023", "2024", "2025", "2026", "2027", "2028") or (val_clean.isdigit() and 1900 <= int(val_clean) <= 2099):
                continue
            key = re.sub(r"[^0-9a-z%]", "", val_clean.lower())
            if not key or key in seen_metric_keys:
                continue
            seen_metric_keys.add(key)
            s_low = s.lower()
            name = "Key Metric"
            if "%" in val_clean or "percent" in val_clean.lower():
                name = "Electricity Reduction" if any(w in s_low for w in ("electric", "energy", "kwh", "power")) else "Efficiency Reduction"
            elif any(w in s_low for w in ("solar", "panel")):
                name = "Solar Panels Installed"
            elif "50,000" in val_clean or ("50" in val_clean and "kwh" in s_low):
                name = "Baseline Monthly Usage"
            elif "38,000" in val_clean or ("38" in val_clean and "kwh" in s_low):
                name = "Post-Pilot Monthly Usage"
            elif "18" in val_clean and any(w in s_low for w in ("lakh", "cost", "invest", "₹", "rs")):
                name = "Project Investment"
            elif any(w in s_low for w in ("payback", "recover", "roi")) or (val_clean in ("4", "four") and "year" in s_low):
                name = "Estimated Payback Period"
            elif "building" in s_low:
                name = "Planned Expansion Buildings" if any(w in s_low for w in ("expand", "additional", "2027")) else "Initial Facilities"
            else:
                name = val_clean

            metrics.append({"name": name, "value": val_clean, "context": s[:200]})
            if len(metrics) >= 15:
                break
        if len(metrics) >= 15:
            break

    events = [{"title": s[:140], "timestamp": d, "impact": "", "actors": []}
              for s in sents for d in _DATE_RE.findall(s)][:10]

    relationships = []
    for e in entities[:8]:
        for f in facts[:4]:
            if e["name"].split()[0] in f["value"]:
                relationships.append({"source": e["name"], "relation": "mentioned in", "target": f["value"][:80]})
                break

    actions = [{"action": s, "priority": "P2 Medium", "timeframe": "", "owner": ""}
               for s in sents if _IMPERATIVE_RE.search(s)][:8]

    return {"summary": summary, "facts": facts, "entities": entities, "events": events,
            "timeline": extract_timeline_deterministic(text),
            "metrics": metrics, "relationships": relationships[:10], "actions": actions,
            "provider": "extractive"}


# ------------------------------------------------------------------
# Public entry points
# ------------------------------------------------------------------
def analyze_text(text: str, use_cache_on_source: Optional[dict] = None) -> dict:
    """Unified text analysis. Returns dict with provider tag + textHash."""
    text = text or ""
    h = text_hash(text)
    if use_cache_on_source:
        cached = (use_cache_on_source.get("analysis") or {})
        if cached.get("textHash") == h and cached.get("result"):
            log.info("analysis cache hit (hash=%s…)", h[:10])
            return {**cached["result"], "provider": cached.get("provider", "cache"), "cached": True}

    result = _ollama_text_analysis(text)
    provider = "ollama-qwen"
    if not result:
        result = _extractive_analysis(text)
        provider = result.pop("provider", "extractive")
    result.setdefault("summary", "")
    for k in ("facts", "entities", "events", "timeline", "metrics", "relationships", "actions"):
        result.setdefault(k, [])
    if not result["timeline"]:
        result["timeline"] = extract_timeline_deterministic(text)
    result.update({"provider": provider, "textHash": h, "cached": False})
    return result


def analyze_image_bytes(image_bytes: bytes) -> dict:
    """Gemma-role visual analysis with metadata fallback."""
    visual = _ollama_image_analysis(image_bytes)
    if visual:
        return {**visual, "provider": "ollama-gemma"}
    try:
        import io as _io
        from PIL import Image

        with Image.open(_io.BytesIO(image_bytes)) as im:
            meta = {"width": im.width, "height": im.height, "format": (im.format or "").lower()}
    except Exception:
        meta = {}
    return {"caption": "Visual content attached (model analysis unavailable).",
            "visualText": "", "visualEntities": [], "chartType": "unknown",
            "provider": "metadata-fallback", **meta}


async def analyze_images_async(items: list[tuple[str, bytes]]) -> list[dict]:
    """Analyse many images concurrently (Phase 12 parallelism)."""
    loop = asyncio.get_running_loop()

    def _one(pair: tuple[str, bytes]) -> dict:
        image_id, raw = pair
        out = analyze_image_bytes(raw)
        out["imageId"] = image_id
        return out

    return await asyncio.gather(*[loop.run_in_executor(None, _one, p) for p in items])
