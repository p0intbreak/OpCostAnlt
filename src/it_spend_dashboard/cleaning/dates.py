"""Date normalization helpers for payment records."""

from __future__ import annotations

import pandas as pd

DATE_COLUMNS = [
    "period",
    "quarter_period",
    "bit_zayavka_na_rashodovanie_sredstv_data",
    "bit_platezhnaya_poziciya_data",
]


def normalize_date_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalize date-like columns and derive reporting attributes."""
    normalized = dataframe.copy()

    for column in DATE_COLUMNS:
        if column in normalized.columns:
            normalized[column] = pd.to_datetime(normalized[column], errors="coerce", dayfirst=True)

    base_period = _select_base_period(normalized)
    normalized["year"] = base_period.dt.year.astype("Int64")
    normalized["month"] = base_period.dt.month.astype("Int64")
    normalized["quarter"] = base_period.dt.quarter.astype("Int64")
    year_text = normalized["year"].astype("string")
    month_text = normalized["month"].astype("string").str.zfill(2)
    normalized["year_month"] = year_text.where(normalized["year"].notna(), pd.NA) + "-" + month_text.where(
        normalized["month"].notna(),
        pd.NA,
    )
    return normalized


def ensure_reporting_years_present(dataframe: pd.DataFrame, required_years: tuple[int, ...]) -> None:
    """Validate that all required reporting years are present in the dataset."""
    if "year" not in dataframe.columns:
        raise ValueError("Column 'year' is missing after date normalization.")

    available_years = set(dataframe["year"].dropna().astype(int).tolist())
    missing_years = [year for year in required_years if year not in available_years]
    if missing_years:
        raise ValueError(f"Missing required reporting years: {missing_years}")


def _select_base_period(dataframe: pd.DataFrame) -> pd.Series:
    """Choose the best available date column to derive reporting fields."""
    for column in ("period", "bit_platezhnaya_poziciya_data", "bit_zayavka_na_rashodovanie_sredstv_data", "quarter_period"):
        if column in dataframe.columns:
            return dataframe[column]
    return pd.Series(pd.NaT, index=dataframe.index, dtype="datetime64[ns]")

