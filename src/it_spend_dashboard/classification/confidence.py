"""Confidence helpers for rule-based spend classification."""

from __future__ import annotations


def confidence_bucket(score: float) -> str:
    """Convert a numeric confidence score into a stable bucket."""
    if score >= 0.85:
        return "high"
    if score >= 0.65:
        return "medium"
    if score > 0.0:
        return "low"
    return "unclassified"


def compose_confidence_score(
    *,
    base_confidence: float,
    article_matched: bool,
    vendor_matched: bool,
    keyword_score: float,
) -> float:
    """Blend rule confidence with evidence signals into a bounded numeric score."""
    score = base_confidence
    if article_matched:
        score += 0.1
    if vendor_matched:
        score += 0.05
    score += keyword_score * 0.15
    return max(0.0, min(score, 1.0))

