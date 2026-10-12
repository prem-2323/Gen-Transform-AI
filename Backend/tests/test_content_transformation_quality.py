"""Automated Test Suite for Content Transformation Quality and Multi-Dimensional Quality Gate.

Covers:
1. Substantive article/report across all 7 deliverable types (LinkedIn, Twitter, Advisory,
   Executive Summary, Infographic, Presentation, Video Script).
2. Instruction-only inputs handled honestly without fabricated findings.
3. Short source with insufficient evidence and explicit limitations.
4. Numerical facts and dates preservation.
5. Ambiguous or conflicting claims preservation.
6. Repetitive source content de-duplication.
7. Quality gate detection of redundancy and repetition penalties.
8. Separation of factual grounding from transformation quality.
9. Detection of ungrounded fabricated metrics.
10. Validation service integration and quality status.
"""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest
from app.services.transformation.source_analyzer import analyze_source_content, SourceProfile
from app.services.transformation.quality_gate import (
    evaluate_deliverable_quality,
    QualityGateResult,
    detect_instruction_leakage,
)
from app.services.transformation.templates import generate_deterministic_deliverable
from app.models.deliverable import TransformationConfig
from app.services.validation.validation_service import check_deliverable


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def substantive_source_text():
    return (
        "Modern cloud infrastructure teams increasingly adopt automated platform engineering. "
        "In a study of 450 enterprise organizations conducted in September 2024, internal developer platforms "
        "reduced lead time for changes by 64% and improved deployment frequency by 3.8x. "
        "However, organizations that adopted platforms without adequate team onboarding experienced "
        "a 28% drop in developer satisfaction during the initial six months. "
        "Platform engineering requires balancing self-service automation with continuous feedback loops. "
        "We recommend establishing dedicated platform product managers, setting clear golden paths, "
        "and tracking developer experience metrics quarterly."
    )


@pytest.fixture
def substantive_uckr(substantive_source_text):
    profile = analyze_source_content(substantive_source_text, fallback_title="Platform Engineering Study")
    facts = [{"id": f"f_{i}", "value": fact, "type": "Finding"} for i, fact in enumerate(profile.findings or profile.key_facts)]
    metrics = [{"id": f"m_{i}", "name": m.label, "value": m.value, "context": m.context} for i, m in enumerate(profile.empirical_metrics)]
    return {
        "title": profile.subject,
        "sourceText": substantive_source_text,
        "version": 1,
        "facts": facts,
        "metrics": metrics,
        "entities": [{"name": e} for e in profile.entities],
    }


@pytest.fixture
def default_config():
    return TransformationConfig(
        audience="executive",
        tone="professional",
        language="English",
        detailLevel="medium",
        objective="awareness",
    )


# ============================================================================
# 1. Substantive Article Across All 7 Deliverables
# ============================================================================

def test_substantive_article_linkedin(substantive_uckr, default_config, substantive_source_text):
    deliverable = generate_deterministic_deliverable("linkedin", substantive_uckr, default_config)

    assert "title" in deliverable
    assert "body" in deliverable
    assert "hashtags" in deliverable
    assert len(deliverable["hashtags"]) >= 2

    # Check anti-leakage: No procedural prompt echo or boilerplates
    body = deliverable["body"].lower()
    assert "fastapi" not in body
    assert "react" not in body
    assert "7 output formats" not in body
    assert "smart india hackathon" not in body
    assert "generate 5 tweets" not in body

    # Quality Gate evaluation
    q_res = evaluate_deliverable_quality("linkedin", deliverable, substantive_source_text, substantive_uckr)
    assert q_res.passed is True
    assert q_res.overall_quality_score >= 80.0
    assert q_res.instruction_leakage_detected is False


