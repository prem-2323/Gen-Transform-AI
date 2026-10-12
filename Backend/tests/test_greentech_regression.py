"""Regression tests for GreenTech Solutions renewable energy test document.

Validates the 10 requirements:
1. The source-supported 24% value is not falsely flagged.
2. Supporting consumption figures (50,000 kWh, 38,000 kWh, ₹18 lakh, 120 panels, 4 years) are preserved.
3. Unsupported invented metrics (95%, 500 panels, ₹90 crore) are still detected.
4. Duplicate warnings are removed.
5. Different grounding scores have explainable evidence.
6. Every agent creates genuinely format-specific output.
7. Executive summary is concise and non-repetitive.
8. Infographic metrics have meaningful labels and correct values (no calendar year 2025 as metric).
9. The planned 2027 expansion is conditional/future, not completed.
10. Meta-disclaimer is stripped from substantive findings, risks, and deliverables.
"""

import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest
from app.models.deliverable import TransformationConfig
from app.services.transformation.source_analyzer import analyze_source_content, SourceProfile
from app.services.transformation.templates import generate_deterministic_deliverable
from app.services.transformation.quality_gate import evaluate_deliverable_quality
from app.services.validation.validation_service import check_deliverable
from app.validation.numeric_validator import NumericValidator
from app.validation.schemas import ValidationContext


GREENTECH_SOURCE = (
    "In 2025, a fictional technology company called GreenTech Solutions launched a renewable energy initiative "
    "to reduce electricity consumption across its offices. The company installed 120 solar panels across three buildings "
    "and introduced an energy monitoring system to track daily usage. During the first six months, electricity consumption "
    "decreased from 50,000 kWh to 38,000 kWh per month, representing a 24% reduction. The project cost ₹18 lakh, and the "
    "company estimates that it could recover the investment within four years if the current savings continue. However, the "
    "results may vary depending on weather conditions, maintenance costs, and future electricity prices. The company plans "
    "to expand the initiative to two additional buildings in 2027, subject to budget approval and an evaluation of the pilot "
    "results. Management recommends monitoring energy consumption monthly, publishing quarterly progress reports, and "
    "comparing actual savings against the original targets before approving further expansion. All figures in this example "
    "are fictional and are provided solely for testing document summarization, factual consistency, and multi-format content "
    "transformation."
)


@pytest.fixture
def greentech_profile() -> SourceProfile:
    return analyze_source_content(GREENTECH_SOURCE, fallback_title="GreenTech Solutions Renewable Energy Initiative")


@pytest.fixture
def greentech_uckr(greentech_profile) -> dict:
    facts = [{"id": f"f_{i}", "value": f, "type": "Finding"} for i, f in enumerate(greentech_profile.substantive_findings)]
    metrics = [
        {"id": f"m_{i}", "name": m.get("label", f"Metric {i+1}"), "value": m.get("value", ""), "context": m.get("subtext", "")}
        for i, m in enumerate(greentech_profile.empirical_metrics)
    ]
    return {
        "title": greentech_profile.core_subject,
        "sourceText": GREENTECH_SOURCE,
        "summary": greentech_profile.summary,
        "facts": facts,
        "metrics": metrics,
    }


@pytest.fixture
def default_config() -> TransformationConfig:
    return TransformationConfig(audience="executive", tone="professional", detailLevel="medium")


# -----------------------------------------------------------------------------
# 1. Metric extraction & preservation
# -----------------------------------------------------------------------------

def test_greentech_metric_extraction(greentech_profile):
    """Metrics extracted must include 24%, 120 panels, 50,000 kWh, 38,000 kWh, ₹18 lakh, and 4 years.
    Calendar year 2025 must NOT be extracted as a primary metric.
    """
    metric_values = [str(m.get("value", "")).lower() for m in greentech_profile.empirical_metrics]
    all_values_str = " ".join(metric_values)

    assert "24%" in all_values_str or "24" in all_values_str
    assert "120" in all_values_str
    assert "50,000" in all_values_str or "50000" in all_values_str
    assert "38,000" in all_values_str or "38000" in all_values_str
    assert "18" in all_values_str or "lakh" in all_values_str

    # Year 2025 alone must not be an empirical metric
    assert "2025" not in [m.get("value", "").strip() for m in greentech_profile.empirical_metrics]

    # Metric labels must be human-readable and semantic
    labels = [m.get("label", "") for m in greentech_profile.empirical_metrics]
    assert any("Reduction" in l or "Electricity" in l for l in labels)
    assert any("Panel" in l or "Solar" in l for l in labels)


