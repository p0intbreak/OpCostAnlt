"""Vendor-focused rule matching utilities."""

from __future__ import annotations

from it_spend_dashboard.classification.taxonomy import ClassificationRule

VENDOR_COLUMNS = {
    "kontragenti_naimenovanie",
    "dogovori_kontragentov_naimenovanie",
}


def match_vendor_rule(record: dict[str, str], rule: ClassificationRule) -> bool:
    """Return whether a rule has a vendor/contract match against the record."""
    for condition in rule.conditions:
        if condition.column not in VENDOR_COLUMNS:
            continue
        value = _normalize(record.get(condition.column, ""))
        if _condition_matches(value, condition.values):
            return True
    return False


def _condition_matches(value: str, patterns: list[str]) -> bool:
    """Check a normalized string against a list of vendor patterns."""
    if "*" in patterns:
        return True
    return any(pattern.lower() in value for pattern in patterns)


def _normalize(value: str) -> str:
    """Normalize vendor text before comparison."""
    return str(value).strip().lower()

