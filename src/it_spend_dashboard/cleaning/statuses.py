"""Business status normalization for payment records."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

STATUS_CONFIG_NAME = "statuses.yaml"
STATUS_COLUMN = "registrator_status_name"
NORMALIZED_STATUS_COLUMN = "business_status"


def normalize_statuses(dataframe: pd.DataFrame, config_dir: Path | None = None) -> pd.DataFrame:
    """Normalize raw registry statuses into business statuses."""
    normalized = dataframe.copy()
    if STATUS_COLUMN not in normalized.columns:
        normalized[NORMALIZED_STATUS_COLUMN] = "other"
        return normalized

    rules = load_status_rules(config_dir)
    raw = normalized[STATUS_COLUMN].astype("string").fillna("").str.strip().str.lower()
    normalized[NORMALIZED_STATUS_COLUMN] = raw.apply(lambda value: map_status(value, rules))
    return normalized


def load_status_rules(config_dir: Path | None = None) -> dict[str, list[str]]:
    """Load status mapping rules from YAML configuration."""
    base_dir = Path(__file__).resolve().parents[3]
    config_path = (config_dir or (base_dir / "config")) / STATUS_CONFIG_NAME
    with config_path.open("r", encoding="utf-8") as file_obj:
        payload = yaml.safe_load(file_obj) or {}
    return {str(key): [str(item).lower() for item in value] for key, value in payload.items()}


def map_status(value: str, rules: dict[str, list[str]]) -> str:
    """Map a raw status value to a business status bucket."""
    for business_status, patterns in rules.items():
        if any(pattern in value for pattern in patterns):
            return business_status
    return "other"

