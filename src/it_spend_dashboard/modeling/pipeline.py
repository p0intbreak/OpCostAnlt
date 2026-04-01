"""Analytical modeling pipeline for IT spend datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from it_spend_dashboard.modeling.aggregations import build_aggregations
from it_spend_dashboard.modeling.dimensions import build_dimensions
from it_spend_dashboard.modeling.facts import build_payments_fact


def run_modeling_pipeline(
    dataframe: pd.DataFrame,
    output_dir: Path | None = None,
) -> pd.DataFrame:
    """Build facts, dimensions, and aggregates, then persist them to parquet."""
    base_dir = Path(__file__).resolve().parents[3]
    target_dir = output_dir or (base_dir / "data" / "processed")
    target_dir.mkdir(parents=True, exist_ok=True)

    payments_fact = build_payments_fact(dataframe)
    dimensions = build_dimensions(payments_fact)
    aggregations = build_aggregations(payments_fact)

    payments_fact.to_parquet(target_dir / "payments_fact.parquet", index=False)
    for name, dimension in dimensions.items():
        dimension.to_parquet(target_dir / f"{name}.parquet", index=False)
    for name, aggregation in aggregations.items():
        aggregation.to_parquet(target_dir / f"{name}.parquet", index=False)

    payments_fact.attrs["dimension_tables"] = sorted(dimensions)
    payments_fact.attrs["aggregation_tables"] = sorted(aggregations)
    payments_fact.attrs["processed_output_dir"] = str(target_dir)
    return payments_fact
