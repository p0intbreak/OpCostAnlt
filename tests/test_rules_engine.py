"""Unit tests for the rule-based spend classification engine."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from it_spend_dashboard.classification.rules_engine import classify_payments
from it_spend_dashboard.classification.taxonomy import load_classification_rules


def test_article_rules_have_highest_priority() -> None:
    """Prefer article-driven rules over vendor-driven matches."""
    rules = load_classification_rules(Path("config") / "classification_rules.yaml")
    dataframe = pd.DataFrame(
        [
            {
                "bit_stati_oborotov_naimenovanie": "hosting services",
                "bit_stati_oborotov_kodifikator": "IT001",
                "kontragenti_naimenovanie": "kaspersky",
                "dogovori_kontragentov_naimenovanie": "hosting agreement",
                "proekti_naimenovanie": "",
                "podrazdeleniya_naimenovanie": "it operations",
                "p_bit_tipi_statei_oborotov_synonim": "",
                "p_bit_vidi_denezhnih_sredstv_synonim": "",
                "naznachenie_platezha": "monthly hosting payment",
            }
        ]
    )

    classified, review_queue = classify_payments(dataframe, rules)

    assert classified.loc[0, "l1_category"] == "infrastructure"
    assert classified.loc[0, "classification_rule_id"] == "infra_cloud_hosting"
    assert classified.loc[0, "classification_confidence"] == "high"
    assert classified.loc[0, "matched_rule_id"] == "infra_cloud_hosting"
    assert classified.loc[0, "matched_article_pattern"] in {"hosting", "cloud", "infrastructure"}
    assert classified.loc[0, "classification_reason_human"]
    assert review_queue.empty


def test_vendor_rules_are_used_second() -> None:
    """Use vendor evidence when article-focused rules do not match."""
    rules = load_classification_rules(Path("config") / "classification_rules.yaml")
    dataframe = pd.DataFrame(
        [
            {
                "bit_stati_oborotov_naimenovanie": "security subscription",
                "bit_stati_oborotov_kodifikator": "",
                "kontragenti_naimenovanie": "kaspersky lab",
                "dogovori_kontragentov_naimenovanie": "annual support",
                "proekti_naimenovanie": "",
                "podrazdeleniya_naimenovanie": "security",
                "p_bit_tipi_statei_oborotov_synonim": "",
                "p_bit_vidi_denezhnih_sredstv_synonim": "",
                "naznachenie_platezha": "",
            }
        ]
    )

    classified, _ = classify_payments(dataframe, rules)

    assert classified.loc[0, "l1_category"] == "information_security"
    assert classified.loc[0, "l3_category"] == "endpoint_protection"
    assert "vendor" in classified.loc[0, "classification_reason"]
    assert classified.loc[0, "matched_vendor_pattern"] in {"kaspersky", "positive technologies"}


def test_low_and_unclassified_rows_go_to_review_queue() -> None:
    """Route weak classifications and unmatched rows into the review queue."""
    rules = load_classification_rules(Path("config") / "classification_rules.yaml")
    dataframe = pd.DataFrame(
        [
            {
                "bit_stati_oborotov_naimenovanie": "misc payment",
                "bit_stati_oborotov_kodifikator": "",
                "kontragenti_naimenovanie": "unknown vendor",
                "dogovori_kontragentov_naimenovanie": "",
                "proekti_naimenovanie": "",
                "podrazdeleniya_naimenovanie": "",
                "p_bit_tipi_statei_oborotov_synonim": "",
                "p_bit_vidi_denezhnih_sredstv_synonim": "",
                "naznachenie_platezha": "",
            }
        ]
    )

    classified, review_queue = classify_payments(dataframe, rules)

    assert classified.loc[0, "classification_confidence"] == "unclassified"
    assert classified.loc[0, "review_required"]
    assert len(review_queue) == 1
    assert review_queue.loc[0, "review_reason"] == "No matching classification rule"


def test_keyword_score_supports_rule_selection() -> None:
    """Use article/description/contract keywords to classify development spend."""
    rules = load_classification_rules(Path("config") / "classification_rules.yaml")
    dataframe = pd.DataFrame(
        [
            {
                "bit_stati_oborotov_naimenovanie": "service fee",
                "bit_stati_oborotov_kodifikator": "",
                "kontragenti_naimenovanie": "outsource partner",
                "dogovori_kontragentov_naimenovanie": "implementation support contract",
                "proekti_naimenovanie": "crm rollout",
                "podrazdeleniya_naimenovanie": "it delivery",
                "p_bit_tipi_statei_oborotov_synonim": "",
                "p_bit_vidi_denezhnih_sredstv_synonim": "",
                "naznachenie_platezha": "crm implementation support services",
            }
        ]
    )

    classified, _ = classify_payments(dataframe, rules)

    assert classified.loc[0, "l1_category"] == "development_and_support"
    assert classified.loc[0, "classification_confidence"] in {"medium", "high"}
    assert "keywords=" in classified.loc[0, "classification_reason"]
    assert classified.loc[0, "matched_keywords"]
