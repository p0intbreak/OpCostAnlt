"""Text cleanup helpers for payment descriptions and labels."""

from __future__ import annotations

import re

import pandas as pd

TEXT_COLUMNS = [
    "bit_stati_oborotov_naimenovanie",
    "naznachenie_platezha",
    "kontragenti_naimenovanie",
    "dogovori_kontragentov_naimenovanie",
]


def normalize_text_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalize core text columns with lowercase, trim, and whitespace cleanup."""
    normalized = dataframe.copy()

    for column in TEXT_COLUMNS:
        if column in normalized.columns:
            normalized[column] = clean_text_series(normalized[column])

    return normalized


def clean_text_series(series: pd.Series) -> pd.Series:
    """Normalize whitespace and casing for a text series."""
    text = series.astype("string")
    text = text.str.strip().str.lower()
    text = text.str.replace(r"\s+", " ", regex=True)
    return text


def tokenize_text(value: str) -> list[str]:
    """Split normalized text into alphanumeric tokens."""
    return [token for token in re.split(r"[^0-9a-zA-Zа-яА-Я]+", value.lower()) if token]

