"""Entity normalization helpers for organizations and counterparties."""

from __future__ import annotations

import pandas as pd

ENTITY_COLUMNS = [
    "organizacii_naimenovanie",
    "podrazdeleniya_naimenovanie",
    "proekti_naimenovanie",
    "kontragenti_naimenovanie",
]


def normalize_entity_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalize key entity dimensions to a comparable canonical form."""
    normalized = dataframe.copy()

    for column in ENTITY_COLUMNS:
        if column in normalized.columns:
            normalized[column] = _normalize_entity_series(normalized[column])

    return normalized


def _normalize_entity_series(series: pd.Series) -> pd.Series:
    """Canonicalize entity names by trimming and collapsing whitespace."""
    text = series.astype("string")
    text = text.str.strip().str.lower()
    text = text.str.replace(r"\s+", " ", regex=True)
    return text

