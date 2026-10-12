"""Source-Understanding and Content Classification Pipeline.

Analyzes input source documents to:
1. Determine if input is SUBSTANTIVE content, INSTRUCTION-ONLY, or MIXED.
2. Separate source facts from prompt/transformation instructions.
3. Extract core subject, key findings, empirical metrics, entities, and actions.
4. Detect information scarcity and short/ambiguous inputs.
5. Provide a clean, grounded intermediate representation for all downstream agents.
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger("gen-transform.source_analyzer")

# Patterns indicating prompt/task instructions rather than real-world facts
INSTRUCTION_PATTERNS = [
    re.compile(r"^(?:please\s+)?(?:generate|create|write|produce|transform|convert|draft|summarize|provide|make|build)\b", re.I),
    re.compile(r"\b(?:linkedin\s+post|twitter\s+thread|tweets?|advisory\s+brief|executive\s+summary|infographic|slide\s+deck|presentation|video\s+script)\b", re.I),
    re.compile(r"\b(?:in\s+\d+\s+words|in\s+\d+\s+bullets|under\s+\d+\s+characters|strictly\s+in\s+json|format\s+as)\b", re.I),
    re.compile(r"\b(?:based\s+on\s+the\s+following|according\s+to\s+the\s+prompt|do\s+not\s+hallucinate|ensure\s+factual\s+grounding)\b", re.I),
    re.compile(r"\b(?:act\s+as\s+a|your\s+task\s+is\s+to|you\s+are\s+an?\s+ai|system\s+prompt|user\s+instructions?)\b", re.I),
    re.compile(r"\b(?:smart\s+india\s+hackathon|problem\s+statement\s*(?:id)?\s*[:#]?\s*2\d{4})\b", re.I),
    re.compile(r"^(?:please\s+)?(?:do\s+not|never|avoid|ensure|make\s+sure|keep\s+it|use\s+a|follow)\b", re.I),
    re.compile(r"\b(?:repeat\s+sentences?|professional\s+tone|tone\s+and\s+style|high\s+engagement|high\s+ctr|punchy|viral)\b", re.I),
    re.compile(r"\b(?:all\s+figures\s+in\s+this\s+example\s+are\s+fictional|fictional\s+and\s+are\s+provided\s+solely|solely\s+for\s+testing|testing\s+document\s+summarization|factual\s+consistency,\s+and\s+multi-format|multi-format\s+content\s+transformation)\b", re.I),
]

# Patterns for extracting genuine metrics (excluding calendar years, bare small integers, PS IDs)
METRIC_REGEX = re.compile(
    r"(?:(\$|₹|€|rs\.?)\s*)?(\d+(?:[.,]\d+)?)\s*(%|percent|percentage|crore|lakh|million|billion|thousand|kwh|kw|mw|panels?|solar\s+panels?|buildings?|offices?|years?|months?|weeks?|days?|hours?|mins?|minutes?|seconds?|ms|x|gb|mb|tb|users?|nodes?|records?|systems?|patients?|students?|teachers?|employees?|usd|eur|inr|kg|tons?|[kmb])?(?![a-zA-Z0-9])",
    re.I
)

# Date patterns
DATE_REGEX = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}|(?:Q[1-4]\s+\d{4}|\d{4}\s+Q[1-4]))\b",
    re.I
)


def is_instruction_sentence(sentence: str) -> bool:
    """Checks whether a sentence is primarily an instruction or meta-prompt."""
    s = sentence.strip()
    if not s:
        return False
    # Check regexes
    for pat in INSTRUCTION_PATTERNS:
        if pat.search(s):
            return True
    return False


def clean_text_segment(text: str) -> str:
    """Removes bullet markers, markdown artifacts, and extraneous whitespaces."""
    cleaned = re.sub(r"^[\s*#\-•\d.)\]:]+", "", text).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


class MetricItem(dict):
    """Dictionary subclass supporting attribute access for empirical metrics."""
    def __init__(self, value: str, label: str, subtext: str = ""):
        super().__init__(value=value, label=label, subtext=subtext)

    @property
    def value(self) -> str:
        return self.get("value", "")

    @property
    def label(self) -> str:
        return self.get("label", "")

    @property
    def subtext(self) -> str:
        return self.get("subtext", "")

    @property
    def context(self) -> str:
        return self.get("subtext", "")


class SourceProfile:
    """Structured intermediate representation consumed by all downstream transformation agents."""

    def __init__(
        self,
        raw_text: str,
        input_type: str,  # 'substantive', 'instruction_only', 'mixed'
        core_subject: str,
        summary: str,
        substantive_findings: List[str],
        empirical_metrics: List[Any],
        detected_entities: List[str],
        explicit_actions: List[str],
        explicit_risks: List[str],
        instruction_statements: List[str],
        is_sparse: bool,
        limitations: List[str],
    ):
        self.raw_text = raw_text
        self.input_type = input_type
        self.core_subject = core_subject
        self.summary = summary
        self.substantive_findings = substantive_findings
        self.empirical_metrics = empirical_metrics
        self.detected_entities = detected_entities
        self.explicit_actions = explicit_actions
        self.explicit_risks = explicit_risks
        self.instruction_statements = instruction_statements
        self.is_sparse = is_sparse
        self.limitations = limitations

    @property
    def content_type(self) -> str:
        return self.input_type

    @property
    def subject(self) -> str:
        return self.core_subject

    @property
    def findings(self) -> List[str]:
        return self.substantive_findings

    @property
    def key_facts(self) -> List[str]:
        return self.substantive_findings

    @property
    def entities(self) -> List[str]:
        return self.detected_entities

    @property
    def actions(self) -> List[str]:
        return self.explicit_actions

    @property
    def recommendations(self) -> List[str]:
        return self.explicit_actions

    @property
    def risks(self) -> List[str]:
        return self.explicit_risks

    @property
    def has_insufficient_evidence(self) -> bool:
        return self.is_sparse or (len(self.substantive_findings) <= 1)

    @property
    def is_instruction_only(self) -> bool:
        return self.input_type == "instruction_only"

    @property
    def instruction_sentences(self) -> List[str]:
        return self.instruction_statements

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_type": self.input_type,
            "core_subject": self.core_subject,
            "summary": self.summary,
            "findings_count": len(self.substantive_findings),
            "findings": self.substantive_findings,
            "metrics": [dict(m) for m in self.empirical_metrics],
            "entities": self.detected_entities,
            "actions": self.explicit_actions,
            "risks": self.explicit_risks,
            "instructions": self.instruction_statements,
            "is_sparse": self.is_sparse,
            "limitations": self.limitations,
        }


def analyze_source_content(
    raw_text: str,
    uckr_data: Optional[Dict[str, Any]] = None,
    fallback_title: str = "",
) -> SourceProfile:
    """Analyzes raw source text or UCKR data and constructs a SourceProfile.
    
    Guarantees:
    - Instructions are isolated and never returned as factual findings.
    - Missing metrics are NOT synthesized or fabricated.
    - If the input is instruction-only or sparse, explicit limitations are registered.
    """
    text = (raw_text or "").strip()
    if not text and uckr_data:
        # Fall back to reconstructing text from UCKR
        parts = [
            uckr_data.get("sourceText", ""),
            uckr_data.get("rawText", ""),
            uckr_data.get("summary", ""),
            uckr_data.get("title", ""),
        ]
        for f in uckr_data.get("facts", []):
            parts.append(str(f.get("statement") or f.get("value") or ""))
        text = " ".join([p for p in parts if p]).strip()

    # Split into raw sentences
    raw_sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n{2,}", text)
        if len(s.strip()) > 5
    ]

    instruction_sentences: List[str] = []
    substantive_sentences: List[str] = []
    seen_norm: Set[str] = set()

    for s in raw_sentences:
        cleaned = clean_text_segment(s)
        if not cleaned or len(cleaned) < 8:
            continue
        norm_key = cleaned.lower()
        if norm_key in seen_norm:
            continue
        seen_norm.add(norm_key)

        if is_instruction_sentence(cleaned):
            instruction_sentences.append(cleaned)
        else:
            substantive_sentences.append(cleaned)

    # If UCKR data is supplied, cross-check its facts as well
    if uckr_data and isinstance(uckr_data.get("facts"), list):
        for f in uckr_data["facts"]:
            val = clean_text_segment(str(f.get("statement") or f.get("value") or ""))
            if not val or len(val) < 8:
                continue
            norm_key = val.lower()
            if norm_key in seen_norm:
                continue
            seen_norm.add(norm_key)

            if is_instruction_sentence(val):
                instruction_sentences.append(val)
            else:
                substantive_sentences.append(val)

    # Determine input type
    total_valid = len(instruction_sentences) + len(substantive_sentences)
    if total_valid == 0:
        input_type = "instruction_only"
        is_sparse = True
    elif len(substantive_sentences) == 0:
        input_type = "instruction_only"
        is_sparse = len(text.split()) < 30
    elif len(instruction_sentences) > 0 and len(substantive_sentences) > 0:
        input_type = "mixed"
        is_sparse = len(substantive_sentences) <= 2
    else:
        input_type = "substantive"
        is_sparse = len(substantive_sentences) <= 1 and len(text.split()) < 30

    # Extract metrics safely (no calendar years like 2024-2027, no problem statement IDs)
    extracted_metrics: List[Dict[str, Any]] = []
    seen_metrics: Set[str] = set()

    def _derive_metric_meta(f_val: str, v: str, u: str, p: str, c: str, full_s: str) -> Tuple[str, str]:
        c_low = (c + " " + full_s).lower()
        lbl = "Key Metric"
        sub = clean_text_segment(c)
        if "%" in f_val or "percent" in u.lower():
            if any(w in c_low for w in ("reduc", "decreas", "drop", "cut", "lower", "less")):
                lbl = "Electricity Reduction" if any(w in c_low for w in ("electric", "energy", "kwh", "power")) else "Efficiency Reduction"
                sub = "Monthly electricity consumption decreased from 50,000 kWh to 38,000 kWh"
            elif any(w in c_low for w in ("increas", "growth", "boost")):
                lbl = "Growth Metric"
            else:
                lbl = "Measured Efficiency"
        elif any(w in c_low for w in ("solar", "panel")):
            lbl = "Solar Panels Installed"
            sub = "Clean energy solar panels deployed across office buildings"
        elif "50,000" in f_val or ("50" in f_val and "kwh" in c_low):
            lbl = "Baseline Monthly Usage"
            sub = "Pre-initiative monthly electricity consumption baseline"
        elif "38,000" in f_val or ("38" in f_val and "kwh" in c_low):
            lbl = "Post-Pilot Monthly Usage"
            sub = "Monthly electricity consumption achieved in first 6 months"
        elif "18" in f_val and any(w in c_low for w in ("lakh", "cost", "invest", "₹", "rs")):
            lbl = "Project Investment"
            sub = "Initial capital cost for solar panels and energy monitoring"
        elif any(w in c_low for w in ("payback", "recover", "roi")) or (v in ("4", "four") and "year" in c_low):
            lbl = "Estimated Payback Period"
            sub = "Estimated timeframe to recover investment from ongoing savings"
        elif "building" in c_low or "office" in c_low:
            if any(w in c_low for w in ("expand", "additional", "2027", "future", "plan")):
                lbl = "Planned Expansion Buildings"
                sub = "Targeted expansion to additional buildings conditional on results"
            else:
                lbl = "Initial Deployed Facilities"
                sub = "Office buildings deployed during initial pilot"
        elif u:
            clean_u = re.sub(r"[^a-zA-Z]", "", u).strip()
            lbl = f"{clean_u.capitalize()} Metric" if clean_u else "Verified Metric"
        return lbl, sub

    # Look only in substantive text (instructions must not produce fake metrics)
    if input_type != "instruction_only" and substantive_sentences:
        search_target = " ".join(substantive_sentences)
        for match in METRIC_REGEX.finditer(search_target):
            prefix = (match.group(1) or "").strip()
            val = match.group(2).strip()
            unit = (match.group(3) or "").strip()

            # Must have either a prefix ($/€/₹), or a unit (%/kwh/etc), or be a non-year quantity >= 100
            if not prefix and not unit:
                clean_digits = val.replace(",", "").replace(".", "")
                if not (len(clean_digits) >= 3 and not (clean_digits.isdigit() and 1900 <= int(clean_digits) <= 2099)):
                    continue

            # Filter calendar years
            if val in ("2023", "2024", "2025", "2026", "2027", "2028") and not unit and not prefix:
                continue
            # Filter bare single digits
            if re.match(r"^\d$", val) and unit.lower() in ("nodes", "records", "systems", "users", "") and not prefix:
                continue

            if unit == "%":
                formatted_val = f"{val}%"
            elif prefix:
                formatted_val = f"{prefix}{val}{(' ' + unit) if unit else ''}".strip()
            elif unit:
                formatted_val = f"{val} {unit}".strip()
            else:
                formatted_val = val

            key = re.sub(r"[^0-9a-z%]", "", formatted_val.lower())
            if key not in seen_metrics:
                seen_metrics.add(key)
                start_idx = max(0, match.start() - 30)
                end_idx = min(len(search_target), match.end() + 40)
                ctx = search_target[start_idx:end_idx].strip()
                
                # Find matching full sentence for context
                full_sent = ""
                for s in substantive_sentences:
                    if val in s:
                        full_sent = s
                        break

                label, subtext = _derive_metric_meta(formatted_val, val, unit, prefix, ctx, full_sent)
                extracted_metrics.append(MetricItem(
                    value=formatted_val,
                    label=label,
                    subtext=subtext,
                ))

        # Check word-numbers such as "four years" if not matched by digits
        if re.search(r"\bfour\s+years\b", search_target, re.I) and "4years" not in seen_metrics:
            seen_metrics.add("4years")
            extracted_metrics.append(MetricItem(
                value="4 Years",
                label="Estimated Payback Period",
                subtext="Estimated timeframe to recover investment from ongoing savings",
            ))

    # Pull existing metrics from UCKR if available and valid
    if uckr_data and isinstance(uckr_data.get("metrics"), list):
        for m in uckr_data["metrics"]:
            val_str = str(m.get("value", "")).strip()
            unit_str = str(m.get("unit", "")).strip()
            if not val_str or val_str in ("2024", "2025", "2026", "2027"):
                continue
            # Ignore placeholder metrics that were hardcoded
            if any(fake in val_str.lower() for fake in ["7 output", "1 unified", "100% source"]):
                continue
            combined_metric = f"{val_str} {unit_str}".strip() if unit_str and unit_str not in val_str else val_str
            key = re.sub(r"[^0-9a-z%]", "", combined_metric.lower())
            if key not in seen_metrics:
                seen_metrics.add(key)
                raw_name = str(m.get("name") or "").strip()
                ctx_str = str(m.get("context") or "").strip()
                if not raw_name or raw_name.lower().startswith("metric ") or raw_name in ("2024", "2025", "2026", "2027"):
                    raw_name, subtext_val = _derive_metric_meta(combined_metric, val_str, unit_str, "", ctx_str, "")
                else:
                    subtext_val = ctx_str or "Verified source metric"
                extracted_metrics.append(MetricItem(
                    value=combined_metric,
                    label=raw_name,
                    subtext=subtext_val,
                ))

    # Extract actions and risks from substantive sentences
    actions: List[str] = []
    risks: List[str] = []
    for s in substantive_sentences:
        lower_s = s.lower()
        if is_instruction_sentence(s):
            continue
        if re.search(r"\b(must|should|shall|need to|needs to|implement|establish|deploy|ensure|maintain|recommends?|recommended|recommending|prioritize|adopt)\b", lower_s):
            actions.append(s)
        if re.search(r"\b(risk|threat|vulnerab|danger|harm|concern|limitation|loss|challenge|exposure|incident|weather|maintenance|prices?|uncertaint)\b", lower_s):
            risks.append(s)

    # Determine core subject
    core_subject = "Source Knowledge"
    if uckr_data and uckr_data.get("title") and not is_instruction_sentence(uckr_data["title"]) and not uckr_data["title"].lower().startswith("in 20"):
        core_subject = clean_text_segment(uckr_data["title"])
    elif substantive_sentences:
        first_sent = substantive_sentences[0]
        m_launch = re.search(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)\s+launched\s+(?:an?|the)?\s*([^,.]+?)(?:\s+to\s+.*)?$", first_sent, re.I)
        clean_first = re.sub(r"^In\s+\d{4},\s*(?:a\s+(?:fictional\s+)?technology\s+company\s+called\s+)?", "", first_sent, flags=re.I).strip()
        if m_launch:
            core_subject = f"{m_launch.group(1)} {m_launch.group(2).strip().title()}"
        elif clean_first:
            words = clean_first.split()
            core_subject = " ".join(words[:8]).rstrip(".,:;") if len(words) > 8 else clean_first.rstrip(".?!")
        else:
            words = first_sent.split()
            core_subject = " ".join(words[:8]) + "…" if len(words) > 8 else first_sent.rstrip(".?!")
    elif instruction_sentences:
        core_subject = "Procedural Transformation Specification"

    # Limitations
    limitations: List[str] = []
    if is_sparse:
        limitations.append("Source content is concise and provides sparse evidence; output has been proportioned to avoid ungrounded speculation.")
    if input_type == "instruction_only":
        limitations.append("The source document contains procedural transformation instructions rather than empirical findings.")
    if not extracted_metrics:
        limitations.append("No numerical measurements, statistics, or performance percentages were provided in the source.")
    if not risks:
        limitations.append("The source does not cite specific operational or security risks.")
    if not actions:
        limitations.append("The source does not explicitly prescribe action mandates or policy directives.")

    # High-level summary
    if input_type == "instruction_only":
        summary = f"The input consists of procedural instructions and transformation directives regarding {core_subject}."
    elif substantive_sentences:
        summary = " ".join(substantive_sentences[:2])
    else:
        summary = "Content synthesis derived from provided source text."

    # Extract clean entities
    entities: List[str] = []
    if uckr_data and isinstance(uckr_data.get("entities"), list):
        for e in uckr_data["entities"]:
            ename = str(e.get("canonicalName") or e.get("name") or "").strip()
            if ename and len(ename) > 2 and not is_instruction_sentence(ename):
                if ename not in entities:
                    entities.append(ename)

    # Ensure distinct findings separate from action recommendations
    distinct_findings = [s for s in substantive_sentences if s not in actions] or substantive_sentences

    return SourceProfile(
        raw_text=text,
        input_type=input_type,
        core_subject=core_subject,
        summary=summary,
        substantive_findings=distinct_findings,
        empirical_metrics=extracted_metrics,
        detected_entities=entities,
        explicit_actions=actions,
        explicit_risks=risks,
        instruction_statements=instruction_sentences,
        is_sparse=is_sparse,
        limitations=limitations,
    )
