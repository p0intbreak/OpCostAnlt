"""Normalization helpers for amount columns in expense datasets."""

from __future__ import annotations

import pandas as pd

AMOUNT_COLUMNS = [
    "summa",
    "summa_regl",
    "summa_upr",
    "summa_vzaimorascheti",
]


def normalize_amount_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Convert known amount columns to numeric values with locale-safe parsing."""
    normalized = dataframe.copy()

    for column in AMOUNT_COLUMNS:
        if column in normalized.columns:
            normalized[column] = _to_numeric_series(normalized[column])

    return normalized


def _to_numeric_series(series: pd.Series) -> pd.Series:
    """Convert a mixed-format numeric series into pandas float values."""
    text = series.astype("string")
    text = text.str.replace("\u00a0", "", regex=False)
    text = text.str.replace(" ", "", regex=False)
    text = text.str.replace(",", ".", regex=False)
    text = text.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "<NA>": pd.NA})
    return pd.to_numeric(text, errors="coerce")

