"""Quality Gate & Multi-Dimensional Content Validation Engine.

Separates factual grounding from transformation quality, ensuring that:
1. Outputs are not marked 'PASS' merely because they verbatim overlap with source facts.
2. Repetitive, redundant, poorly formatted, or instruction-leaking content is flagged and gated.
3. Every deliverable is evaluated across independent, transparent dimensions:
   - Factual Grounding (are factual claims backed by UCKR evidence?)
   - Transformation Quality (has text been thoughtfully rewritten for the target medium?)
   - Redundancy & Repetition (are sentences or slides duplicating content?)
   - Format Compliance (does it follow platform length, slide, or structural rules?)
   - Instruction Leakage (did prompt meta-instructions leak into the output?)
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger("gen-transform.quality_gate")

INSTRUCTION_LEAK_WORDS = [
    re.compile(r"\b(?:as\s+an?\s+ai|i\s+am\s+an?\s+ai|prompt\s+instructions?|system\s+prompt|generate\s+a\s+linkedin|generate\s+a\s+twitter|create\s+a\s+presentation)\b", re.I),
    re.compile(r"\b(?:strict\s+json|matching\s+this\s+schema|do\s+not\s+hallucinate|universal\s+source-grounded|rftc\s+prompt)\b", re.I),
    re.compile(r"\b(?:here\s+is\s+the\s+requested|below\s+is\s+the\s+output|sure,\s+i\s+can\s+help)\b", re.I),
    re.compile(r"\b(?:smart\s+india\s+hackathon|problem\s+statement\s*(?:id)?\s*[:#]?\s*2\d{4})\b", re.I),
]


def flatten_content_to_strings(content: Any) -> List[str]:
    """Extracts all user-facing textual segments from a deliverable structure."""
    strings: List[str] = []
    if isinstance(content, str):
        clean = content.strip()
        if clean:
            strings.append(clean)
    elif isinstance(content, list):
        for item in content:
            strings.extend(flatten_content_to_strings(item))
    elif isinstance(content, dict):
        skip_keys = {
            "usedFactIds", "citations", "validation", "id", "deliverableId",
            "status", "createdAt", "updatedAt", "targetAudience", "characterCount",
            "charCount", "severity", "severityTag", "dateIssued", "advisoryId",
            "subtitlesSrt", "srt", "subtitles", "durationSeconds", "totalDurationSeconds",
            "sceneNumber", "slideNumber", "postNumber", "index",
            "subtext", "context", "metric", "iconName", "layoutRecommendation",
            "visualStyle", "visualRecommendation", "aspectRatio", "style",
            "complianceReferences", "references", "domain", "priority", "onScreenText",
            "sceneDescription",
        }
        # Skip redundant alias containers
        if "body" in content and "content" in content:
            skip_keys.add("content")
        if "posts" in content:
            if "thread" in content:
                skip_keys.add("thread")
            if "singlePost" in content:
                skip_keys.add("singlePost")
            if "content" in content:
                skip_keys.add("content")
        if "summary" in content:
            if "abstract" in content:
                skip_keys.add("abstract")
            if "executiveOverview" in content:
                skip_keys.add("executiveOverview")
        if "observations" in content and "keyInformation" in content:
            skip_keys.add("keyInformation")
        if "situation" in content and "background" in content:
            skip_keys.add("background")
        if "sections" in content and "supportingPoints" in content:
            skip_keys.add("supportingPoints")
        if "sections" in content:
            skip_keys.add("subHeadline")
            skip_keys.add("keyMessage")
        if "keyStatistics" in content and "keyNumbers" in content:
            skip_keys.add("keyNumbers")
        if "recommendedActions" in content and "recommendations" in content:
            skip_keys.add("recommendations")
        if "recommendedActions" in content and "strategicActions" in content:
            skip_keys.add("strategicActions")
        if "implications" in content and "keyRisks" in content:
            skip_keys.add("keyRisks")
        if "scenes" in content:
            if "script" in content:
                skip_keys.add("script")
        if "situation" in content:
            if "background" in content:
                skip_keys.add("background")
            if "strategicContext" in content:
                skip_keys.add("strategicContext")
        if "observations" in content and "keyInformation" in content:
            skip_keys.add("keyInformation")
        if "metrics" in content and "keyStatistics" in content:
            skip_keys.add("metrics")
        if "title" in content:
            if "deckTitle" in content:
                skip_keys.add("deckTitle")
            if "presentation_title" in content:
                skip_keys.add("presentation_title")

        for k, v in content.items():
            if k in skip_keys:
                continue
            strings.extend(flatten_content_to_strings(v))
    return strings


def tokenize_words(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9]{3,}\b", text)]


def jaccard_similarity(tokens1: Set[str], tokens2: Set[str]) -> float:
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union)


class QualityGateResult:
    """Detailed multi-dimensional validation result for a deliverable."""

    def __init__(
        self,
        deliverable_type: str,
        gate_passed: bool,
        grounding_score: float,
        transformation_score: float,
        format_compliance_score: float,
        repetition_penalty: float,
        overall_quality_score: float,
        status: str,  # 'PASS', 'WARNING', 'FAIL'
        instruction_leakage_detected: bool,
        redundancy_detected: bool,
        issues: List[str],
        warnings: List[str],
        supported_facts: List[str],
        unsupported_claims: List[str],
        verbatim_copying_detected: bool = False,
    ):
        self.deliverable_type = deliverable_type
        self.gate_passed = gate_passed
        self.grounding_score = grounding_score
        self.transformation_score = transformation_score
        self.format_compliance_score = format_compliance_score
        self.repetition_penalty = repetition_penalty
        self.overall_quality_score = overall_quality_score
        self.status = status
        self.instruction_leakage_detected = instruction_leakage_detected
        self.redundancy_detected = redundancy_detected
        self.issues = issues
        self.warnings = warnings
        self.supported_facts = supported_facts
        self.unsupported_claims = unsupported_claims
        self.verbatim_copying_detected = verbatim_copying_detected

    @property
    def passed(self) -> bool:
        return self.gate_passed

    @property
    def flags(self) -> List[str]:
        flag_list: List[str] = []
        if self.instruction_leakage_detected:
            flag_list.append("INSTRUCTION_LEAKAGE")
        if self.redundancy_detected:
            flag_list.append("REPETITIVE_CONTENT")
        if self.verbatim_copying_detected:
            flag_list.append("VERBATIM_COPYING")
        for iss in self.issues + self.unsupported_claims + self.warnings:
            iss_l = iss.lower()
            if "ungrounded metric" in iss_l or "unsupported metric" in iss_l or "ungrounded number" in iss_l:
                if "UNGROUNDED_NUMBERS" not in flag_list:
                    flag_list.append("UNGROUNDED_NUMBERS")
            elif "verbatim" in iss_l or "overlap" in iss_l:
                if "VERBATIM_COPYING" not in flag_list:
                    flag_list.append("VERBATIM_COPYING")
            elif "repetition" in iss_l or "redundant" in iss_l or "repetitive" in iss_l:
                if "REPETITIVE_CONTENT" not in flag_list:
                    flag_list.append("REPETITIVE_CONTENT")
            else:
                flag_list.append(iss)
        return flag_list

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deliverableType": self.deliverable_type,
            "gatePassed": self.gate_passed,
            "status": self.status,
            "metrics": {
                "groundingScore": self.grounding_score,
                "transformationQuality": self.transformation_score,
                "formatCompliance": self.format_compliance_score,
                "repetitionPenalty": self.repetition_penalty,
                "overallScore": self.overall_quality_score,
            },
            "instructionLeakage": self.instruction_leakage_detected,
            "redundancyDetected": self.redundancy_detected,
            "issues": self.issues,
            "warnings": self.warnings,
            "supportedFacts": self.supported_facts,
            "unsupportedClaims": self.unsupported_claims,
            "flags": self.flags,
        }


def detect_instruction_leakage(text: str) -> bool:
    """Checks if text contains prompt or system directive leakage."""
    for pat in INSTRUCTION_LEAK_WORDS:
        if pat.search(text):
            return True
    return False


def evaluate_deliverable_quality(
    dtype: str,
    content: Dict[str, Any],
    uckr_or_source: Any,
    source_or_uckr: Any = None,
) -> QualityGateResult:
    """Evaluates a deliverable against all quality gate dimensions."""
    if isinstance(uckr_or_source, str) and isinstance(source_or_uckr, dict):
        source_text = uckr_or_source
        uckr = source_or_uckr
    elif isinstance(uckr_or_source, dict):
        uckr = uckr_or_source
        source_text = source_or_uckr if isinstance(source_or_uckr, str) else (uckr.get("sourceText") or "")
    else:
        source_text = str(uckr_or_source or "")
        uckr = source_or_uckr if isinstance(source_or_uckr, dict) else {}

    issues: List[str] = []
    warnings: List[str] = []

    text_segments = flatten_content_to_strings(content)
    full_text = " ".join(text_segments)

    # 1. Instruction Leakage Check
    instruction_leaked = False
    for pat in INSTRUCTION_LEAK_WORDS:
        m = pat.search(full_text)
        if m:
            instruction_leaked = True
            issues.append(f"Instruction leakage detected: contains prompt/system directive '{m.group(0)}'.")
            break

    # 2. Redundancy & Repetition Check
    redundancy_detected = False
    repetition_penalty = 0.0

    # Check for identical non-trivial sentences across the deliverable
    header_titles: Set[str] = set()
    if isinstance(content, dict):
        header_titles = {
            str(content.get("title", "")).strip().lower(),
            str(content.get("deckTitle", "")).strip().lower(),
            str(content.get("presentation_title", "")).strip().lower(),
            str(content.get("headline", "")).strip().lower(),
        }
        if "slides" in content and isinstance(content["slides"], list):
            for sl in content["slides"]:
                if isinstance(sl, dict) and sl.get("title"):
                    header_titles.add(str(sl["title"]).strip().lower())
    seen_sentences: Set[str] = set()
    duplicate_sentences: List[str] = []
    for seg in text_segments:
        for sent in re.split(r"(?<=[.!?])\s+", seg):
            clean_sent = re.sub(r"\s+", " ", sent).strip().lower()
            if len(clean_sent) > 25:
                if clean_sent in header_titles and clean_sent not in seen_sentences:
                    seen_sentences.add(clean_sent)
                    continue
                if clean_sent in seen_sentences:
                    duplicate_sentences.append(sent.strip())
                else:
                    seen_sentences.add(clean_sent)

    if duplicate_sentences:
        redundancy_detected = True
        repetition_penalty += min(40.0, len(duplicate_sentences) * 15.0)
        issues.append(f"Redundant repetitive sentences detected ({len(duplicate_sentences)} repeated sentences).")

    # Format-specific redundancy: slides and twitter posts
    if dtype in ("presentation", "slides") and "slides" in content:
        slides = content.get("slides") or []
        for i in range(len(slides)):
            for j in range(i + 1, len(slides)):
                s1_tokens = set(tokenize_words(" ".join(slides[i].get("bullets", []) or [])))
                s2_tokens = set(tokenize_words(" ".join(slides[j].get("bullets", []) or [])))
                sim = jaccard_similarity(s1_tokens, s2_tokens)
                if sim > 0.65 and len(s1_tokens) > 5:
                    redundancy_detected = True
                    repetition_penalty += 25.0
                    issues.append(f"Slide {i+1} and Slide {j+1} have high content duplication (Jaccard {round(sim, 2)}).")

    if dtype in ("twitter", "x") and "posts" in content:
        posts = content.get("posts") or []
        for i in range(len(posts)):
            for j in range(i + 1, len(posts)):
                p1_tokens = set(tokenize_words(posts[i].get("text", "")))
                p2_tokens = set(tokenize_words(posts[j].get("text", "")))
                sim = jaccard_similarity(p1_tokens, p2_tokens)
                if sim > 0.70 and len(p1_tokens) > 5:
                    redundancy_detected = True
                    repetition_penalty += 25.0
                    issues.append(f"Tweet {i+1} and Tweet {j+1} duplicate the same content.")

    # 3. Format Compliance Check
    format_compliance_score = 100.0

    if dtype in ("twitter", "x"):
        posts = content.get("posts") or content.get("thread") or []
        if isinstance(posts, list) and posts:
            for p in posts:
                txt = p.get("text", "") if isinstance(p, dict) else str(p)
                if len(txt) > 280:
                    format_compliance_score -= 20.0
                    issues.append(f"Twitter post exceeds 280 character limit ({len(txt)} chars).")
        else:
            format_compliance_score -= 30.0
            warnings.append("Twitter content missing posts thread array.")

    elif dtype in ("presentation", "slides"):
        slides = content.get("slides") or []
        if len(slides) < 2:
            format_compliance_score -= 30.0
            issues.append(f"Presentation deck has only {len(slides)} slide(s); minimum is 2.")
        for sl in slides:
            bullets = sl.get("bullets") or []
            if len(bullets) > 6:
                format_compliance_score -= 10.0
                warnings.append(f"Slide '{sl.get('title')}' has {len(bullets)} bullets (recommended <= 5).")

    elif dtype == "infographic":
        stats = content.get("keyStatistics") or content.get("keyNumbers") or []
        # Check for fake metrics: 7 output formats, 1 unified knowledge core, 100% source grounding
        for st in stats:
            val = str(st.get("value") or "").lower()
            if "7 output" in val or "1 unified" in val or "100% source" in val:
                format_compliance_score -= 30.0
                issues.append("Infographic contains boilerplate system metrics instead of source data.")

    elif dtype == "advisory":
        req_fields = ["title", "situation", "recommendedActions"]
        missing = [f for f in req_fields if f not in content or not content[f]]
        if missing:
            format_compliance_score -= 20.0 * len(missing)
            issues.append(f"Advisory missing essential sections: {', '.join(missing)}.")

    elif dtype in ("executive_summary", "summary"):
        if not content.get("summary") and not content.get("abstract") and not content.get("executiveOverview"):
            format_compliance_score -= 30.0
            issues.append("Executive summary is missing core summary/abstract paragraph.")

    format_compliance_score = max(0.0, min(100.0, format_compliance_score))

    # 4. Factual Grounding & Supported Facts Check
    facts = uckr.get("facts") or []
    uckr_fact_tokens = [set(tokenize_words(f.get("statement") or f.get("value") or "")) for f in facts]
    supported_facts: List[str] = []
    unsupported_claims: List[str] = []

    # Check numerical grounding (detect ungrounded numbers >= 2 digits not in UCKR or source)
    uckr_text = (source_text or "") + " " + " ".join(str(f.get("statement") or f.get("value") or "") for f in facts)
    for m in (uckr.get("metrics") or []):
        uckr_text += " " + str(m.get("value") or "")
    uckr_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)*", uckr_text))
    uckr_numbers |= {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "15", "16", "20", "25", "30", "45", "60", "90", "100", "2024", "2025", "2026", "2027"}

    content_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)*", full_text))
    ungrounded_nums = [n for n in content_numbers if n not in uckr_numbers and len(n) >= 2]
    if ungrounded_nums:
        for un in ungrounded_nums[:4]:
            msg = f"Ungrounded number '{un}' detected without UCKR source basis."
            unsupported_claims.append(msg)
            issues.append(msg)

    # Match used facts
    for idx, f_tokens in enumerate(uckr_fact_tokens):
        if not f_tokens:
            continue
        # Check if deliverable contains significant tokens from this fact
        matched = False
        for seg in text_segments:
            seg_tokens = set(tokenize_words(seg))
            if len(f_tokens & seg_tokens) >= max(2, int(len(f_tokens) * 0.4)):
                matched = True
                break
        if matched and idx < len(facts):
            fid = facts[idx].get("factId") or facts[idx].get("id") or f"fact_{idx+1}"
            supported_facts.append(fid)

    grounding_score = 100.0
    if unsupported_claims:
        grounding_score = max(40.0, 100.0 - (len(unsupported_claims) * 20.0))

    # 5. Transformation Quality Score (is it actually rewritten rather than verbatim dumping?)
    transformation_score = 95.0
    if instruction_leaked:
        transformation_score -= 40.0
    if redundancy_detected:
        transformation_score -= repetition_penalty

    # Check if deliverable is identical verbatim copy of raw source text
    verbatim_copying_detected = False
    if source_text and len(source_text.strip()) > 30:
        src_tokens = set(tokenize_words(source_text))
        deliv_tokens = set(tokenize_words(full_text))
        sim = jaccard_similarity(src_tokens, deliv_tokens)
        if sim > 0.85 and len(deliv_tokens) > 10:
            verbatim_copying_detected = True
            transformation_score -= 40.0
            warnings.append("High verbatim overlap with raw source; content lacks format-specific restructuring.")
            issues.append("Verbatim copying detected: deliverable reproduces source text without transformation.")

    transformation_score = max(0.0, min(100.0, transformation_score))

    # 6. Overall Weighted Quality Score
    overall_quality = round(
        (grounding_score * 0.40) +
        (transformation_score * 0.35) +
        (format_compliance_score * 0.25),
        1
    )

    # 7. Status & Gate Decision
    gate_passed = (len(issues) == 0) and (overall_quality >= 70.0)
    if not gate_passed:
        status = "FAIL" if (instruction_leaked or repetition_penalty >= 30.0 or overall_quality < 60.0) else "WARNING"
    elif warnings:
        status = "WARNING"
    else:
        status = "PASS"

    return QualityGateResult(
        deliverable_type=dtype,
        gate_passed=gate_passed,
        grounding_score=round(grounding_score, 1),
        transformation_score=round(transformation_score, 1),
        format_compliance_score=round(format_compliance_score, 1),
        repetition_penalty=round(repetition_penalty, 1),
        overall_quality_score=overall_quality,
        status=status,
        instruction_leakage_detected=instruction_leaked,
        redundancy_detected=redundancy_detected,
        issues=issues,
        warnings=warnings,
        supported_facts=supported_facts,
        unsupported_claims=unsupported_claims,
        verbatim_copying_detected=verbatim_copying_detected,
    )
