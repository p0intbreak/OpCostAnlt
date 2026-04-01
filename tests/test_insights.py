"""Unit tests for automatic dashboard insights."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from it_spend_dashboard.insights.generators import (
    anomaly_candidates,
    large_unpaid_items,
    status_bottlenecks,
    top_spend_categories,
    uncategorized_share,
    vendor_concentration,
    yoy_growth_categories,
)
from it_spend_dashboard.insights.narratives import build_management_narratives
from it_spend_dashboard.insights.pipeline import run_insights_pipeline


def _sample_payments_fact() -> pd.DataFrame:
    """Create a representative payments fact dataset for insight tests."""
    return pd.DataFrame(
        [
            {
                "payment_id": "p1",
                "period_date": "2025-01-31",
                "year": 2025,
                "month": 1,
                "quarter": 1,
                "amount": 100.0,
                "status_group": "paid",
                "vendor_name": "vendor a",
                "l1_category": "infrastructure",
                "l2_category": "cloud_and_hosting",
                "l3_category": "managed_hosting",
                "classification_confidence": "high",
            },
            {
                "payment_id": "p2",
                "period_date": "2025-02-28",
                "year": 2025,
                "month": 2,
                "quarter": 1,
                "amount": 120.0,
                "status_group": "approved_not_paid",
                "vendor_name": "vendor a",
                "l1_category": "infrastructure",
                "l2_category": "cloud_and_hosting",
                "l3_category": "managed_hosting",
                "classification_confidence": "medium",
            },
            {
                "payment_id": "p3",
                "period_date": "2026-01-31",
                "year": 2026,
                "month": 1,
                "quarter": 1,
                "amount": 400.0,
                "status_group": "approved_not_paid",
                "vendor_name": "vendor a",
                "l1_category": "infrastructure",
                "l2_category": "cloud_and_hosting",
                "l3_category": "managed_hosting",
                "classification_confidence": "high",
            },
            {
                "payment_id": "p4",
                "period_date": "2026-02-28",
                "year": 2026,
                "month": 2,
                "quarter": 1,
                "amount": 220.0,
                "status_group": "in_approval",
                "vendor_name": "vendor b",
                "l1_category": "software_and_licenses",
                "l2_category": "productivity_and_collaboration",
                "l3_category": "office_suites",
                "classification_confidence": "medium",
            },
            {
                "payment_id": "p5",
                "period_date": "2026-03-31",
                "year": 2026,
                "month": 3,
                "quarter": 1,
                "amount": 900.0,
                "status_group": "paid",
                "vendor_name": "vendor c",
                "l1_category": "other_it",
                "l2_category": "unclassified",
                "l3_category": "review_required",
                "classification_confidence": "unclassified",
            },
            {
                "payment_id": "p6",
                "period_date": "2026-03-31",
                "year": 2026,
                "month": 3,
                "quarter": 1,
                "amount": 130.0,
                "status_group": "paid",
                "vendor_name": "vendor d",
                "l1_category": "infrastructure",
                "l2_category": "cloud_and_hosting",
                "l3_category": "managed_hosting",
                "classification_confidence": "high",
            },
            {
                "payment_id": "p7",
                "period_date": "2026-04-30",
                "year": 2026,
                "month": 4,
                "quarter": 2,
                "amount": 140.0,
                "status_group": "paid",
                "vendor_name": "vendor e",
                "l1_category": "infrastructure",
                "l2_category": "cloud_and_hosting",
                "l3_category": "managed_hosting",
                "classification_confidence": "high",
            },
            {
                "payment_id": "p8",
                "period_date": "2026-05-31",
                "year": 2026,
                "month": 5,
                "quarter": 2,
                "amount": 150.0,
                "status_group": "paid",
                "vendor_name": "vendor f",
                "l1_category": "infrastructure",
                "l2_category": "cloud_and_hosting",
                "l3_category": "managed_hosting",
                "classification_confidence": "high",
            },
        ]
    )


def test_generators_return_required_fields() -> None:
    """Return fully shaped insight objects for the UI."""
    fact = _sample_payments_fact()
    insight = top_spend_categories(fact)

    assert set(insight) == {"title", "metric", "explanation", "severity", "supporting_filters"}
    assert insight["severity"] in {"info", "warning", "critical"}


def test_yoy_growth_and_status_bottlenecks_are_detected() -> None:
    """Detect year-over-year growth and unpaid bottlenecks."""
    fact = _sample_payments_fact()

    yoy = yoy_growth_categories(fact)
    bottleneck = status_bottlenecks(fact)

    assert yoy["title"] == "Рост расходов год к году"
    assert yoy["severity"] in {"warning", "critical"}
    assert bottleneck["supporting_filters"]["status_group"] in {"approved_not_paid", "in_approval"}


def test_vendor_unpaid_uncategorized_and_anomaly_insights() -> None:
    """Produce supplier, unpaid, uncategorized, and anomaly insights."""
    fact = _sample_payments_fact()

    concentration = vendor_concentration(fact)
    unpaid = large_unpaid_items(fact)
    uncategorized = uncategorized_share(fact)
    anomalies = anomaly_candidates(fact)

    assert concentration["title"] == "Концентрация на поставщиках"
    assert unpaid["title"] == "Крупные неоплаченные позиции"
    assert uncategorized["severity"] in {"warning", "critical"}
    assert anomalies["title"] == "Потенциальные аномалии"


def test_build_management_narratives_returns_top_five_insights() -> None:
    """Return the top five ranked insights for the dashboard UI."""
    narratives = build_management_narratives(_sample_payments_fact(), limit=5)

    assert len(narratives) == 5
    assert all("title" in item for item in narratives)


def test_run_insights_pipeline_persists_json_export(tmp_path: Path) -> None:
    """Persist management insights into the export layer for the UI."""
    insights = run_insights_pipeline(_sample_payments_fact(), export_dir=tmp_path)
    export_path = tmp_path / "management_insights.json"

    assert export_path.exists()
    assert len(insights) == 5
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert len(payload) == 5