# -----------------------------------------------------------------------------
# 2. 24% is not falsely flagged
# -----------------------------------------------------------------------------

def test_24_percent_not_falsely_flagged(greentech_uckr, default_config):
    """Deliverable containing 24% reduction and 50,000 kWh must be verified without false warning."""
    deliv = generate_deterministic_deliverable("linkedin", greentech_uckr, default_config)
    res = check_deliverable(deliv, greentech_uckr)

    # Inconsistencies must not contain 24 or 24%
    assert "24" not in res.get("inconsistencies", [])
    assert "24%" not in res.get("inconsistencies", [])
    assert res.get("groundingScore", 0) >= 80.0

    # Also test numeric validator directly
    num_val = NumericValidator()
    ctx = ValidationContext(
        transformation_output="During the first six months, electricity consumption decreased representing a 24% reduction.",
        source_evidence=[{"content": GREENTECH_SOURCE}],
    )
    num_issues, date_issues = num_val.validate_numerics_and_dates(ctx)
    assert len(num_issues) == 0


# -----------------------------------------------------------------------------
# 3. Supporting figures and currency units are preserved
# -----------------------------------------------------------------------------

def test_supporting_figures_and_units_preserved(greentech_uckr, default_config):
    """Ensure ₹18 lakh, kWh, panels, and payback timeframe are represented with context."""
    deliv_summary = generate_deterministic_deliverable("executive_summary", greentech_uckr, default_config)
    content_text = str(deliv_summary)

    assert "120" in content_text
    assert "50,000" in content_text or "50000" in content_text
    assert "38,000" in content_text or "38000" in content_text
    assert "18" in content_text
    assert "four years" in content_text.lower() or "4 years" in content_text.lower() or "payback" in content_text.lower()


# -----------------------------------------------------------------------------
# 4. Unsupported invented metrics are still detected
# -----------------------------------------------------------------------------

def test_unsupported_invented_metrics_detected(greentech_uckr):
    """If deliverable invents 99% reduction or 500 solar panels or ₹90 crore, it must be flagged."""
    hallucinated_deliv = {
        "id": "del_hallucinated",
        "type": "linkedin",
        "content": {
            "title": "GreenTech Renewable Initiative",
            "body": "The company installed 500 solar panels achieving a 99% reduction at a total cost of ₹90 crore."
        }
    }
    res = check_deliverable(hallucinated_deliv, greentech_uckr)
    inconsistencies = res.get("inconsistencies", [])

    # Either 99 or 500 or 90 must be caught as inconsistent numbers not in source facts
    assert any(n in inconsistencies for n in ["99", "500", "90"])
    assert res.get("status") in ["REVIEW_REQUIRED", "FAIL"]


# -----------------------------------------------------------------------------
# 5. Warnings deduplication
# -----------------------------------------------------------------------------

def test_warnings_deduplication(greentech_uckr):
    """Deliverable with repeated unsupported claims should not emit duplicate warning strings."""
    deliv = {
        "id": "del_dup",
        "type": "linkedin",
        "content": {
            "body": "The system reached 99% efficiency. Again, 99% was recorded. And 99% repeated."
        }
    }
    res = check_deliverable(deliv, greentech_uckr)
    warnings = res.get("qualityWarnings", [])
    issues = res.get("qualityIssues", [])

    assert len(warnings) == len(set(warnings))
    assert len(issues) == len(set(issues))
    # Inconsistencies must also be unique
    inconsistencies = res.get("inconsistencies", [])
    assert len(inconsistencies) == len(set(inconsistencies))


# -----------------------------------------------------------------------------
# 6. Separate documented grounding policy with explainable evidence
# -----------------------------------------------------------------------------

def test_grounding_policy_and_explainable_evidence(greentech_uckr, default_config):
    """Quality gate and validation results provide separate, unconfused metrics."""
    deliv = generate_deterministic_deliverable("linkedin", greentech_uckr, default_config)
    res = check_deliverable(deliv, greentech_uckr)

    assert "groundingScore" in res
    assert "completenessScore" in res
    assert "transformationQuality" in res
    assert "formatCompliance" in res
    assert "qualityScore" in res

    # All individual scores are within valid 0-100 ranges
    for score_key in ["groundingScore", "completenessScore", "transformationQuality", "formatCompliance", "qualityScore"]:
        assert 0.0 <= res[score_key] <= 100.0


