"""Article-focused rule matching utilities."""

from __future__ import annotations

from it_spend_dashboard.classification.taxonomy import ClassificationRule

ARTICLE_COLUMNS = {
    "bit_stati_oborotov_naimenovanie",
    "bit_stati_oborotov_kodifikator",
    "p_bit_tipi_statei_oborotov_synonim",
    "p_bit_vidi_denezhnih_sredstv_synonim",
}


def match_article_rule(record: dict[str, str], rule: ClassificationRule) -> bool:
    """Return whether a rule has a positive article-focused signal."""
    for condition in rule.conditions:
        if condition.column not in ARTICLE_COLUMNS:
            continue
        value = _normalize(record.get(condition.column, ""))
        if _condition_matches(value, condition.values):
            return True
    return False


def _condition_matches(value: str, patterns: list[str]) -> bool:
    """Check a normalized string against article patterns."""
    if "*" in patterns:
        return True
    return any(pattern.lower() in value for pattern in patterns)


def _normalize(value: str) -> str:
    """Normalize article text before comparison."""
    return str(value).strip().lower()

