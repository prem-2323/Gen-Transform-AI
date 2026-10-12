from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from ...models.deliverable import TransformationConfig
from ..ai.prompts import OUTPUT_INSTRUCTIONS


def format_uckr_context(uckr: Dict[str, Any]) -> str:
    """Renders UCKR knowledge items into a compact, structured representation."""
    lines: List[str] = []
    lines.append(f"TITLE: {uckr.get('title', 'Knowledge Brief')}")
    if uckr.get("summary"):
        lines.append(f"SUMMARY: {uckr.get('summary')}")
    lines.append("")

    # Facts
    facts = uckr.get("facts", [])
    lines.append(f"FACTS ({len(facts)} items):")
    for idx, f in enumerate(facts, 1):
        fid = f.get("factId", f.get("id", f"fact_{idx:03d}"))
        stmt = f.get("statement", f.get("value", f.get("text", "")))
        ftype = f.get("type", "fact")
        lines.append(f"  [{fid}] ({ftype}): {stmt}")
    lines.append("")

    # Entities
    entities = uckr.get("entities", [])
    lines.append(f"ENTITIES ({len(entities)} items):")
    for idx, e in enumerate(entities, 1):
        eid = e.get("entityId", f.get("id", f"entity_{idx:03d}"))
        name = e.get("canonicalName", e.get("name", ""))
        etype = e.get("type", e.get("category", "ENTITY"))
        aliases = e.get("aliases", [])
        alias_str = f" (Aliases: {', '.join(aliases)})" if aliases else ""
        lines.append(f"  [{eid}] {name} ({etype}){alias_str}")
    lines.append("")

    # Events
    events = uckr.get("events", [])
    if events:
        lines.append(f"EVENTS ({len(events)} items):")
        for idx, ev in enumerate(events, 1):
            evid = ev.get("eventId", f.get("id", f"event_{idx:03d}"))
            evtype = ev.get("eventType", "EVENT")
            desc = ev.get("description", ev.get("title", ""))
            date = ev.get("date", ev.get("timestamp", "N/A"))
            lines.append(f"  [{evid}] {evtype}: {desc} (Date: {date})")
        lines.append("")

    # Metrics
    metrics = uckr.get("metrics", [])
    if metrics:
        lines.append(f"METRICS ({len(metrics)} items):")
        for idx, m in enumerate(metrics, 1):
            mid = m.get("metricId", f.get("id", f"metric_{idx:03d}"))
            val = m.get("value", "")
            unit = m.get("unit", "")
            ctx = m.get("context", "")
            lines.append(f"  [{mid}] {val} {unit} — Context: {ctx}")
        lines.append("")

    # Claims
    claims = uckr.get("claims", [])
    if claims:
        lines.append(f"CLAIMS ({len(claims)} items):")
        for idx, c in enumerate(claims, 1):
            cid = c.get("claimId", f.get("id", f"claim_{idx:03d}"))
            stmt = c.get("statement", c.get("claim", ""))
            attr = c.get("attribution", "Source")
            lines.append(f"  [{cid}] {stmt} (Attribution: {attr})")
        lines.append("")

    # Actions
    actions = uckr.get("actions", [])
    if actions:
        lines.append(f"ACTIONS ({len(actions)} items):")
        for idx, a in enumerate(actions, 1):
            aid = a.get("actionId", f.get("id", f"action_{idx:03d}"))
            act = a.get("action", a.get("text", ""))
            actor = a.get("actor", a.get("owner", ""))
            status = a.get("status", a.get("priority", "RECOMMENDED"))
            lines.append(f"  [{aid}] {act} (Actor: {actor}, Status: {status})")
        lines.append("")

    # Relationships
    relationships = uckr.get("relationships", [])
    if relationships:
        lines.append(f"RELATIONSHIPS ({len(relationships)} items):")
        for idx, r in enumerate(relationships, 1):
            rid = r.get("relationshipId", f.get("id", f"rel_{idx:03d}"))
            src = r.get("sourceEntityId", r.get("source", ""))
            rel = r.get("relationshipType", r.get("relation", "RELATED_TO"))
            tgt = r.get("targetEntityId", r.get("target", ""))
            lines.append(f"  [{rid}] {src} -> {rel} -> {tgt}")
        lines.append("")

    return "\n".join(lines)


