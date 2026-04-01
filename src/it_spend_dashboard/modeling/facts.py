"""Fact table builders for dashboard-ready IT spend analytics."""

from __future__ import annotations

import pandas as pd

from it_spend_dashboard.modeling.grain import collapse_to_position_grain


def build_payments_fact(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Build the canonical payments fact table at one row per payment position."""
    fact = collapse_to_position_grain(dataframe)
    fact["payment_id"] = fact["payment_position_id"]
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
    fact["matched_rule_id"] = _series_or_default(fact, "matched_rule_id")
    fact["matched_keywords"] = _series_or_default(fact, "matched_keywords")
    fact["matched_vendor_pattern"] = _series_or_default(fact, "matched_vendor_pattern")
    fact["matched_article_pattern"] = _series_or_default(fact, "matched_article_pattern")
    fact["classification_reason_human"] = _series_or_default(fact, "classification_reason_human")

    ordered_columns = [
        "payment_id",
        "payment_document_id",
        "payment_position_id",
        "payment_source_line_id",
        "source_line_count",
        "source_line_unique_count",
        "has_source_duplicates",
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
        "matched_rule_id",
        "matched_keywords",
        "matched_vendor_pattern",
        "matched_article_pattern",
        "classification_reason_human",
    ]
    return fact.loc[:, ordered_columns]


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
