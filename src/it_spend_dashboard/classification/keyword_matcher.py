"""Keyword-based matching utilities for IT spend classification."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

TEXT_SCORE_COLUMNS = [
    "bit_stati_oborotov_naimenovanie",
    "naznachenie_platezha",
    "dogovori_kontragentov_naimenovanie",
]
WEIGHTS = {
    "bit_stati_oborotov_naimenovanie": 0.5,
    "naznachenie_platezha": 0.3,
    "dogovori_kontragentov_naimenovanie": 0.2,
}


def compute_keyword_score(record: dict[str, str], keywords: Sequence[str]) -> float:
    """Compute a normalized keyword match score across article, description, and contract."""
    normalized_keywords = [_normalize(keyword) for keyword in keywords if _normalize(keyword)]
    if not normalized_keywords:
        return 0.0

    score = 0.0
    for column in TEXT_SCORE_COLUMNS:
        value = _normalize(record.get(column, ""))
        if not value:
            continue
        if any(keyword in value for keyword in normalized_keywords):
            score += WEIGHTS[column]

    return min(score, 1.0)


def extract_keywords(values: Iterable[str]) -> list[str]:
    """Extract non-empty keywords from a sequence of rule values."""
    return [keyword for keyword in (_normalize(value) for value in values) if keyword and keyword != "*"]


def _normalize(value: str) -> str:
    """Normalize a text value for keyword comparison."""
    return str(value).strip().lower()