def test_substantive_article_twitter(substantive_uckr, default_config, substantive_source_text):
    deliverable = generate_deterministic_deliverable("twitter", substantive_uckr, default_config)

    assert "posts" in deliverable
    posts = deliverable["posts"]
    assert 2 <= len(posts) <= 7

    # Check Twitter format constraints: <= 280 characters per tweet
    for post in posts:
        text = post.get("text", "")
        assert len(text) <= 280, f"Tweet exceeds 280 chars: {text}"
        assert len(text) > 20, "Tweet too short"

    # Distinct content across posts
    texts = [p["text"] for p in posts]
    assert len(set(texts)) == len(texts), "Duplicate tweets detected"

    q_res = evaluate_deliverable_quality("twitter", deliverable, substantive_source_text, substantive_uckr)
    assert q_res.passed is True
    assert q_res.repetition_penalty == 0.0


def test_substantive_article_advisory(substantive_uckr, default_config, substantive_source_text):
    deliverable = generate_deterministic_deliverable("advisory", substantive_uckr, default_config)

    required_keys = ["title", "severity", "situation", "observations", "recommendations"]
    for k in required_keys:
        assert k in deliverable, f"Missing key in advisory: {k}"

    assert len(deliverable["observations"]) >= 2
    assert len(deliverable["recommendations"]) >= 1

    q_res = evaluate_deliverable_quality("advisory", deliverable, substantive_source_text, substantive_uckr)
    assert q_res.passed is True
    assert q_res.overall_quality_score >= 80.0


def test_substantive_article_executive_summary(substantive_uckr, default_config, substantive_source_text):
    deliverable = generate_deterministic_deliverable("executive_summary", substantive_uckr, default_config)

    assert "title" in deliverable
    assert "summary" in deliverable
    assert "keyFindings" in deliverable
    assert "recommendedActions" in deliverable

    assert len(deliverable["keyFindings"]) >= 2
    # Ensure findings don't repeat the summary verbatim
    assert deliverable["summary"] not in deliverable["keyFindings"]

    q_res = evaluate_deliverable_quality("executive_summary", deliverable, substantive_source_text, substantive_uckr)
    assert q_res.passed is True


def test_substantive_article_infographic(substantive_uckr, default_config, substantive_source_text):
    deliverable = generate_deterministic_deliverable("infographic", substantive_uckr, default_config)

    assert "title" in deliverable
    assert "sections" in deliverable
    assert "keyNumbers" in deliverable

    key_numbers = deliverable["keyNumbers"]
    # Source has real metrics (64%, 3.8x, 28%, 450)
    assert len(key_numbers) >= 1

    # Verify no fake stats like "100% Grounding" or claims count presented as real-world metric
    for kn in key_numbers:
        val_str = str(kn.get("value", ""))
        label_str = str(kn.get("label", "")).lower()
        assert "grounding" not in label_str
        assert "claims mapped" not in label_str
        assert "7 output" not in label_str

    q_res = evaluate_deliverable_quality("infographic", deliverable, substantive_source_text, substantive_uckr)
    assert q_res.passed is True


def test_substantive_article_presentation(substantive_uckr, default_config, substantive_source_text):
    deliverable = generate_deterministic_deliverable("presentation", substantive_uckr, default_config)

    assert "title" in deliverable
    assert "slides" in deliverable
    slides = deliverable["slides"]
    assert 3 <= len(slides) <= 6

    # Verify each slide has distinct narrative and no slide duplicates bullets
    for slide in slides:
        assert "title" in slide
        assert "bullets" in slide
        assert "speakerNotes" in slide
        assert len(slide["bullets"]) >= 1
        # Bullets should be concise
        for b in slide["bullets"]:
            assert len(b.split()) <= 25, f"Bullet too wordy: {b}"

    # Check pairwise uniqueness of slides
    slide_titles = [s["title"] for s in slides]
    assert len(set(slide_titles)) == len(slide_titles), "Duplicate slide titles detected"

    q_res = evaluate_deliverable_quality("presentation", deliverable, substantive_source_text, substantive_uckr)
    assert q_res.passed is True
    assert q_res.repetition_penalty == 0.0