def get_schema_for_type(dtype: str) -> str:
    """Returns the JSON schema specification for the given deliverable type."""
    normalized_type = dtype.lower()
    if normalized_type in ("linkedin", "li"):
        return json.dumps({
            "title": "Concise post headline",
            "body": "Multi-paragraph post formatted for LinkedIn with spacing and bullet points",
            "content": "Professional LinkedIn post text with an engaging opening, clear paragraphs, and relevant hashtags.",
            "hashtags": ["#AgriTech", "#Innovation"],
            "usedFactIds": ["fact_001", "fact_002"]
        }, indent=2)
    elif normalized_type in ("x", "twitter"):
        return json.dumps({
            "content": "Complete, concise X/Twitter post or thread text.",
            "posts": [
                {
                    "postNumber": 1,
                    "text": "1/3 First tweet in thread containing key hook and findings (<=280 chars)...",
                    "usedFactIds": ["fact_001"]
                },
                {
                    "postNumber": 2,
                    "text": "2/3 Second tweet detailing impact metrics (<=280 chars)...",
                    "usedFactIds": ["fact_002"]
                },
                {
                    "postNumber": 3,
                    "text": "3/3 Concluding takeaways and recommendations (<=280 chars)...",
                    "usedFactIds": []
                }
            ]
        }, indent=2)
    elif normalized_type in ("summary", "executive_summary"):
        return json.dumps({
            "title": "Executive Summary Title",
            "summary": "High-level strategic briefing paragraph",
            "content": "Concise, grounded summary derived strictly from the source text.",
            "keyFindings": ["Finding 1 with exact numbers", "Finding 2"],
            "keyRisks": ["Strategic risk 1", "Operational risk 2"],
            "recommendedActions": ["Immediate mitigation step 1", "Strategic policy change 2"],
            "usedFactIds": ["fact_001", "fact_002"]
        }, indent=2)
    elif normalized_type in ("advisory", "advisory_memo"):
        return json.dumps({
            "title": "Security / Technical Advisory Title",
            "severity": "HIGH",
            "summary": "Technical overview of the advisory",
            "content": "CONFIDENTIAL - ADVISORY MEMO\n\nSubject: ...\n\n1. EXECUTIVE SUMMARY\n...\n2. KEY FINDINGS\n...\n3. KEY RISKS & CONSIDERATIONS\n...\n4. RECOMMENDATIONS\n...\n5. IMPLEMENTATION / TIMELINE\n...\n6. COST / RESOURCE REQUIREMENTS\n...\n7. NEXT STEPS\n...\n8. CONCLUSION\n...",
            "affectedEntities": ["System A", "Product B"],
            "observations": ["Technical observation 1", "Technical observation 2"],
            "recommendations": ["Remediation step 1", "Patch requirement 2"],
            "references": ["Ref-001", "Source Document Ref"],
            "usedFactIds": ["fact_001", "fact_002"]
        }, indent=2)
    elif normalized_type in ("email", "announcement"):
        return json.dumps({
            "content": "Subject: [Engaging Email Subject]\n\nDear Team / Partners,\n\n[Body text with key announcement points, executive takeaways, call to action, and formal sign-off]."
        }, indent=2)
    elif normalized_type in ("infographic", "infographics"):
        return json.dumps({
            "title": "Headline derived strictly from source",
            "main_message": "Core takeaway message from source",
            "key_statistics": [
                {
                    "value": "98.90%",
                    "label": "CatBoost Classification Accuracy"
                }
            ],
            "sections": [
                {
                    "heading": "Section Heading",
                    "content": "Section Content derived from source"
                }
            ],
            "supporting_text": "Contextual summary from source",
            "visual_hierarchy": "Guidance on primary vs secondary visual focus areas",
            "icon_recommendations": ["cpu", "activity"],
            "color_recommendations": ["#10B981", "#6366F1"],
            "layout_recommendation": "Vertical timeline / process flow",
            "usedFactIds": ["fact_001", "fact_002"]
        }, indent=2)
    elif normalized_type in ("presentation", "deck", "slides"):
        return json.dumps({
            "presentation_title": "Main Presentation Title",
            "subtitle": "Subtitle or Deck Summary",
            "slides": [
                {
                    "slide_number": 1,
                    "title": "Title Slide Title",
                    "layout": "title",
                    "subtitle": "Cover Subtitle",
                    "content": [],
                    "speaker_notes": "Welcome audience to the presentation.",
                    "visual_recommendation": "Modern graphic concept",
                    "usedFactIds": ["fact_001"]
                },
                {
                    "slide_number": 2,
                    "title": "Key Market Insights",
                    "layout": "bullet_points",
                    "content": [
                        "Key insight bullet point 1",
                        "Key insight bullet point 2"
                    ],
                    "speaker_notes": "Detailed spoken narration for this slide.",
                    "visual_recommendation": "Bar chart comparing key growth metrics",
                    "usedFactIds": ["fact_002"]
                },
                {
                    "slide_number": 3,
                    "title": "Strategic Roadmap",
                    "layout": "two_column",
                    "column_left": ["Action step 1", "Action step 2"],
                    "column_right": ["Expected outcome 1", "Expected outcome 2"],
                    "speaker_notes": "Explain how operational actions lead to outcomes.",
                    "visual_recommendation": "Two-column grid layout with accent borders",
                    "usedFactIds": []
                }
            ]
        }, indent=2)
    elif normalized_type in ("video_script", "video"):
        return json.dumps({
            "video_title": "Catchy professional title derived strictly from source content",
            "duration": "60 seconds",
            "storyboard": [
                {
                    "scene": 1,
                    "duration": "0-10 sec",
                    "visuals": "Detailed description of B-roll or visual elements matching source topic",
                    "narration": "Voiceover script text for this scene derived strictly from source",
                    "on_screen_text": "Concise key text callout",
                    "subtitle": "Subtitle text for accessibility",
                    "transition": "Fade to next scene",
                    "usedFactIds": ["fact_001"]
                }
            ],
            "music_recommendation": "Suggested background music genre, tempo, and mood",
            "voice_over_direction": "Tone, pacing, emotion, and accent guidance for voiceover",
            "thumbnail_recommendation": "Description for engaging video thumbnail concept"
        }, indent=2)
    return "{}"


