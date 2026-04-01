"""Utilities for turning manually reviewed samples into YAML classification rules."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pandas as pd
import yaml


def apply_manual_labels_to_rules(
    review_csv_path: Path,
    rules_yaml_path: Path,
    *,
    starting_priority: int = 200,
    default_confidence: float = 0.82,
    review_required_below: float = 0.75,
) -> Path:
    """Append manually reviewed training samples to the YAML classification ruleset."""
    reviewed = pd.read_csv(review_csv_path)
    if reviewed.empty:
        return rules_yaml_path

    with rules_yaml_path.open("r", encoding="utf-8") as file_obj:
        payload = yaml.safe_load(file_obj) or {}
    rules: list[dict[str, Any]] = list(payload.get("rules", []))
    existing_rule_ids = {str(rule.get("rule_id", "")) for rule in rules}
    next_priority = max([int(rule.get("priority", 0)) for rule in rules] + [starting_priority - 10]) + 10

    for index, row in reviewed.iterrows():
        if not _has_target(row):
            continue
        rule = _build_rule_from_review_row(
            row=row,
            fallback_rule_id=f"manual_review_rule_{index + 1}",
            priority=next_priority,
            confidence=default_confidence,
            review_required_below=review_required_below,
        )
        if rule["rule_id"] in existing_rule_ids:
            continue
        rules.append(rule)
        existing_rule_ids.add(rule["rule_id"])
        next_priority += 10

    payload["rules"] = rules
    with rules_yaml_path.open("w", encoding="utf-8") as file_obj:
        yaml.safe_dump(payload, file_obj, allow_unicode=True, sort_keys=False)
    return rules_yaml_path


def _build_rule_from_review_row(
    *,
    row: pd.Series,
    fallback_rule_id: str,
    priority: int,
    confidence: float,
    review_required_below: float,
) -> dict[str, Any]:
    """Convert a single reviewed CSV row into a YAML rule."""
    rule_id = _build_rule_id(
        str(row.get("suggested_l1", "")),
        str(row.get("suggested_l2", "")),
        str(row.get("suggested_l3", "")),
    ) or fallback_rule_id
    conditions: list[dict[str, Any]] = []

    raw_article = _clean_value(row.get("raw_article", ""))
    raw_description = _clean_value(row.get("raw_description", ""))
    raw_vendor = _clean_value(row.get("raw_vendor", ""))

    if raw_article:
        conditions.append(
            {
                "column": "bit_stati_oborotov_naimenovanie",
                "match_type": "contains_any",
                "values": [raw_article],
            }
        )
    if raw_description:
        conditions.append(
            {
                "column": "naznachenie_platezha",
                "match_type": "contains_any",
                "values": [raw_description],
            }
        )
    if raw_vendor:
        conditions.append(
            {
                "column": "kontragenti_naimenovanie",
                "match_type": "contains_any",
                "values": [raw_vendor],
            }
        )

    return {
        "rule_id": rule_id,
        "priority": priority,
        "confidence": float(row.get("confidence_score", confidence)) if "confidence_score" in row else confidence,
        "target": {
            "l1": str(row.get("suggested_l1", "")).strip(),
            "l2": str(row.get("suggested_l2", "")).strip(),
            "l3": str(row.get("suggested_l3", "")).strip(),
        },
        "conditions": conditions or [
            {
                "column": "bit_stati_oborotov_naimenovanie",
                "match_type": "contains_any",
                "values": ["*"],
            }
        ],
        "review_required_below": review_required_below,
    }


def _has_target(row: pd.Series) -> bool:
    """Check whether a reviewed row has a complete target label."""
    return all(str(row.get(column, "")).strip() for column in ("suggested_l1", "suggested_l2", "suggested_l3"))


def _build_rule_id(l1: str, l2: str, l3: str) -> str:
    """Build a stable rule identifier from target labels."""
    raw = "_".join(part.strip().lower() for part in (l1, l2, l3) if part.strip())
    normalized = re.sub(r"[^0-9a-z_]+", "_", raw).strip("_")
    return normalized


def _clean_value(value: object) -> str:
    """Normalize raw text values for YAML rule generation."""
    return str(value).strip().lower() if str(value).strip() and str(value).strip().lower() != "nan" else ""
