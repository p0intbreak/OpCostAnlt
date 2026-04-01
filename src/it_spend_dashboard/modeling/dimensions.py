"""Dimension table builders for dashboard drill-downs."""

from __future__ import annotations

import pandas as pd


def build_dimensions(payments_fact: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build all dimension tables from the canonical payments fact."""
    return {
        "dim_vendors": build_dim_vendors(payments_fact),
        "dim_articles": build_dim_articles(payments_fact),
        "dim_orgs": build_dim_orgs(payments_fact),
        "dim_projects": build_dim_projects(payments_fact),
    }


def build_dim_vendors(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Build the vendor dimension."""
    return _build_unique_dimension(
        payments_fact,
        source_column="vendor_name",
        key_name="vendor_id",
        value_name="vendor_name",
    )


def build_dim_articles(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Build the article dimension with article code and article name."""
    columns = ["article_code", "article_name"]
    dimension = payments_fact.loc[:, columns].drop_duplicates().reset_index(drop=True)
    dimension.insert(0, "article_id", range(1, len(dimension) + 1))
    return dimension


def build_dim_orgs(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Build the organization dimension."""
    return _build_unique_dimension(
        payments_fact,
        source_column="organization_name",
        key_name="organization_id",
        value_name="organization_name",
    )


def build_dim_projects(payments_fact: pd.DataFrame) -> pd.DataFrame:
    """Build the project dimension."""
    return _build_unique_dimension(
        payments_fact,
        source_column="project_name",
        key_name="project_id",
        value_name="project_name",
    )


def _build_unique_dimension(
    payments_fact: pd.DataFrame,
    *,
    source_column: str,
    key_name: str,
    value_name: str,
) -> pd.DataFrame:
    """Build a one-column unique dimension with a surrogate integer key."""
    dimension = (
        payments_fact.loc[:, [source_column]]
        .rename(columns={source_column: value_name})
        .drop_duplicates()
        .reset_index(drop=True)
    )
    dimension.insert(0, key_name, range(1, len(dimension) + 1))
    return dimension