def build_transformation_prompt(
    dtype: str,
    uckr: Dict[str, Any],
    cfg: TransformationConfig,
    source_content: Optional[str] = None,
) -> str:
    """Builds a complete, rigorous RFTC prompt for the LLM using OUTPUT_INSTRUCTIONS rules."""
    context = format_uckr_context(uckr)
    normalized_type = dtype.lower()
    schema = get_schema_for_type(dtype)

    # Get specific output instruction rules
    rule_key = "summary" if normalized_type in ("summary", "executive_summary") else (
        "twitter" if normalized_type in ("x", "twitter") else (
            "video_script" if normalized_type in ("video", "video_script") else (
                "presentation" if normalized_type in ("presentation", "deck", "slides") else (
                    "infographic" if normalized_type in ("infographic", "infographics") else (
                        "advisory" if normalized_type in ("advisory", "advisory_memo") else (
                            "email" if normalized_type in ("email", "announcement") else "linkedin"
                        )
                    )
                )
            )
        )
    )
    instruction_text = OUTPUT_INSTRUCTIONS.get(rule_key, "")

    lang_constraint = ""
    if cfg.language and cfg.language.strip().lower() not in ("english", "en"):
        lang_constraint = f"\n5. MANDATORY TARGET LANGUAGE: The entire content (all titles, headlines, summaries, hooks, call to action, descriptions, bullet points, recommendations, narration, notes, and text values) MUST BE WRITTEN FLUENTLY IN {cfg.language.upper()} (e.g. if Tamil, write in Tamil script தமிழ்; if Hindi, write in Devanagari script हिन्दी). Do NOT output English content text when {cfg.language} is requested. JSON structural keys must remain in English."

    # If video_script format template has placeholder variables, substitute them
    if rule_key == "video_script" and "{source_content}" in instruction_text:
        _raw_src = source_content or uckr.get("summary") or context
        try:
            from ...core.token_budgets import truncate_to_token_budget as _trunc

            src_text, _ = _trunc(str(_raw_src or "")[:8000], 1500, model="transform", stage="video_src")
        except Exception:
            src_text = str(_raw_src or "")[:2000]
        instruction_text = instruction_text.format(
            source_content=src_text,
            uckr_facts=context,
            target_audience=cfg.audience,
            requested_duration="60 seconds",
        )

    prompt = f"""[ROLE]
You are a senior communications and intelligence transformation specialist. Your mission is to generate professional {dtype.upper()} deliverables derived EXCLUSIVELY from the canonical Unified Content Knowledge Representation (UCKR) provided below.

[TASK]
Generate a complete, high-quality '{dtype}' output matching the user's configuration parameters:
- Audience: {cfg.audience}
- Tone: {cfg.tone}
- Language: {cfg.language}
- Detail Level: {cfg.detailLevel}
- Objective: {cfg.objective}

[SPECIFIC OUTPUT FORMAT RULES & INSTRUCTIONS]
{instruction_text}

[REFERENCE KNOWLEDGE (CANONICAL UCKR)]
{context}

[UNIVERSAL SOURCE-GROUNDED CONSTRAINTS]
1. SOURCE-FIRST AUTHORITY: The provided UCKR is the primary authority. Do not replace source information with general model knowledge or assume missing facts.
2. ZERO HALLUCINATIONS: Never invent statistics, metrics, dates, names, organizations, users, performance numbers, revenue, cost, or benefits.
3. PRESERVE NUMBERS, UNITS & DATES: Exact numbers, units (e.g., tons, %, ₹, kg, ms), dates, and version numbers must remain strictly unaltered.
4. NO UNSUPPORTED CAPABILITY CLAIMS: Never convert a proposed capability or concept into a proven result (e.g., "designed to clean" != "cleaned 100 tons").
5. GROUNDED PROVENANCE: Every fact or metric used MUST include its exact fact ID (e.g. "fact_001", "fact_002") in `usedFactIds`.
6. UNCERTAINTY HANDLING: If an item is not specified in the source, use "Not specified in the source." DO NOT GUESS.
7. FAIL-CLOSED PRINCIPLE: Creativity must never override source truth. If verification fails, output will be regenerated.
8. JSON FORMAT ONLY: Output ONLY valid, parsable JSON matching the schema below. Do not wrap in conversational preamble.{lang_constraint}

[TARGET JSON SCHEMA]
```json
{schema}
```
"""
    return prompt

