"""Fact table builders for dashboard-ready IT spend analytics."""

from __future__ import annotations

import hashlib

import pandas as pd


def build_payments_fact(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Build the canonical payments fact table at one row per payment operation."""
    fact = dataframe.copy()
    fact["payment_id"] = _build_payment_ids(fact)
    fact["period_date"] = pd.to_datetime(fact.get("period"), errors="coerce")
    fact["year"] = _prefer_column(fact, "year", fact["period_date"].dt.year).astype("Int64")
    fact["month"] = _prefer_column(fact, "month", fact["period_date"].dt.month).astype("Int64")
    fact["quarter"] = _prefer_column(fact, "quarter", fact["period_date"].dt.quarter).astype("Int64")
    fact["amount"] = pd.to_numeric(fact.get("summa"), errors="coerce").fillna(0.0)
    fact["status_raw"] = _series_or_default(fact, "registrator_status_name")
    fact["status_group"] = _series_or_default(fact, "business_status")
    fact["article_name"] = _series_or_default(fact, "bit_stati_oborotov_naimenovanie")
    fact["article_code"] = _series_or_default(fact, "bit_stati_oborotov_kodifikator")
    fact["vendor_name"] = _series_or_default(fact, "kontragenti_naimenovanie")
    fact["contract_name"] = _series_or_default(fact, "dogovori_kontragentov_naimenovanie")
    fact["project_name"] = _series_or_default(fact, "proekti_naimenovanie")
    fact["department_name"] = _series_or_default(fact, "podrazdeleniya_naimenovanie")
    fact["organization_name"] = _series_or_default(fact, "organizacii_naimenovanie")
    fact["l1_category"] = _series_or_default(fact, "l1_category", "other_it")
    fact["l2_category"] = _series_or_default(fact, "l2_category", "unclassified")
    fact["l3_category"] = _series_or_default(fact, "l3_category", "review_required")
    fact["classification_confidence"] = _series_or_default(fact, "classification_confidence", "unclassified")

    ordered_columns = [
        "payment_id",
        "period_date",
        "year",
        "month",
        "quarter",
        "amount",
        "status_raw",
        "status_group",
        "article_name",
        "article_code",
        "vendor_name",
        "contract_name",
        "project_name",
        "department_name",
        "organization_name",
        "l1_category",
        "l2_category",
        "l3_category",
        "classification_confidence",
    ]
    return fact.loc[:, ordered_columns]


def _build_payment_ids(dataframe: pd.DataFrame) -> pd.Series:
    """Build a deterministic technical key for each payment row."""
    key_columns = [
        "period",
        "summa",
        "bit_stati_oborotov_naimenovanie",
        "kontragenti_naimenovanie",
        "dogovori_kontragentov_naimenovanie",
        "proekti_naimenovanie",
        "podrazdeleniya_naimenovanie",
        "organizacii_naimenovanie",
    ]

    def make_digest(row: pd.Series) -> str:
        payload = "|".join(_stringify(row.get(column, "")) for column in key_columns)
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    return dataframe.apply(make_digest, axis=1)


def _prefer_column(dataframe: pd.DataFrame, column: str, fallback: pd.Series) -> pd.Series:
    """Use an existing column when available, otherwise a fallback series."""
    if column in dataframe.columns:
        return pd.to_numeric(dataframe[column], errors="coerce")
    return pd.to_numeric(fallback, errors="coerce")


def _series_or_default(dataframe: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    """Return a string-typed series or a default-filled fallback."""
    if column in dataframe.columns:
        return dataframe[column].astype("string").fillna(default)
    return pd.Series([default] * len(dataframe), index=dataframe.index, dtype="string")


def _stringify(value: object) -> str:
    """Convert nullable values into stable key fragments."""
    if pd.isna(value):
        return ""
    return str(value).strip()

