"""Consistency tests for the analytical modeling layer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from it_spend_dashboard.modeling.aggregations import build_aggregations
from it_spend_dashboard.modeling.dimensions import build_dimensions
from it_spend_dashboard.modeling.facts import build_payments_fact
from it_spend_dashboard.modeling.pipeline import run_modeling_pipeline


def _sample_classified_payments() -> pd.DataFrame:
    """Create a representative classified payments dataset for modeling tests."""
    return pd.DataFrame(
        [
            {
                "period": "2025-01-31",
                "year": 2025,
                "month": 1,
                "quarter": 1,
                "summa": 100.0,
                "registrator_status_name": "paid raw",
                "business_status": "paid",
                "bit_stati_oborotov_naimenovanie": "hosting",
                "bit_stati_oborotov_kodifikator": "A1",
                "kontragenti_naimenovanie": "vendor a",
                "dogovori_kontragentov_naimenovanie": "contract a",
                "proekti_naimenovanie": "erp",
                "podrazdeleniya_naimenovanie": "it ops",
                "organizacii_naimenovanie": "org 1",
                "l1_category": "infrastructure",
                "l2_category": "cloud_and_hosting",
                "l3_category": "managed_hosting",
                "classification_confidence": "high",
                "matched_rule_id": "infra_cloud_hosting",
                "matched_keywords": "hosting",
                "matched_vendor_pattern": "vendor a",
                "matched_article_pattern": "hosting",
                "classification_reason_human": "Тестовое объяснение 1",
            },
            {
                "period": "2025-02-28",
                "year": 2025,
                "month": 2,
                "quarter": 1,
                "summa": 200.0,
                "registrator_status_name": "approval raw",
                "business_status": "in_approval",
                "bit_stati_oborotov_naimenovanie": "microsoft 365",
                "bit_stati_oborotov_kodifikator": "A2",
                "kontragenti_naimenovanie": "vendor b",
                "dogovori_kontragentov_naimenovanie": "contract b",
                "proekti_naimenovanie": "crm",
                "podrazdeleniya_naimenovanie": "it support",
                "organizacii_naimenovanie": "org 1",
                "l1_category": "software_and_licenses",
                "l2_category": "productivity_and_collaboration",
                "l3_category": "office_suites",
                "classification_confidence": "medium",
                "matched_rule_id": "licenses_productivity",
                "matched_keywords": "microsoft 365",
                "matched_vendor_pattern": "",
                "matched_article_pattern": "microsoft 365",
                "classification_reason_human": "Тестовое объяснение 2",
            },
            {
                "period": "2026-01-31",
                "year": 2026,
                "month": 1,
                "quarter": 1,
                "summa": 300.0,
                "registrator_status_name": "rejected raw",
                "business_status": "rejected",
                "bit_stati_oborotov_naimenovanie": "misc expense",
                "bit_stati_oborotov_kodifikator": "A3",
                "kontragenti_naimenovanie": "vendor c",
                "dogovori_kontragentov_naimenovanie": "contract c",
                "proekti_naimenovanie": "security",
                "podrazdeleniya_naimenovanie": "security",
                "organizacii_naimenovanie": "org 2",
                "l1_category": "other_it",
                "l2_category": "unclassified",
                "l3_category": "review_required",
                "classification_confidence": "low",
                "matched_rule_id": "",
                "matched_keywords": "",
                "matched_vendor_pattern": "",
                "matched_article_pattern": "",
                "classification_reason_human": "Тестовое объяснение 3",
            },
        ]
    )


def test_build_payments_fact_creates_expected_grain_and_columns() -> None:
    """Build the canonical payments fact with one row per payment operation."""
    fact = build_payments_fact(_sample_classified_payments())

    assert len(fact) == 3
    assert fact["payment_id"].nunique() == 3
    assert list(fact.columns) == [
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
        "matched_rule_id",
        "matched_keywords",
        "matched_vendor_pattern",
        "matched_article_pattern",
        "classification_reason_human",
    ]


def test_aggregated_sums_reconcile_with_fact_amount() -> None:
    """Ensure core aggregate totals reconcile with the fact table total."""
    fact = build_payments_fact(_sample_classified_payments())
    aggregations = build_aggregations(fact)
    total_amount = fact["amount"].sum()

    assert aggregations["agg_status"]["total_amount"].sum() == pytest.approx(total_amount)
    assert aggregations["agg_categories"]["total_amount"].sum() == pytest.approx(total_amount)
    assert aggregations["agg_orgs"]["total_amount"].sum() == pytest.approx(total_amount)
    assert aggregations["agg_department"]["total_amount"].sum() == pytest.approx(total_amount)


def test_statuses_are_not_lost_in_aggregation() -> None:
    """Preserve all fact status groups in the status aggregate."""
    fact = build_payments_fact(_sample_classified_payments())
    agg_status = build_aggregations(fact)["agg_status"]

    assert set(fact["status_group"].dropna()) == set(agg_status["status_group"].dropna())


def test_categories_cover_expected_share_of_records() -> None:
    """Verify that category assignment covers the expected share of fact rows."""
    fact = build_payments_fact(_sample_classified_payments())
    covered_share = (fact["l1_category"].fillna("") != "other_it").mean()

    assert covered_share >= 2 / 3


def test_run_modeling_pipeline_persists_processed_parquet_files(tmp_path: Path) -> None:
    """Persist fact, dimensions, and aggregates into the processed layer."""
    fact = run_modeling_pipeline(_sample_classified_payments(), output_dir=tmp_path)

    expected_files = [
        "payments_fact.parquet",
        "dim_vendors.parquet",
        "dim_articles.parquet",
        "dim_orgs.parquet",
        "dim_projects.parquet",
        "agg_kpi_year_month.parquet",
        "agg_status.parquet",
        "agg_categories.parquet",
        "agg_vendors.parquet",
        "agg_orgs.parquet",
        "agg_department.parquet",
        "agg_year_compare_2025_2026.parquet",
    ]

    for filename in expected_files:
        assert (tmp_path / filename).exists()

    assert fact.attrs["dimension_tables"] == [
        "dim_articles",
        "dim_orgs",
        "dim_projects",
        "dim_vendors",
    ]
    assert fact.attrs["aggregation_tables"] == [
        "agg_categories",
        "agg_department",
        "agg_kpi_year_month",
        "agg_orgs",
        "agg_status",
        "agg_vendors",
        "agg_year_compare_2025_2026",
    ]


def test_dimension_builders_create_unique_members() -> None:
    """Create de-duplicated dimension members from the fact table."""
    fact = build_payments_fact(_sample_classified_payments())
    dimensions = build_dimensions(fact)

    assert len(dimensions["dim_vendors"]) == fact["vendor_name"].nunique(dropna=False)
    assert len(dimensions["dim_orgs"]) == fact["organization_name"].nunique(dropna=False)
