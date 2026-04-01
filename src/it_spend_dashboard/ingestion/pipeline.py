"""Orchestration for raw data ingestion from 1C CSV exports."""

from pathlib import Path

import pandas as pd

from it_spend_dashboard.ingestion.load_csv import load_payments_csv
from it_spend_dashboard.ingestion.normalize_columns import normalize_columns
from it_spend_dashboard.ingestion.schema import validate_required_columns


def run_ingestion_pipeline(
    csv_path: Path | None = None,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Load a raw 1C CSV export, normalize columns, validate, and persist parquet."""
    base_dir = Path(__file__).resolve().parents[3]
    source = csv_path or (base_dir / "data" / "raw" / "payments.csv")
    target = output_path or (base_dir / "data" / "interim" / "payments_clean.parquet")

    dataframe = load_payments_csv(source)
    normalized, mapping = normalize_columns(dataframe)
    validate_required_columns(normalized)

    original_columns = {
        alias: original_name
        for original_name, alias in mapping.items()
    }
    normalized.attrs["original_columns"] = original_columns

    target.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_parquet(target, index=False)
    return normalized
