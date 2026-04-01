"""Classification pipeline for assigning cost categories to transactions."""

from pathlib import Path

import pandas as pd

from it_spend_dashboard.classification.review_queue import save_review_queue
from it_spend_dashboard.classification.rules_engine import classify_payments
from it_spend_dashboard.classification.taxonomy import (
    load_category_taxonomy,
    load_classification_rules,
    validate_classification_rules,
    validate_taxonomy_tree,
)


def run_classification_pipeline(
    dataframe: pd.DataFrame,
    config_dir: Path | None = None,
    review_queue_output_path: Path | None = None,
) -> pd.DataFrame:
    """Validate config and classify payments with a rule-based engine."""
    base_dir = Path(__file__).resolve().parents[3]
    resolved_config_dir = config_dir or (base_dir / "config")
    review_path = review_queue_output_path or (base_dir / "data" / "interim" / "classifier_training_sample.csv")

    taxonomy = load_category_taxonomy(resolved_config_dir / "category_taxonomy.yaml")
    rules = load_classification_rules(resolved_config_dir / "classification_rules.yaml")
    validate_taxonomy_tree(taxonomy)
    validate_classification_rules(rules, taxonomy)

    classified, review_queue = classify_payments(dataframe, rules)
    classified.attrs["review_queue"] = review_queue
    save_review_queue(classified, review_path)
    classified.attrs["review_queue_path"] = review_path
    return classified