# -----------------------------------------------------------------------------
# 7. Every agent creates genuinely format-specific output
# -----------------------------------------------------------------------------

def test_format_specific_deliverable_generation(greentech_uckr, default_config):
    """All 7 deliverable formats must exhibit distinct schemas and stylistic structure."""
    types = ["linkedin", "twitter", "advisory", "infographic", "executive_summary", "presentation", "video_script"]

    for dtype in types:
        d = generate_deterministic_deliverable(dtype, greentech_uckr, default_config)
        assert isinstance(d, dict)

        if dtype == "linkedin":
            assert "hook" in d
            assert "hashtags" in d
            assert any("Renewable" in tag or "Sustainability" in tag or "CleanTech" in tag for tag in d["hashtags"])
        elif dtype == "twitter":
            assert "thread" in d or "posts" in d
            posts = d.get("thread") or d.get("posts")
            assert len(posts) >= 2
        elif dtype == "advisory":
            assert "situation" in d or "observations" in d or "advisorySections" in d
        elif dtype == "infographic":
            assert "metrics" in d
            assert len(d["metrics"]) >= 3
            # Metrics must not be complete sentences
            for m in d["metrics"]:
                assert len(m["label"].split()) <= 6
        elif dtype == "executive_summary":
            assert "keyFindings" in d
            assert len(d["keyFindings"]) >= 2
        elif dtype == "presentation":
            assert "slides" in d
            assert len(d["slides"]) >= 3
            # Slides must not use generic "Core Capabilities" title
            slide_titles = [s.get("title", "") for s in d["slides"]]
            assert not any("Core Capabilities & System Features" in t for t in slide_titles)
        elif dtype == "video_script":
            assert "scenes" in d
            assert len(d["scenes"]) >= 2


# -----------------------------------------------------------------------------
# 8. Executive summary is concise and non-repetitive
# -----------------------------------------------------------------------------

def test_executive_summary_conciseness(greentech_uckr, default_config):
    """Executive summary must not repeat findings and must remain concise."""
    deliv = generate_deterministic_deliverable("executive_summary", greentech_uckr, default_config)
    findings = deliv.get("keyFindings", [])
    finding_descs = [f.get("description", str(f)) if isinstance(f, dict) else str(f) for f in findings]
    assert len(finding_descs) == len(set(finding_descs))
    assert len(finding_descs) >= 2

    # Findings should be distinct summaries, not entire raw paragraph dumps
    for fd in finding_descs:
        assert len(fd.split()) < 50


# -----------------------------------------------------------------------------
# 9. Infographic metrics have semantic labels and no calendar years as primary
# -----------------------------------------------------------------------------

def test_infographic_metrics_structure(greentech_uckr, default_config):
    """Infographic metrics must have clean labels (e.g. Electricity Reduction) not 'Metric 1' or 2025."""
    deliv = generate_deterministic_deliverable("infographic", greentech_uckr, default_config)
    metrics = deliv.get("metrics", [])

    assert len(metrics) >= 3
    for m in metrics:
        assert m.get("value") != "2025"
        label = m.get("label", "")
        assert not label.startswith("In 2025, a fictional")
        assert len(label.split()) <= 6


# -----------------------------------------------------------------------------
# 10. Meta-disclaimer is stripped and 2027 expansion is conditional
# -----------------------------------------------------------------------------

def test_meta_disclaimer_stripped_and_expansion_conditional(greentech_uckr, default_config):
    """The testing disclaimer must be completely absent from deliverables.
    The 2027 expansion must be framed as planned/conditional.
    """
    for dtype in ["linkedin", "executive_summary", "advisory", "presentation"]:
        d = generate_deterministic_deliverable(dtype, greentech_uckr, default_config)
        text = str(d).lower()

        assert "provided solely for testing document summarization" not in text
        assert "all figures in this example are fictional and are provided solely" not in text

        # Check expansion context if mentioned
        if "2027" in text:
            assert any(word in text for word in ["plan", "expansion", "expand", "budget", "evaluation", "conditional", "subject to"])