def test_substantive_article_video_script(substantive_uckr, default_config, substantive_source_text):
    deliverable = generate_deterministic_deliverable("video", substantive_uckr, default_config)

    assert "title" in deliverable
    assert "scenes" in deliverable
    scenes = deliverable["scenes"]
    assert len(scenes) >= 3

    for scene in scenes:
        assert "sceneNumber" in scene
        assert "narration" in scene
        assert "visualDescription" in scene
        assert len(scene["narration"]) > 10

    q_res = evaluate_deliverable_quality("video", deliverable, substantive_source_text, substantive_uckr)
    assert q_res.passed is True


# ============================================================================
# 2. Instruction-Only Input Handling
# ============================================================================

def test_instruction_only_input_handling():
    instruction_input = (
        "Write 5 tweets about our product release. "
        "Make sure to highlight high engagement, include hashtags, and keep it under 280 characters. "
        "Do not repeat sentences and ensure a professional tone."
    )

    profile = analyze_source_content(instruction_input, fallback_title="Social Media Instructions")
    assert profile.content_type == "instruction_only"
    assert profile.is_instruction_only is True
    assert len(profile.limitations) >= 1
    assert "procedural" in profile.limitations[0].lower() or "instruction" in profile.limitations[0].lower()

    # Build UCKR from instruction profile
    uckr = {
        "title": profile.subject,
        "sourceText": instruction_input,
        "facts": [{"id": "f_1", "value": s} for s in profile.instruction_sentences],
        "metrics": [],
        "entities": [],
    }

    # Generate deliverable
    cfg = TransformationConfig()
    exec_summary = generate_deterministic_deliverable("executive_summary", uckr, cfg)

    # Deliverable must honestly describe instructions rather than fabricating business findings
    summary_text = exec_summary["summary"].lower()
    assert ("instruction" in summary_text or "procedure" in summary_text or "task" in summary_text or "request" in summary_text)

    # Must NOT invent fake empirical metrics
    infographic = generate_deterministic_deliverable("infographic", uckr, cfg)
    assert len(infographic["keyNumbers"]) == 0  # No fake numbers invented

    q_res = evaluate_deliverable_quality("executive_summary", exec_summary, instruction_input, uckr)
    assert q_res.passed is True
    assert q_res.instruction_leakage_detected is False


# ============================================================================
# 3. Short & Insufficient Evidence Source
# ============================================================================

def test_short_and_insufficient_evidence_source():
    sparse_input = "We launched beta testing yesterday."
    profile = analyze_source_content(sparse_input, fallback_title="Beta Launch")

    assert profile.has_insufficient_evidence is True
    assert len(profile.limitations) >= 1
    assert any("sparse" in l.lower() or "concise" in l.lower() or "insufficient" in l.lower() for l in profile.limitations)

    uckr = {
        "title": profile.subject,
        "sourceText": sparse_input,
        "facts": [{"id": "f_1", "value": sparse_input}],
        "metrics": [],
        "entities": [],
    }

    cfg = TransformationConfig()
    advisory = generate_deterministic_deliverable("advisory", uckr, cfg)

    # Advisory must document evidence limitations
    recs = " ".join(advisory.get("recommendations", []))
    obs = " ".join(advisory.get("observations", []))
    combined = (recs + " " + obs).lower()
    assert ("insufficient" in combined or "further empirical validation" in combined or "sparse" in combined)

    # Quality Gate should pass without hallucinated critical alerts
    q_res = evaluate_deliverable_quality("advisory", advisory, sparse_input, uckr)
    assert q_res.passed is True


# ============================================================================
# 4. Numerical Facts and Dates Preservation
# ============================================================================

