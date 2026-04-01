"""Unit tests for semi-automatic review queue and manual labeling utilities."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from it_spend_dashboard.classification.manual_labeling import apply_manual_labels_to_rules
from it_spend_dashboard.classification.review_queue import build_review_queue, save_review_queue


def test_build_review_queue_returns_training_sample_columns() -> None:
    """Build the review queue in the expected CSV training-sample shape."""
    dataframe = pd.DataFrame(
        [
            {
                "article_name": "hosting",
                "naznachenie_platezha": "monthly cloud hosting",
                "vendor_name": "vendor a",
                "l1_category": "infrastructure",
                "l2_category": "cloud_and_hosting",
                "l3_category": "managed_hosting",
                "classification_confidence": "low",
                "classification_reason": "Matched weak keyword rule.",
            },
            {
                "article_name": "licenses",
                "vendor_name": "vendor b",
                "l1_category": "software_and_licenses",
                "l2_category": "productivity_and_collaboration",
                "l3_category": "office_suites",
                "classification_confidence": "high",
                "classification_reason": "Matched vendor rule.",
            },
        ]
    )

    queue = build_review_queue(dataframe)

    assert list(queue.columns) == [
        "raw_article",
        "raw_description",
        "raw_vendor",
        "suggested_l1",
        "suggested_l2",
        "suggested_l3",
        "confidence",
        "reason",
    ]
    assert len(queue) == 1
    assert queue.loc[0, "raw_article"] == "hosting"


def test_save_review_queue_writes_csv(tmp_path: Path) -> None:
    """Persist the review queue as classifier_training_sample.csv."""
    dataframe = pd.DataFrame(
        [
            {
                "article_name": "misc",
                "vendor_name": "vendor x",
                "l1_category": "other_it",
                "l2_category": "unclassified",
                "l3_category": "review_required",
                "classification_confidence": "unclassified",
                "classification_reason": "No matching rule.",
            }
        ]
    )
    output_path = tmp_path / "classifier_training_sample.csv"

    save_review_queue(dataframe, output_path)

    assert output_path.exists()
    restored = pd.read_csv(output_path)
    assert "raw_article" in restored.columns


def test_apply_manual_labels_to_rules_appends_yaml_rule(tmp_path: Path) -> None:
    """Append a reviewed training sample back into classification_rules.yaml."""
    csv_path = tmp_path / "classifier_training_sample.csv"
    rules_path = tmp_path / "classification_rules.yaml"

    pd.DataFrame(
        [
            {
                "raw_article": "vpn services",
                "raw_description": "branch vpn connectivity",
                "raw_vendor": "vendor net",
                "suggested_l1": "communications",
                "suggested_l2": "connectivity",
                "suggested_l3": "vpn",
                "confidence": "low",
                "reason": "Needs manual review",
            }
        ]
    ).to_csv(csv_path, index=False)

    rules_path.write_text("rules: []\n", encoding="utf-8")
    apply_manual_labels_to_rules(csv_path, rules_path)

    payload = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    assert len(payload["rules"]) == 1
    assert payload["rules"][0]["target"]["l3"] == "vpn"
    assert payload["rules"][0]["conditions"][0]["column"] == "bit_stati_oborotov_naimenovanie"
