"""Unit tests for taxonomy and classification config validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from it_spend_dashboard.classification.taxonomy import (
    load_category_taxonomy,
    load_classification_rules,
    validate_classification_rules,
    validate_taxonomy_tree,
)


def test_load_and_validate_taxonomy_configs() -> None:
    """Load production taxonomy and rules configs and validate cross-references."""
    config_dir = Path("config")
    taxonomy = load_category_taxonomy(config_dir / "category_taxonomy.yaml")
    rules = load_classification_rules(config_dir / "classification_rules.yaml")

    validate_taxonomy_tree(taxonomy)
    validate_classification_rules(rules, taxonomy)

    assert "infrastructure" in taxonomy.taxonomy
    assert rules.rules[0].target.l1 in taxonomy.taxonomy


def test_validate_classification_rules_raises_for_unknown_target(tmp_path: Path) -> None:
    """Fail validation when a rule points to a missing L3 taxonomy node."""
    taxonomy_path = tmp_path / "category_taxonomy.yaml"
    rules_path = tmp_path / "classification_rules.yaml"

    taxonomy_path.write_text(
        "\n".join(
            [
                "taxonomy:",
                "  infrastructure:",
                '    description: "Core infra"',
                "    children:",
                "      cloud_and_hosting:",
                "        - iaas",
            ]
        ),
        encoding="utf-8",
    )
    rules_path.write_text(
        "\n".join(
            [
                "rules:",
                '  - rule_id: "broken_rule"',
                "    priority: 1",
                "    confidence: 0.9",
                "    target:",
                "      l1: infrastructure",
                "      l2: cloud_and_hosting",
                "      l3: missing_bucket",
                "    conditions:",
                "      - column: bit_stati_oborotov_naimenovanie",
                "        match_type: contains_any",
                "        values:",
                '          - "hosting"',
            ]
        ),
        encoding="utf-8",
    )

    taxonomy = load_category_taxonomy(taxonomy_path)
    rules = load_classification_rules(rules_path)

    with pytest.raises(ValueError, match="Unknown L3 category"):
        validate_classification_rules(rules, taxonomy)
