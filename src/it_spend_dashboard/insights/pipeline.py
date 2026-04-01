"""Insight generation pipeline for modeled IT expense data."""

from pathlib import Path

import pandas as pd


def run_insights_pipeline(dataframe: pd.DataFrame, export_dir: Path | None = None) -> list[str]:
    """Generate placeholder insights from the modeled dataset."""
    _ = dataframe
    _ = export_dir
    return ["No insights implemented yet."]

