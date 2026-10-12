"""Transformation Service Orchestrator (Phase 6).

Transforms canonical UCKR into multiple communications deliverables:
- LinkedIn
- X (Twitter) Thread
- Executive Summary
- Technical Advisory
- Infographic Specification
- Presentation Slide Deck
- Explainer Video Script

Persists all generated outputs in `deliverables` repository with full provenance tracking.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from ...storage.repository import get_repository
from ...config.settings import get_settings
from ...models.deliverable import (
    DeliverableType,
    DeliverableRecord,
    TransformationConfig,
    TransformationRequest,
    TransformResponse,
)
from ...utils.helpers import utcnow_iso
from .prompt_builder import build_transformation_prompt
from .templates import generate_deterministic_deliverable
from .output_validator import validate_deliverable_output

log = logging.getLogger("gen-transform.transformation_service")


def _clean_json_str(raw: str) -> str:
    """Strip markdown code formatting blocks."""
    cleaned = raw.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
    return cleaned


def _call_qwen_for_deliverable(
    dtype: DeliverableType,
    uckr: Dict[str, Any],
    cfg: TransformationConfig,
) -> Optional[Dict[str, Any]]:
    """Invokes local Qwen model via Ollama if available."""
    settings = get_settings()
    if not settings.ollama_enabled:
        return None

    try:
        import ollama
        prompt = build_transformation_prompt(dtype, uckr, cfg)
        # Centralized per-deliverable output budget (preserves prior unbounded
        # behaviour by choosing a sized default instead of model maximum).
        try:
            from ...core.token_budgets import estimate_tokens, resolve_output_budget

            num_predict = int(resolve_output_budget(str(dtype), None))
            log.info(
                "transformation_generate type=%s prompt_tokens~%d num_predict=%d model=%s",
                dtype,
                int(estimate_tokens(prompt)),
                num_predict,
                settings.text_model,
            )
        except Exception:
            num_predict = {"executive_summary": 800, "advisory": 2048}.get(str(dtype), 2048)
        response = ollama.chat(
            model=settings.text_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional content transformation specialist. You must strictly output valid JSON adhering to the specified schema, without markdown conversational formatting.",
                },
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.2, "num_predict": int(num_predict)},
        )
        content_str = response.get("message", {}).get("content", "")
        cleaned = _clean_json_str(content_str)
        return json.loads(cleaned)
    except Exception as exc:
        log.warning("Ollama text generation skipped or failed (%s), using deterministic template fallback.", exc)
        return None


def generate_single_deliverable(
    dtype: DeliverableType,
    uckr: Dict[str, Any],
    cfg: TransformationConfig,
    user_uid: str,
    project_id: str,
    source_id: str,
) -> DeliverableRecord:
    """Generates, validates, and persists a single deliverable from UCKR."""
    from .quality_gate import evaluate_deliverable_quality

    source_text = uckr.get("sourceText") or " ".join([f.get("value", "") for f in uckr.get("facts", [])])

    # 1. Attempt AI generation or fallback to template
    raw_content = _call_qwen_for_deliverable(dtype, uckr, cfg)
    if raw_content and isinstance(raw_content, dict):
        quality_check = evaluate_deliverable_quality(str(dtype), raw_content, source_text, uckr)
        if not quality_check.passed:
            log.warning(
                "AI generation failed quality gate for %s (score=%.2f, flags=%s). Auto-repairing with quality engine.",
                dtype, quality_check.overall_quality_score, quality_check.flags
            )
            raw_content = generate_deterministic_deliverable(dtype, uckr, cfg)
    else:
        raw_content = generate_deterministic_deliverable(dtype, uckr, cfg)

    # 2. Validate content and fact grounding
    is_valid, errors, warnings, used_fact_ids = validate_deliverable_output(dtype, raw_content, uckr)
    quality_res = evaluate_deliverable_quality(str(dtype), raw_content, source_text, uckr)

    # 3. Associate citations for used facts
    uckr_citations = uckr.get("citations", [])
    attached_citations = []
    if uckr_citations:
        fact_id_set = set(used_fact_ids)
        for cit in uckr_citations:
            if cit.get("factId") in fact_id_set:
                attached_citations.append(cit)
        if not attached_citations and uckr_citations:
            attached_citations = uckr_citations[:2]

    deliverable_id = f"del_{uuid.uuid4().hex[:8]}"
    now = utcnow_iso()

    uckr_id_raw = uckr.get("_id") or uckr.get("id") or uckr.get("uckrId") or f"uckr_{source_id}"
    uckr_id_str = str(uckr_id_raw)

    doc = {
        "deliverableId": deliverable_id,
        "id": deliverable_id,
        "userId": user_uid,
        "projectId": project_id,
        "sourceId": source_id,
        "uckrId": uckr_id_str,
        "uckrVersion": uckr.get("version", 1),
        "type": dtype,
        "configuration": cfg.model_dump(),
        "content": raw_content,
        "usedFactIds": used_fact_ids,
        "citations": attached_citations,
        "status": "completed" if (is_valid and quality_res.passed) else ("needs_review" if is_valid else "failed"),
        "validation": {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
        },
        "quality": quality_res.to_dict(),
        "qualityScore": quality_res.overall_quality_score,
        "groundingScore": quality_res.grounding_score,
        "qualityStatus": quality_res.status,
        "createdAt": now,
        "updatedAt": now,
    }

    deliv_repo = get_repository("deliverables")
    deliv_repo.insert_one(doc)
    log.info("Persisted deliverable %s (%s) for project %s (status=%s, qualityScore=%.2f)", deliverable_id, dtype, project_id, doc["status"], quality_res.overall_quality_score)

    return DeliverableRecord.model_validate(doc)


def _project_filter(project_id: str, user_uid: str) -> Dict[str, Any]:
    return {
        "$and": [
            {"$or": [{"id": project_id}, {"projectId": project_id}]},
            {"$or": [{"userId": user_uid}, {"firebaseUid": user_uid}]},
        ]
    }


def transform_content(
    project_id: str,
    req: TransformationRequest,
    user: Dict[str, Any],
) -> TransformResponse:
    """Main transformation pipeline entrypoint for projects."""
    user_uid = user.get("uid") or user.get("userId") or user.get("firebaseUid")
    if not user_uid:
        raise HTTPException(status_code=401, detail="Authentication required.")

    # 1. Verify Project
    proj_repo = get_repository("projects")
    proj = proj_repo.find_one(_project_filter(project_id, user_uid), projection={"_id": 0})
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")

    # 2. Resolve Source ID
    source_id = req.sourceId
    if not source_id:
        src_repo = get_repository("sources")
        latest_source = src_repo.find_one({"projectId": project_id}, sort=[("createdAt", -1)], projection={"_id": 0})
        if latest_source:
            source_id = latest_source.get("sourceId") or latest_source.get("id")
    if not source_id:
        raise HTTPException(status_code=400, detail="No source ID specified and no sources found in project.")

    # 3. Load Canonical UCKR Document
    uckr_repo = get_repository("uckr")
    uckr_query: Dict[str, Any] = {"projectId": project_id, "sourceId": source_id}
    if req.uckrVersion:
        uckr_query["version"] = req.uckrVersion

    uckr_doc = uckr_repo.find_one(uckr_query, sort=[("version", -1)], projection={"_id": 0})

    if not uckr_doc:
        raise HTTPException(
            status_code=404,
            detail=f"Canonical UCKR not found for source '{source_id}'. Please run Phase 5 UCKR builder first.",
        )

    # 4. Generate all requested deliverables
    generated_deliverables: List[Dict[str, Any]] = []
    for dtype in req.outputTypes:
        rec = generate_single_deliverable(
            dtype=dtype,
            uckr=uckr_doc,
            cfg=req.configuration,
            user_uid=user_uid,
            project_id=project_id,
            source_id=source_id,
        )
        d_dict = rec.model_dump(by_alias=True)
        d_dict["id"] = str(d_dict.get("id") or d_dict.get("deliverableId"))
        generated_deliverables.append(d_dict)

    return TransformResponse(
        ok=True,
        projectId=project_id,
        sourceId=source_id,
        uckrVersion=uckr_doc.get("version", 1),
        deliverables=generated_deliverables,
    )


def get_project_deliverables(project_id: str, user: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Lists all deliverables for a project."""
    user_uid = user.get("uid") or user.get("userId") or user.get("firebaseUid")
    if not user_uid:
        raise HTTPException(status_code=401, detail="Authentication required.")

    proj_repo = get_repository("projects")
    proj = proj_repo.find_one(_project_filter(project_id, user_uid), projection={"_id": 0})
    if proj is None:
        raise HTTPException(status_code=403, detail="Project access forbidden.")

    deliv_repo = get_repository("deliverables")
    docs = deliv_repo.find({"projectId": project_id}, sort=[("createdAt", -1)], projection={"_id": 0})
    for doc in docs:
        doc["id"] = str(doc.get("id") or doc.get("deliverableId"))
    return docs


