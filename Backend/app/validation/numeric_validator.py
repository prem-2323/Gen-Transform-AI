"""Phase 13 Validation Engine — Numeric & Date Validator.

Validates numbers, percentages, monetary amounts, and calendar dates against
trusted source evidence, normalizing harmless formatting variations.
"""

from __future__ import annotations

import re
import logging
from typing import List, Set, Tuple
from .schemas import (
    IssueTypeEnum,
    SeverityEnum,
    ValidationContext,
    ValidationIssue,
)

log = logging.getLogger("gen-transform.validation.numeric_validator")


class NumericValidator:
    """Validator auditing numeric values and dates against source ground truth."""

    @staticmethod
    def _normalize_number(val_str: str) -> float:
        """Convert number/monetary string to normalized float representation."""
        clean = val_str.lower().replace(",", "").replace("$", "").replace("₹", "").replace("rs.", "").replace("rs", "").replace("€", "").replace("%", "").strip()
        if clean.endswith("million") or clean.endswith("m"):
            clean = clean.replace("million", "").rstrip("m").strip()
            return float(clean) * 1_000_000.0
        if clean.endswith("billion") or clean.endswith("b"):
            clean = clean.replace("billion", "").rstrip("b").strip()
            return float(clean) * 1_000_000_000.0
        if clean.endswith("lakh"):
            clean = clean.replace("lakh", "").strip()
            return float(clean) * 100_000.0
        if clean.endswith("crore"):
            clean = clean.replace("crore", "").strip()
            return float(clean) * 10_000_000.0
        if clean.endswith("kwh") or clean.endswith("kw") or clean.endswith("mw"):
            clean = re.sub(r"[a-z]+$", "", clean).strip()
            return float(clean)
        if clean.endswith("k"):
            clean = clean.rstrip("k").strip()
            return float(clean) * 1_000.0
        try:
            return float(clean)
        except ValueError:
            return 0.0

    def validate_numerics_and_dates(
        self, context: ValidationContext
    ) -> Tuple[List[ValidationIssue], List[ValidationIssue]]:
        """Validate generated numbers and dates against source content.

        Returns:
            Tuple of (numeric_issues, date_issues)
        """
        numeric_issues: List[ValidationIssue] = []
        date_issues: List[ValidationIssue] = []

        gen_text = context.transformation_output or ""
        source_text = " ".join([item.get("content", "") for item in context.source_evidence])
        if not source_text and context.source_evidence:
            source_text = str(context.source_evidence)

        # 1. Date Extraction & Matching
        date_regex = r"\b\d{4}-\d{2}-\d{2}\b"
        gen_dates = set(re.findall(date_regex, gen_text))
        source_dates = set(re.findall(date_regex, source_text))

        for g_date in gen_dates:
            if source_dates and g_date not in source_dates:
                msg = f"Date mismatch: Generated date '{g_date}' does not match trusted source dates {sorted(source_dates)}"
                date_issues.append(
                    ValidationIssue(
                        issue_type=IssueTypeEnum.DATE_MISMATCH,
                        severity=SeverityEnum.CRITICAL,
                        message=msg,
                        generated_text=g_date,
                    )
                )

        # 2. Number & Percentage Extraction & Matching
        number_regex = r"\b(?:\d+(?:\.\d+)?%|(?:₹|\$|€|rs\.?)\s*\d+(?:\.\d+)?(?:\s*(?:lakh|crore|million|billion))?|\d+\s*(?:lakh|crore|million|billion|kwh|kw|mw)|\d+)\b"
        gen_numbers = re.findall(number_regex, gen_text, re.IGNORECASE)
        source_numbers = re.findall(number_regex, source_text, re.IGNORECASE)

        # Convert source numbers to normalized floats
        source_norm_vals: Set[float] = {
            self._normalize_number(num) for num in source_numbers if num.strip()
        }

        for g_num in set(gen_numbers):
            # Skip single digit section/header numbers like 1, 2, 3
            if len(g_num.strip()) <= 1 and g_num.strip().isdigit():
                continue

            norm_g = self._normalize_number(g_num)
            if source_norm_vals and norm_g not in source_norm_vals:
                # Allow minor float precision tolerance
                if not any(abs(norm_g - s_val) < 1e-4 for s_val in source_norm_vals):
                    msg = f"Numeric mismatch: Generated value '{g_num}' is not supported by source evidence."
                    numeric_issues.append(
                        ValidationIssue(
                            issue_type=IssueTypeEnum.NUMBER_MISMATCH,
                            severity=SeverityEnum.ERROR,
                            message=msg,
                            generated_text=g_num,
                        )
                    )

        return numeric_issues, date_issues


__all__ = ["NumericValidator"]
