"""Rule-based classification engine for IT spend records."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from it_spend_dashboard.classification.article_matcher import match_article_rule
from it_spend_dashboard.classification.confidence import compose_confidence_score, confidence_bucket
from it_spend_dashboard.classification.keyword_matcher import compute_keyword_score, extract_keywords
from it_spend_dashboard.classification.review_queue import build_review_queue
from it_spend_dashboard.classification.taxonomy import ClassificationRule, ClassificationRuleset
from it_spend_dashboard.classification.vendor_matcher import match_vendor_rule

CLASSIFICATION_INPUT_COLUMNS = [
    "bit_stati_oborotov_naimenovanie",
    "bit_stati_oborotov_kodifikator",
    "kontragenti_naimenovanie",
    "dogovori_kontragentov_naimenovanie",
    "proekti_naimenovanie",
    "podrazdeleniya_naimenovanie",
    "p_bit_tipi_statei_oborotov_synonim",
    "p_bit_vidi_denezhnih_sredstv_synonim",
    "naznachenie_platezha",
]


@dataclass(frozen=True)
class RuleMatchResult:
    """Structured classification result for a single record."""

    l1_category: str
    l2_category: str
    l3_category: str
    classification_reason: str
    classification_reason_human: str
    classification_confidence: str
    classification_confidence_score: float
    classification_rule_id: str | None
    matched_rule_id: str | None
    matched_keywords: list[str]
    matched_vendor_pattern: str | None
    matched_article_pattern: str | None
    review_required: bool


def classify_payments(dataframe: pd.DataFrame, ruleset: ClassificationRuleset) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Classify a payments DataFrame and return classified rows plus a review queue."""
    classified = dataframe.copy()
    results = [
        classify_record(_record_to_dict(record), ruleset)
        for record in classified.to_dict(orient="records")
    ]

    classified["l1_category"] = [result.l1_category for result in results]
    classified["l2_category"] = [result.l2_category for result in results]
    classified["l3_category"] = [result.l3_category for result in results]
    classified["classification_reason"] = [result.classification_reason for result in results]
    classified["classification_reason_human"] = [result.classification_reason_human for result in results]
    classified["classification_confidence"] = [result.classification_confidence for result in results]
    classified["classification_confidence_score"] = [result.classification_confidence_score for result in results]
    classified["classification_rule_id"] = [result.classification_rule_id for result in results]
    classified["matched_rule_id"] = [result.matched_rule_id for result in results]
    classified["matched_keywords"] = [", ".join(result.matched_keywords) for result in results]
    classified["matched_vendor_pattern"] = [result.matched_vendor_pattern for result in results]
    classified["matched_article_pattern"] = [result.matched_article_pattern for result in results]
    classified["review_required"] = [result.review_required for result in results]

    review_queue = build_review_queue(classified)
    return classified, review_queue


def classify_record(record: dict[str, str], ruleset: ClassificationRuleset) -> RuleMatchResult:
    """Classify a single normalized record according to rule priorities."""
    ordered_rules = sorted(ruleset.rules, key=lambda item: item.priority)

    article_matches: list[ClassificationRule] = []
    vendor_matches: list[ClassificationRule] = []
    keyword_candidates: list[tuple[ClassificationRule, float]] = []

    for rule in ordered_rules:
        article_matched = match_article_rule(record, rule)
        vendor_matched = match_vendor_rule(record, rule)
        keyword_score = _rule_keyword_score(record, rule)

        if article_matched:
            article_matches.append(rule)
            continue
        if vendor_matched:
            vendor_matches.append(rule)
            continue
        if keyword_score > 0.0:
            keyword_candidates.append((rule, keyword_score))

    if article_matches:
        return _build_match_result(record, article_matches[0], article_matched=True, vendor_matched=match_vendor_rule(record, article_matches[0]))
    if vendor_matches:
        return _build_match_result(record, vendor_matches[0], article_matched=False, vendor_matched=True)
    if keyword_candidates:
        rule, _ = sorted(
            keyword_candidates,
            key=lambda item: (-item[1], item[0].priority),
        )[0]
        return _build_match_result(record, rule, article_matched=False, vendor_matched=False)

    return RuleMatchResult(
        l1_category="other_it",
        l2_category="unclassified",
        l3_category="review_required",
        classification_reason="No article, vendor, or keyword rule matched.",
        classification_reason_human="Категория не определена автоматически: ни правило по статье, ни правило по поставщику, ни ключевые слова не дали уверенного совпадения.",
        classification_confidence="unclassified",
        classification_confidence_score=0.0,
        classification_rule_id=None,
        matched_rule_id=None,
        matched_keywords=[],
        matched_vendor_pattern=None,
        matched_article_pattern=None,
        review_required=True,
    )


