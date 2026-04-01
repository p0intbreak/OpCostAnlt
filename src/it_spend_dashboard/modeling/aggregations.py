"""Aggregate builders for dashboard KPIs and drill-down views."""

from __future__ import annotations

import pandas as pd


def build_aggregations(payments_fact: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build all dashboard-oriented aggregate tables."""
    return {
        "agg_kpi_year_month": build_agg_kpi_year_month(payments_fact),
        "agg_status": build_agg_status(payments_fact),
        "agg_categories": build_agg_categories(payments_fact),
        "agg_vendors": build_agg_vendors(payments_fact),
        "agg_orgs": build_agg_orgs(payments_fact),
        "agg_department": build_agg_department(payments_fact),
        "agg_year_compare_2025_2026": build_agg_year_compare_2025_2026(payments_fact),
    }


def build_agg_kpi_year_month(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Aggregate monthly KPI metrics."""
    grouped = (
        payments_fact.groupby(["year", "month"], dropna=False, as_index=False)
        .agg(
            total_amount=("amount", "sum"),
            payments_count=("payment_id", "nunique"),
        )
        .sort_values(["year", "month"])
        .reset_index(drop=True)
    )
    grouped["year_month"] = grouped["year"].astype("string") + "-" + grouped["month"].astype("string").str.zfill(2)
    return grouped.loc[:, ["year", "month", "year_month", "total_amount", "payments_count"]]


def build_agg_status(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Aggregate metrics by status group."""
    return _group_amount_and_count(payments_fact, ["status_group"])


def build_agg_categories(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Aggregate metrics by L1/L2/L3 category hierarchy."""
    return _group_amount_and_count(payments_fact, ["l1_category", "l2_category", "l3_category"])


def build_agg_vendors(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Aggregate metrics by vendor."""
    return _group_amount_and_count(payments_fact, ["vendor_name"])


def build_agg_orgs(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Aggregate metrics by organization."""
    return _group_amount_and_count(payments_fact, ["organization_name"])


def build_agg_department(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Aggregate metrics by department."""
    return _group_amount_and_count(payments_fact, ["department_name"])


def build_agg_year_compare_2025_2026(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Compare yearly totals and payment counts for 2025 and 2026."""
    filtered = payments_fact[payments_fact["year"].isin([2025, 2026])].copy()
    yearly = (
        filtered.groupby("year", dropna=False, as_index=False)
        .agg(
            total_amount=("amount", "sum"),
            payments_count=("payment_id", "nunique"),
        )
        .sort_values("year")
        .reset_index(drop=True)
    )
    return yearly


def _group_amount_and_count(payments_fact: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    """Group fact data by selected dimensions and compute standard metrics."""
    return (
        payments_fact.groupby(dimensions, dropna=False, as_index=False)
        .agg(
            total_amount=("amount", "sum"),
            payments_count=("payment_id", "nunique"),
        )
        .sort_values(dimensions)
        .reset_index(drop=True)
    )

