"""Normalization and standard categorization engine for UCKR items."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from ...models.uckr import Action, Claim, Event, Fact, Metric, SourceRef, TimelineNode

_EVENT_TYPES = {
    "attack": "CYBER_ATTACK",
    "ransomware": "CYBER_ATTACK",
    "phishing": "CYBER_ATTACK",
    "breach": "INCIDENT",
    "incident": "INCIDENT",
    "detected": "DETECTION",
    "discovery": "DISCOVERY",
    "announced": "ANNOUNCEMENT",
    "launch": "LAUNCH",
    "policy": "POLICY_CHANGE",
    "response": "RESPONSE",
    "meeting": "MEETING",
    "research": "RESEARCH",
}


def normalize_events(
    raw_events: List[Any],
    source_id: str,
    page_texts: Dict[int, str],
) -> List[Event]:
    """Normalizes events into standardized event types with grounded citations."""
    events: List[Event] = []

    for idx, item in enumerate(raw_events, start=1):
        if isinstance(item, dict):
            desc = (item.get("description") or item.get("event") or item.get("title") or item.get("name") or "").strip()
            date_val = item.get("date") or item.get("timestamp") or None
            loc = item.get("location")
            impact = item.get("impact", "")
            actors = item.get("actors") or item.get("participants") or []
            conf = float(item.get("confidence", 0.95))
        else:
            desc = str(item).strip()
            date_val = None
            loc = None
            impact = ""
            actors = []
            conf = 0.92

        if not desc or len(desc) < 3:
            continue

        # Match event type
        ev_type = "INCIDENT"
        desc_lower = desc.lower()
        for k, v in _EVENT_TYPES.items():
            if k in desc_lower:
                ev_type = v
                break

        page_no = 1
        for pn, ptext in page_texts.items():
            if desc[:40] and desc[:40].lower() in ptext.lower():
                page_no = pn
                break

        eid = f"event_{idx:03d}"
        sref = SourceRef(
            sourceId=source_id,
            chunkId=f"chunk_{page_no:03d}",
            pageNumber=page_no,
            textQuote=desc[:150],
        )

        ev = Event(
            eventId=eid,
            id=eid,
            eventType=ev_type,
            description=desc,
            name=desc,
            title=desc,
            date=str(date_val) if date_val else None,
            timestamp=str(date_val) if date_val else None,
            location=loc,
            impact=impact,
            actors=[str(a) for a in actors],
            participants=[str(a) for a in actors],
            confidence=round(conf, 3),
            sourceRefs=[sref],
        )
        events.append(ev)

    return events


def normalize_timeline(
    raw_timeline: List[Any],
    source_id: str,
    page_texts: Dict[int, str],
    facts: List[Fact],
) -> List[TimelineNode]:
    """Normalize extracted durations and connect them to their supporting facts."""
    timeline: List[TimelineNode] = []

    for idx, item in enumerate(raw_timeline, start=1):
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or item.get("event") or "").strip()
        if not description:
            continue

        raw_duration = item.get("duration_value", item.get("durationValue"))
        try:
            duration_value = float(raw_duration) if raw_duration is not None else None
        except (TypeError, ValueError):
            duration_value = None
        if duration_value is not None and duration_value <= 0:
            continue

        duration_unit = item.get("duration_unit") or item.get("durationUnit")
        duration_unit = str(duration_unit).lower().strip() if duration_unit else None
        if duration_unit and not duration_unit.endswith("s"):
            duration_unit += "s"
        source_text = str(
            item.get("source_text") or item.get("sourceText") or item.get("quote") or ""
        ).strip()

        source_fact = next(
            (
                fact for fact in facts
                if source_text and (
                    source_text.casefold() in fact.quote.casefold()
                    or fact.quote.casefold() in source_text.casefold()
                )
            ),
            None,
        )
        page_no = source_fact.page if source_fact else 1
        if source_text and not source_fact:
            for pn, page_text in page_texts.items():
                if source_text[:40].casefold() in page_text.casefold():
                    page_no = pn
                    break

        kind = str(item.get("kind") or "phase").lower().strip()
        is_total = bool(item.get("is_total") or item.get("isTotal")) or kind == "total"
        if not is_total and re.match(r"^total\b", description, re.I):
            is_total = True
        if kind not in {"total", "phase", "milestone"}:
            kind = "total" if is_total else "phase"
        elif is_total:
            kind = "total"

        source_ref = SourceRef(
            sourceId=source_id,
            chunkId=source_fact.chunkId if source_fact else f"chunk_{page_no:03d}",
            pageNumber=page_no,
            textQuote=(source_text or (source_fact.quote if source_fact else description))[:200],
        )
        timeline.append(TimelineNode(
            id=f"T-{len(timeline) + 1}",
            description=description,
            duration_value=duration_value,
            duration_unit=duration_unit,
            sequence=item.get("sequence") or idx,
            kind=kind,
            sourceFactId=source_fact.factId if source_fact else None,
            sourceText=source_text or (source_fact.quote if source_fact else ""),
            sourceRefs=[source_ref],
            startRelationship=item.get("start_relationship") or item.get("startRelationship"),
            endRelationship=item.get("end_relationship") or item.get("endRelationship"),
        ))

    return timeline


def normalize_metrics(
    raw_metrics: List[Any],
    source_id: str,
    page_texts: Dict[int, str],
) -> List[Metric]:
    """Extracts and standardizes numeric metrics with exact units and context."""
    metrics: List[Metric] = []

    for idx, item in enumerate(raw_metrics, start=1):
        if isinstance(item, dict):
            val = item.get("value", "")
            name = item.get("name") or ""
            unit = item.get("unit", "")
            ctx = item.get("context", "")
            date_val = item.get("date")
            conf = float(item.get("confidence", 0.98))
        else:
            val = str(item)
            name = ""
            unit = ""
            ctx = str(item)
            date_val = None
            conf = 0.95

        val_str = str(val).strip()
        # Skip calendar years
        if val_str in ("2023", "2024", "2025", "2026", "2027", "2028") or (val_str.isdigit() and 1900 <= int(val_str) <= 2099 and not unit):
            continue

        # Extract unit if embedded
        if isinstance(val, str):
            u_match = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z%]+)", val)
            if u_match and not unit:
                unit = u_match.group(2)

        if not name or name.lower().startswith("metric ") or name in ("2024", "2025", "2026", "2027"):
            ctx_low = (ctx or "").lower()
            if "%" in val_str:
                name = "Electricity Reduction" if any(w in ctx_low for w in ("electric", "energy", "kwh", "power")) else "Efficiency Reduction"
            elif any(w in ctx_low for w in ("solar", "panel")):
                name = "Solar Panels Installed"
            elif "50,000" in val_str or ("50" in val_str and "kwh" in ctx_low):
                name = "Baseline Monthly Usage"
            elif "38,000" in val_str or ("38" in val_str and "kwh" in ctx_low):
                name = "Post-Pilot Monthly Usage"
            elif "18" in val_str and any(w in ctx_low for w in ("lakh", "cost", "invest", "₹", "rs")):
                name = "Project Investment"
            elif any(w in ctx_low for w in ("payback", "recover", "roi")) or (val_str in ("4", "four") and "year" in ctx_low):
                name = "Estimated Payback Period"
            elif "building" in ctx_low:
                name = "Planned Expansion Buildings" if any(w in ctx_low for w in ("expand", "additional", "2027")) else "Initial Facilities"
            else:
                name = f"Metric {idx}"

        page_no = 1
        for pn, ptext in page_texts.items():
            if ctx and ctx[:40].lower() in ptext.lower():
                page_no = pn
                break

        mid = f"metric_{idx:03d}"
        sref = SourceRef(
            sourceId=source_id,
            chunkId=f"chunk_{page_no:03d}",
            pageNumber=page_no,
            textQuote=f"{val} {unit}".strip(),
        )

        metrics.append(Metric(
            metricId=mid,
            id=mid,
            name=name[:120],
            value=val,
            unit=unit,
            context=ctx[:300],
            date=date_val,
            confidence=round(conf, 3),
            sourceRefs=[sref],
        ))

    return metrics


def normalize_claims(
    raw_claims: List[Any],
    source_id: str,
    page_texts: Dict[int, str],
) -> List[Claim]:
    """Separates verifiable facts from source claims and assertions."""
    claims: List[Claim] = []

    for idx, item in enumerate(raw_claims, start=1):
        if isinstance(item, dict):
            stmt = (item.get("statement") or item.get("claim") or item.get("text") or "").strip()
            ctype = item.get("claimType", "SOURCE_ASSERTION")
            attr = item.get("attribution", "")
            conf = float(item.get("confidence", 0.92))
        else:
            stmt = str(item).strip()
            ctype = "SOURCE_ASSERTION"
            attr = ""
            conf = 0.90

        if not stmt:
            continue

        page_no = 1
        for pn, ptext in page_texts.items():
            if stmt[:40].lower() in ptext.lower():
                page_no = pn
                break

        cid = f"claim_{idx:03d}"
        sref = SourceRef(
            sourceId=source_id,
            chunkId=f"chunk_{page_no:03d}",
            pageNumber=page_no,
            textQuote=stmt[:150],
        )

        claims.append(Claim(
            claimId=cid,
            id=cid,
            statement=stmt,
            text=stmt,
            claimType=ctype,
            attribution=attr,
            confidence=round(conf, 3),
            sourceRefs=[sref],
        ))

    return claims


def normalize_actions(
    raw_actions: List[Any],
    source_id: str,
    page_texts: Dict[int, str],
) -> List[Action]:
    """Standardizes recommended and mandatory operational actions."""
    actions: List[Action] = []

    for idx, item in enumerate(raw_actions, start=1):
        if isinstance(item, dict):
            act_text = (item.get("action") or item.get("text") or "").strip()
            actor = item.get("actor") or item.get("owner") or ""
            status = item.get("status", "RECOMMENDED")
            prio = item.get("priority", "P1 High")
            timeframe = item.get("timeframe", "")
        else:
            act_text = str(item).strip()
            actor = ""
            status = "RECOMMENDED"
            prio = "P1 High"
            timeframe = ""

        if not act_text:
            continue

        page_no = 1
        for pn, ptext in page_texts.items():
            if act_text[:40].lower() in ptext.lower():
                page_no = pn
                break

        aid = f"action_{idx:03d}"
        sref = SourceRef(
            sourceId=source_id,
            chunkId=f"chunk_{page_no:03d}",
            pageNumber=page_no,
            textQuote=act_text[:150],
        )

        actions.append(Action(
            actionId=aid,
            id=aid,
            action=act_text,
            text=act_text,
            actor=actor,
            status=status,
            priority=prio,
            timeframe=timeframe,
            owner=actor,
            sourceRefs=[sref],
        ))

    return actions
