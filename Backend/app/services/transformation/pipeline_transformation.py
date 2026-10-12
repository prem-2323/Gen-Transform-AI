"""Transformation engine (Phase 5) — outputs are generated FROM the UCKR,
never independently from the raw document.

Types: linkedin, twitter (X), advisory, executive_summary, infographic,
       presentation, video
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import HTTPException
from ...storage.repository import get_repository
from ...utils.helpers import utcnow_iso
from ..uckr import pipeline_uckr as uckr_service

log = logging.getLogger("gen-transform.transform")

VALID_TYPES = ("linkedin", "twitter", "advisory", "executive_summary",
               "infographic", "presentation", "video")


def _owner_filter(uid: str) -> dict:
    return {"$or": [{"userId": uid}, {"firebaseUid": uid}]}


def _top(uckr: dict, key: str, n: int) -> list[dict]:
    return (uckr.get(key) or [])[:n]


def _fact_values(uckr: dict, n: int = 6) -> list[str]:
    return [f["value"] for f in _top(uckr, "facts", n) if f.get("value")]


def _mark_used(uckr: dict, dtype: str) -> None:
    for f in uckr.get("facts", [])[:12]:
        used = f.setdefault("usedInDeliverables", [])
        if dtype not in used:
            used.append(dtype)


from .templates import generate_deterministic_deliverable, translate_text, _get_ui_labels, _normalize_lang
from ...models.deliverable import TransformationConfig


def _translate_str(text: str, lang: str) -> str:
    return translate_text(text, lang)


def _gen(dtype: str, uckr: dict, cfg: dict) -> dict:
    type_map = {"x": "twitter", "video_script": "video", "slides": "presentation", "summary": "executive_summary"}
    gen_type = type_map.get(dtype, dtype)
    
    cfg_obj = TransformationConfig(
        audience=cfg.get("audience", "executive"),
        tone=cfg.get("tone", "professional"),
        language=cfg.get("language", "English"),
        detailLevel=cfg.get("detailLevel", "medium"),
        objective=cfg.get("objective", "awareness"),
    ) if isinstance(cfg, dict) else cfg

    return generate_deterministic_deliverable(gen_type, uckr, cfg_obj)



def generate(
    uid: str, project_id: str, uckr_version: Optional[int], dtype: str,
    config: Optional[dict] = None, source_id: Optional[str] = None,
) -> dict:
    """Generate ONE deliverable from the project's UCKR and persist it."""
    from ..projects.project_service import get_project

    if dtype not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Unknown type. Valid: {list(VALID_TYPES)}.")
    project = get_project(project_id, uid)
    uckr_repo = get_repository("uckr")
    filt: dict[str, Any] = {"projectId": project_id, **_owner_filter(uid)}
    if source_id:
        filt["sourceId"] = source_id
    if uckr_version is not None:
        filt["version"] = uckr_version
    uckr = uckr_repo.find_one(filt, sort=[("version", -1)], projection={"_id": 0})
    if not uckr:
        raise HTTPException(status_code=404, detail="No UCKR found — run analysis first.")

    from .quality_gate import evaluate_deliverable_quality

    content = _gen(dtype, uckr, config or {})
    _mark_used(uckr, dtype)
    now = utcnow_iso()
    deliv_id = f"del-{uuid.uuid4().hex[:12]}"
    used_facts = [
        f.get("factId") or f.get("id")
        for f in uckr.get("facts", [])[:5]
        if f.get("factId") or f.get("id")
    ]
    source_text = uckr.get("sourceText") or " ".join([f.get("value", "") for f in uckr.get("facts", [])])
    quality_res = evaluate_deliverable_quality(dtype, content, source_text, uckr)

    doc = {
        "id": deliv_id,
        "deliverableId": deliv_id,
        "userId": uid,
        "projectId": project_id,
        "sourceId": uckr.get("sourceId", ""),
        "uckrVersion": uckr.get("version", 1),
        "type": dtype,
        "content": content,
        "usedFactIds": used_facts,
        "configuration": config or {"audience": "executive", "tone": "professional",
                                     "language": "English", "detailLevel": "medium"},
        "status": "completed" if quality_res.passed else "needs_review",
        "quality": quality_res.to_dict(),
        "qualityScore": quality_res.overall_quality_score,
        "groundingScore": quality_res.grounding_score,
        "qualityStatus": quality_res.status,
        "storagePath": None,
        "createdAt": now,
        "updatedAt": now,
    }
    deliv_repo = get_repository("deliverables")
    deliv_repo.update_one({"id": deliv_id}, {"$set": doc}, upsert=True)
    uckr_repo.update_one(
        {"uckrId": uckr.get("uckrId")}, {"$set": {"facts": uckr.get("facts", [])}}
    )
    log.info("deliverable generated project=%s type=%s uckrV=%s", project_id, dtype, doc["uckrVersion"])
    return doc


def generate_many(
    uid: str, project_id: str, types: list[str], config: Optional[dict] = None,
    source_id: Optional[str] = None,
) -> list[dict]:
    """Generate all requested deliverables from the SAME UCKR version (Phase 5 fan-out)."""
    from ..projects.project_service import get_project

    get_project(project_id, uid)
    uckr_repo = get_repository("uckr")
    filt: dict[str, Any] = {"projectId": project_id, **_owner_filter(uid)}
    if source_id:
        filt["sourceId"] = source_id
    uckr = uckr_repo.find_one(filt, sort=[("version", -1)], projection={"_id": 0})
    if not uckr:
        raise HTTPException(status_code=404, detail="No UCKR found — run analysis first.")
    out = [
        generate(uid, project_id, int(uckr.get("version", 1)), t, config, source_id)
        for t in types
    ]
    try:
        from ..projects.project_service import update_project

        snapshot = {d["type"]: d["content"] for d in out}
        update_project(project_id, {"deliverables": snapshot, "status": "completed"}, uid)
    except Exception as exc:
        log.warning("project deliverables snapshot skipped: %s", exc)
    return out


def list_deliverables(uid: str, project_id: str) -> list[dict]:
    from ..projects.project_service import get_project

    get_project(project_id, uid)
    deliv_repo = get_repository("deliverables")
    return deliv_repo.find({"projectId": project_id, **_owner_filter(uid)}, sort=[("createdAt", -1)], projection={"_id": 0})


# --- legacy shim (kept for old route shape) ---
def run_pipeline(source: dict, config: dict, selected_outputs: list) -> dict:
    text = (source or {}).get("extractedText", "") or (source or {}).get("text", {}).get("content", "")
    if not text.strip():
        return {"status": "failed", "error": "No source text provided.", "deliverables": {}}
    analysis = __import__("app.services.ai.pipeline_orchestrator", fromlist=["analyze_text"]).analyze_text(text)
    uckr = uckr_service.build_uckr(
        {"pages": [{"pageNumber": 1, "text": text}], "document": {"name": (source or {}).get("name", "source")}},
        analysis, uid="legacy", project_id="legacy", source_id="legacy",
    )
    deliverables = {}
    for t in (selected_outputs or [])[:7]:
        if t in VALID_TYPES:
            deliverables[t] = _gen(t, uckr, config or {})
    return {"status": "completed", "deliverables": deliverables,
            "analysis": {"summary": analysis.get("summary", "")}, "uckr": uckr}