def _build_match_result(
    record: dict[str, str],
    rule: ClassificationRule,
    *,
    article_matched: bool,
    vendor_matched: bool,
) -> RuleMatchResult:
    """Create a structured result from the selected matching rule."""
    matched_keywords = _matched_keywords(record, rule)
    keyword_score = compute_keyword_score(record, matched_keywords)
    matched_vendor_pattern = _matched_vendor_pattern(record, rule) if vendor_matched else None
    matched_article_pattern = _matched_article_pattern(record, rule) if article_matched else None
    numeric_confidence = compose_confidence_score(
        base_confidence=rule.confidence,
        article_matched=article_matched,
        vendor_matched=vendor_matched,
        keyword_score=keyword_score,
    )
    confidence = confidence_bucket(numeric_confidence)
    review_required = confidence in {"low", "unclassified"} or numeric_confidence < rule.review_required_below
    reason = _build_reason(
        rule,
        article_matched=article_matched,
        vendor_matched=vendor_matched,
        keyword_score=keyword_score,
    )
    reason_human = _build_human_reason(
        rule,
        article_pattern=matched_article_pattern,
        vendor_pattern=matched_vendor_pattern,
        keywords=matched_keywords,
    )
    return RuleMatchResult(
        l1_category=rule.target.l1,
        l2_category=rule.target.l2,
        l3_category=rule.target.l3,
        classification_reason=reason,
        classification_reason_human=reason_human,
        classification_confidence=confidence,
        classification_confidence_score=round(numeric_confidence, 4),
        classification_rule_id=rule.rule_id,
        matched_rule_id=rule.rule_id,
        matched_keywords=matched_keywords,
        matched_vendor_pattern=matched_vendor_pattern,
        matched_article_pattern=matched_article_pattern,
        review_required=review_required,
    )


def _rule_keyword_score(record: dict[str, str], rule: ClassificationRule) -> float:
    """Score keyword evidence from rule conditions and record text fields."""
    return compute_keyword_score(record, _matched_keywords(record, rule))


def _build_reason(
    rule: ClassificationRule,
    *,
    article_matched: bool,
    vendor_matched: bool,
    keyword_score: float,
) -> str:
    """Build a human-readable classification reason."""
    evidence: list[str] = []
    if article_matched:
        evidence.append("article")
    if vendor_matched:
        evidence.append("vendor")
    if keyword_score > 0.0:
        evidence.append(f"keywords={keyword_score:.2f}")
    evidence_text = ", ".join(evidence) if evidence else "rule fallback"
    return f"Matched rule '{rule.rule_id}' using {evidence_text}."


def _build_human_reason(
    rule: ClassificationRule,
    *,
    article_pattern: str | None,
    vendor_pattern: str | None,
    keywords: list[str],
) -> str:
    """Build a user-facing explanation for why the row was classified."""
    fragments: list[str] = [f"Применено правило {rule.rule_id}."]
    if article_pattern:
        fragments.append(f"Совпала статья/код с шаблоном '{article_pattern}'.")
    if vendor_pattern:
        fragments.append(f"Совпал поставщик или договор с шаблоном '{vendor_pattern}'.")
    if keywords:
        fragments.append(f"Дополнительно сработали ключевые слова: {', '.join(keywords)}.")
    fragments.append(
        f"Запись отнесена в категорию {rule.target.l1} / {rule.target.l2} / {rule.target.l3}."
    )
    return " ".join(fragments)


def _matched_keywords(record: dict[str, str], rule: ClassificationRule) -> list[str]:
    """Return the subset of rule keywords that actually matched the record."""
    matched: list[str] = []
    text_fields = [
        _normalize(record.get("bit_stati_oborotov_naimenovanie", "")),
        _normalize(record.get("naznachenie_platezha", "")),
        _normalize(record.get("dogovori_kontragentov_naimenovanie", "")),
    ]
    for condition in rule.conditions:
        if condition.column in {
            "bit_stati_oborotov_naimenovanie",
            "naznachenie_platezha",
            "dogovori_kontragentov_naimenovanie",
        }:
            for keyword in extract_keywords(condition.values):
                if keyword and any(keyword in field for field in text_fields):
                    matched.append(keyword)
    return list(dict.fromkeys(matched))


def _matched_vendor_pattern(record: dict[str, str], rule: ClassificationRule) -> str | None:
    """Return the matched vendor-related pattern when available."""
    for condition in rule.conditions:
        if condition.column in {"kontragenti_naimenovanie", "dogovori_kontragentov_naimenovanie"}:
            value = _normalize(record.get(condition.column, ""))
            for pattern in condition.values:
                normalized = _normalize(pattern)
                if normalized == "*" or normalized in value:
                    return pattern
    return None


def _matched_article_pattern(record: dict[str, str], rule: ClassificationRule) -> str | None:
    """Return the matched article-related pattern when available."""
    for condition in rule.conditions:
        if condition.column in {
            "bit_stati_oborotov_naimenovanie",
            "bit_stati_oborotov_kodifikator",
            "p_bit_tipi_statei_oborotov_synonim",
            "p_bit_vidi_denezhnih_sredstv_synonim",
        }:
            value = _normalize(record.get(condition.column, ""))
            for pattern in condition.values:
                normalized = _normalize(pattern)
                if normalized == "*" or normalized in value:
                    return pattern
    return None


def _record_to_dict(record: dict[str, object]) -> dict[str, str]:
    """Project the input record into a normalized string dictionary."""
    projected: dict[str, str] = {}
    for column in CLASSIFICATION_INPUT_COLUMNS:
        value = record.get(column, "")
        projected[column] = "" if pd.isna(value) else str(value)
    return projected


def _normalize(value: str) -> str:
    """Normalize raw string values for rule matching."""
    return str(value).strip().lower()