def test_numerical_facts_and_dates_preservation():
    metric_input = (
        "In Q3 2024, ACME Cloud reduced average latency by 42% across 1,500 edge nodes. "
        "The project completed on October 15, 2024, yielding annual infrastructure savings of $3.2M."
    )
    profile = analyze_source_content(metric_input, fallback_title="ACME Latency Report")

    # Metrics accurately extracted
    metric_values = [m.value for m in profile.empirical_metrics]
    assert "42%" in metric_values
    assert any("1,500" in v or "1500" in v for v in metric_values)
    assert any("3.2" in v and "m" in v.lower() for v in metric_values)

    # Calendar year 2024 is not treated as a fake metric quantity
    assert "2024" not in metric_values

    uckr = {
        "title": profile.subject,
        "sourceText": metric_input,
        "facts": [{"id": f"f_{i}", "value": f} for i, f in enumerate(profile.findings or profile.key_facts)],
        "metrics": [{"id": f"m_{i}", "name": m.label, "value": m.value, "context": m.context} for i, m in enumerate(profile.empirical_metrics)],
        "entities": [],
    }

    cfg = TransformationConfig()
    info = generate_deterministic_deliverable("infographic", uckr, cfg)

    # Infographic contains the verified empirical metrics
    info_vals = [str(kn.get("value")) for kn in info.get("keyNumbers", [])]
    assert any("42%" in v for v in info_vals)

    q_res = evaluate_deliverable_quality("infographic", info, metric_input, uckr)
    assert q_res.passed is True
    assert q_res.grounding_score >= 80.0


# ============================================================================
# 5. Ambiguous and Conflicting Claims Preservation
# ============================================================================

def test_ambiguous_and_conflicting_claims():
    ambiguous_input = (
        "Initial internal benchmarks suggested up to 45% speedups, but preliminary field trials "
        "indicated gains between 10% and 14%, with several edge locations showing neutral performance. "
        "Engineering teams caution that results depend on cluster network topologies."
    )
    profile = analyze_source_content(ambiguous_input, fallback_title="Benchmark Analysis")

    # Should detect qualification/caution
    assert len(profile.limitations) >= 1 or any("depend" in f.lower() or "caution" in f.lower() for f in profile.key_facts)

    uckr = {
        "title": profile.subject,
        "sourceText": ambiguous_input,
        "facts": [{"id": f"f_{i}", "value": f} for i, f in enumerate(profile.findings or profile.key_facts)],
        "metrics": [{"id": f"m_{i}", "name": m.label, "value": m.value, "context": m.context} for i, m in enumerate(profile.empirical_metrics)],
    }

    cfg = TransformationConfig()
    exec_sum = generate_deterministic_deliverable("executive_summary", uckr, cfg)

    # Summary or findings must reflect qualifications
    findings_texts = [f["description"] if isinstance(f, dict) else str(f) for f in exec_sum.get("keyFindings", [])]
    findings_str = " ".join(findings_texts + [exec_sum.get("summary", "")]).lower()
    assert ("depend" in findings_str or "topology" in findings_str or "preliminary" in findings_str or "benchmark" in findings_str)

    q_res = evaluate_deliverable_quality("executive_summary", exec_sum, ambiguous_input, uckr)
    assert q_res.passed is True


# ============================================================================
# 6. Repetitive Source Content De-duplication
# ============================================================================

def test_repetitive_source_content_deduplication():
    repetitive_input = (
        "The distributed database ensures zero data loss. "
        "The distributed database ensures zero data loss. "
        "The distributed database ensures zero data loss. "
        "Automatic failover takes under 500ms during network partitions."
    )
    profile = analyze_source_content(repetitive_input, fallback_title="Database Report")

    # Key facts must be deduplicated
    assert len(profile.key_facts) <= 2

    uckr = {
        "title": profile.subject,
        "sourceText": repetitive_input,
        "facts": [{"id": f"f_{i}", "value": f} for i, f in enumerate(profile.key_facts)],
        "metrics": [],
    }

    cfg = TransformationConfig()
    pres = generate_deterministic_deliverable("presentation", uckr, cfg)

    # Presentation slides must not duplicate bullets
    for slide in pres["slides"]:
        assert len(slide["bullets"]) == len(set(slide["bullets"]))

    q_res = evaluate_deliverable_quality("presentation", pres, repetitive_input, uckr)
    assert q_res.repetition_penalty == 0.0
    assert q_res.passed is True


# ============================================================================
# 7. Quality Gate Detects Redundancy and Repetition Penalty
# ============================================================================

