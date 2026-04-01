"""Data cleaning pipeline for IT expense operations."""

from pathlib import Path

import pandas as pd

from it_spend_dashboard.cleaning.amounts import normalize_amount_columns
from it_spend_dashboard.cleaning.dates import ensure_reporting_years_present, normalize_date_columns
from it_spend_dashboard.cleaning.entities import normalize_entity_columns
from it_spend_dashboard.cleaning.statuses import normalize_statuses
from it_spend_dashboard.cleaning.text import normalize_text_columns


def clean_payments(dataframe: pd.DataFrame, config_dir: Path | None = None) -> pd.DataFrame:
    """Apply the full cleaning pipeline to a raw payments dataset."""
    cleaned = dataframe.copy()
    cleaned = normalize_amount_columns(cleaned)
    cleaned = normalize_statuses(cleaned, config_dir=config_dir)
    cleaned = normalize_date_columns(cleaned)
    cleaned = normalize_text_columns(cleaned)
    cleaned = normalize_entity_columns(cleaned)
    ensure_reporting_years_present(cleaned, required_years=(2025, 2026))
    return cleaned


def run_cleaning_pipeline(
    dataframe: pd.DataFrame,
    output_path: Path | None = None,
    config_dir: Path | None = None,
) -> pd.DataFrame:
    """Clean the payments dataset and persist the interim parquet artifact."""
    base_dir = Path(__file__).resolve().parents[3]
    target = output_path or (base_dir / "data" / "interim" / "payments_clean.parquet")
    cleaned = clean_payments(dataframe, config_dir=config_dir or (base_dir / "config"))
    target.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_parquet(target, index=False)
    return cleaned

