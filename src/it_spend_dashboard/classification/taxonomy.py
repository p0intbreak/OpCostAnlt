"""Load and validate configurable IT spend taxonomy and classification rules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

FEATURE_COLUMNS = [
    "bit_stati_oborotov_naimenovanie",
    "bit_stati_oborotov_kodifikator",
    "naznachenie_platezha",
    "kontragenti_naimenovanie",
    "dogovori_kontragentov_naimenovanie",
    "proekti_naimenovanie",
    "podrazdeleniya_naimenovanie",
    "p_bit_tipi_statei_oborotov_synonim",
    "p_bit_vidi_denezhnih_sredstv_synonim",
]
SUPPORTED_MATCH_TYPES = {"contains_any", "equals_any", "regex_any", "in_list"}


class TaxonomyNode(BaseModel):
    """Single L1 taxonomy node with nested L2/L3 values."""

    model_config = ConfigDict(extra="forbid")

    description: str
    children: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_children(self) -> "TaxonomyNode":
        """Ensure that every L2 bucket declares at least one L3 value."""
        for l2_name, l3_values in self.children.items():
            if not l3_values:
                raise ValueError(f"Taxonomy node '{l2_name}' must contain at least one L3 category.")
        return self


class TaxonomyTree(BaseModel):
    """Full configurable taxonomy for IT department expenses."""

    model_config = ConfigDict(extra="forbid")

    taxonomy: dict[str, TaxonomyNode]


class ClassificationCondition(BaseModel):
    """Single field-level matching rule used by the classifier."""

    model_config = ConfigDict(extra="forbid")

    column: str
    match_type: str
    values: list[str]

    @model_validator(mode="after")
    def validate_condition(self) -> "ClassificationCondition":
        """Validate supported feature columns and matching modes."""
        if self.column not in FEATURE_COLUMNS:
            raise ValueError(f"Unsupported feature column: {self.column}")
        if self.match_type not in SUPPORTED_MATCH_TYPES:
            raise ValueError(f"Unsupported match type: {self.match_type}")
        if not self.values:
            raise ValueError("Condition values must not be empty.")
        return self


class ClassificationTarget(BaseModel):
    """L1/L2/L3 target category for a classification rule."""

    model_config = ConfigDict(extra="forbid")

    l1: str
    l2: str
    l3: str


class ClassificationRule(BaseModel):
    """Single YAML-defined classification rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    priority: int
    confidence: float = Field(ge=0.0, le=1.0)
    target: ClassificationTarget
    conditions: list[ClassificationCondition]
    review_required_below: float = Field(default=0.75, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_rule(self) -> "ClassificationRule":
        """Ensure rules carry at least one condition."""
        if not self.conditions:
            raise ValueError(f"Rule '{self.rule_id}' must contain at least one condition.")
        return self


class ClassificationRuleset(BaseModel):
    """Full ruleset loaded from YAML configuration."""

    model_config = ConfigDict(extra="forbid")

    rules: list[ClassificationRule]


def load_category_taxonomy(path: Path) -> TaxonomyTree:
    """Load taxonomy YAML and parse it into a typed model."""
    payload = _read_yaml(path)
    return TaxonomyTree.model_validate(payload)


def load_classification_rules(path: Path) -> ClassificationRuleset:
    """Load classification rules YAML and parse it into a typed model."""
    payload = _read_yaml(path)
    return ClassificationRuleset.model_validate(payload)


def validate_taxonomy_tree(taxonomy: TaxonomyTree) -> None:
    """Validate uniqueness and completeness of the taxonomy tree."""
    if not taxonomy.taxonomy:
        raise ValueError("Taxonomy tree must contain at least one L1 category.")

    for l1_name, node in taxonomy.taxonomy.items():
        if not node.children:
            raise ValueError(f"L1 category '{l1_name}' must contain at least one L2 category.")


def validate_classification_rules(ruleset: ClassificationRuleset, taxonomy: TaxonomyTree) -> None:
    """Validate that every classification rule points to a valid taxonomy node."""
    seen_rule_ids: set[str] = set()

    for rule in ruleset.rules:
        if rule.rule_id in seen_rule_ids:
            raise ValueError(f"Duplicate classification rule_id: {rule.rule_id}")
        seen_rule_ids.add(rule.rule_id)
        _validate_target(rule.target, taxonomy)


def _validate_target(target: ClassificationTarget, taxonomy: TaxonomyTree) -> None:
    """Ensure a rule target exists in the taxonomy definition."""
    l1_node = taxonomy.taxonomy.get(target.l1)
    if l1_node is None:
        raise ValueError(f"Unknown L1 category in rule target: {target.l1}")

    l3_values = l1_node.children.get(target.l2)
    if l3_values is None:
        raise ValueError(f"Unknown L2 category '{target.l2}' under L1 '{target.l1}'")

    if target.l3 not in l3_values:
        raise ValueError(
            f"Unknown L3 category '{target.l3}' under L1 '{target.l1}' and L2 '{target.l2}'"
        )


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read YAML configuration from disk."""
    with path.open("r", encoding="utf-8") as file_obj:
        return yaml.safe_load(file_obj) or {}
