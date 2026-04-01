"""Analytical modeling pipeline for IT spend datasets."""

import pandas as pd


def run_modeling_pipeline(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return a modeled dataset enriched with placeholder metrics."""
    modeled = dataframe.copy()
    modeled["reporting_month"] = modeled["operation_date"]
    return modeled