def get_single_deliverable(project_id: str, deliverable_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves a single deliverable by ID."""
    user_uid = user.get("uid") or user.get("userId") or user.get("firebaseUid")
    if not user_uid:
        raise HTTPException(status_code=401, detail="Authentication required.")

    proj_repo = get_repository("projects")
    proj = proj_repo.find_one(_project_filter(project_id, user_uid), projection={"_id": 0})
    if proj is None:
        raise HTTPException(status_code=403, detail="Project access forbidden.")

    deliv_repo = get_repository("deliverables")
    doc = deliv_repo.find_one(
        {"$or": [{"id": deliverable_id}, {"deliverableId": deliverable_id}], "projectId": project_id},
        projection={"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Deliverable not found.")
    doc["id"] = str(doc.get("id") or doc.get("deliverableId"))
    return doc


def delete_single_deliverable(project_id: str, deliverable_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    """Deletes a single deliverable."""
    user_uid = user.get("uid") or user.get("userId") or user.get("firebaseUid")
    if not user_uid:
        raise HTTPException(status_code=401, detail="Authentication required.")

    proj_repo = get_repository("projects")
    proj = proj_repo.find_one(_project_filter(project_id, user_uid), projection={"_id": 0})
    if proj is None:
        raise HTTPException(status_code=403, detail="Project access forbidden.")

    deliv_repo = get_repository("deliverables")
    deleted = deliv_repo.delete_many(
        {"$or": [{"id": deliverable_id}, {"deliverableId": deliverable_id}], "projectId": project_id}
    )
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Deliverable not found.")
    return {"ok": True, "deleted": deliverable_id}