def test_quality_gate_penalizes_redundancy():
    source_text = "Acme Corp launched a new caching system to speed up dashboard loads."
    uckr = {
        "sourceText": source_text,
        "facts": [{"id": "f_1", "value": source_text}],
    }

    # Artificially redundant presentation deliverable
    repetitive_presentation = {
        "title": "Acme Presentation",
        "slides": [
            {
                "slideNumber": 1,
                "title": "Overview",
                "bullets": ["Acme Corp launched a new caching system to speed up dashboard loads."],
                "speakerNotes": "Welcome",
            },
            {
                "slideNumber": 2,
                "title": "System Details",
                "bullets": ["Acme Corp launched a new caching system to speed up dashboard loads."],
                "speakerNotes": "Welcome",
            },
            {
                "slideNumber": 3,
                "title": "Conclusion",
                "bullets": ["Acme Corp launched a new caching system to speed up dashboard loads."],
                "speakerNotes": "Welcome",
            },
        ],
    }

    q_res = evaluate_deliverable_quality("presentation", repetitive_presentation, source_text, uckr)
    assert q_res.repetition_penalty > 0.0
    assert "REPETITIVE_CONTENT" in q_res.flags
    assert q_res.overall_quality_score < 75.0


# ============================================================================
# 8. Separation of Factual Grounding from Transformation Quality
# ============================================================================

def test_separation_of_grounding_and_transformation_quality():
    source_text = (
        "Smart India Hackathon problem statement 1729 requires teams to build "
        "a multimodal document transformation pipeline."
    )
    uckr = {
        "sourceText": source_text,
        "facts": [{"id": "f_1", "value": source_text}],
    }

    # Output that simply copied the source verbatim into all fields without transformation
    verbatim_copy_deliverable = {
        "title": source_text,
        "body": f"{source_text} {source_text} {source_text}",
        "hashtags": [],
    }

    q_res = evaluate_deliverable_quality("linkedin", verbatim_copy_deliverable, source_text, uckr)

    # Grounding is high because words are from the source
    assert q_res.grounding_score >= 80.0
    # BUT transformation score is penalized for high verbatim copying and missing structure
    assert q_res.transformation_score < 60.0
    assert "VERBATIM_COPYING" in q_res.flags or "REPETITIVE_CONTENT" in q_res.flags
    # Proves deliverable is NOT unconditionally passed just because words overlap
    assert q_res.overall_quality_score < 80.0


# ============================================================================
# 9. Detection of Ungrounded Fabricated Metrics
# ============================================================================

def test_detection_of_ungrounded_fabricated_metrics():
    source_text = "The team evaluated three open source databases on local developer laptops."
    uckr = {
        "sourceText": source_text,
        "facts": [{"id": "f_1", "value": source_text}],
        "metrics": [],
    }

    # Infographic that hallucinated 99.999% uptime and $50M savings
    hallucinated_infographic = {
        "title": "Database Benchmark",
        "sections": [{"heading": "Architecture", "content": "Modern distributed system"}],
        "keyNumbers": [
            {"label": "System Uptime", "value": "99.999%"},
            {"label": "Cost Savings", "value": "$50M"},
        ],
    }

    q_res = evaluate_deliverable_quality("infographic", hallucinated_infographic, source_text, uckr)
    assert q_res.grounding_score < 100.0
    assert "UNGROUNDED_NUMBERS" in q_res.flags
    assert q_res.passed is False


# ============================================================================
# 10. Validation Service Integration
# ============================================================================

def test_validation_service_integration(substantive_uckr, default_config, substantive_source_text):
    deliverable_content = generate_deterministic_deliverable("linkedin", substantive_uckr, default_config)

    # Deliverable record matching validation service expectations
    deliv_record = {
        "id": "del_test_123",
        "type": "linkedin",
        "content": deliverable_content,
        "usedFactIds": ["f_0", "f_1"],
    }

    val_res = check_deliverable(deliv_record, substantive_uckr)

    assert "quality" in val_res
    assert "qualityScore" in val_res
    assert val_res["status"] == "PASS"
    assert val_res["qualityScore"] >= 80.0
    trans_score = val_res["quality"].get("metrics", {}).get("transformationQuality") or val_res["quality"].get("transformation_score")
    assert trans_score > 60.0
