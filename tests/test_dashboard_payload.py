"""Unit tests for dashboard payload generation and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from it_spend_dashboard.dashboard.payload_builder import (
    build_dashboard_payload,
    save_dashboard_payload,
    validate_dashboard_payload,
)


def _sample_payments_fact() -> pd.DataFrame:
    """Create a representative payments fact dataset for dashboard payload tests."""
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
                "article_name": "hosting",
                "article_code": "A1",
                "vendor_name": "vendor a",
                "contract_name": "contract a",
                "project_name": "erp",
                "department_name": "it ops",
                "organization_name": "org 1",
                "l1_category": "infrastructure",
                "l2_category": "cloud_and_hosting",
                "l3_category": "managed_hosting",
                "classification_confidence": "high",
            },
            {
                "payment_id": "p2",
                "period_date": "2026-02-28",
                "year": 2026,
                "month": 2,
                "quarter": 1,
                "amount": 200.0,
                "status_group": "approved_not_paid",
                "article_name": "microsoft 365",
                "article_code": "A2",
                "vendor_name": "vendor b",
                "contract_name": "contract b",
                "project_name": "crm",
                "department_name": "it support",
                "organization_name": "org 2",
                "l1_category": "software_and_licenses",
                "l2_category": "productivity_and_collaboration",
                "l3_category": "office_suites",
                "classification_confidence": "medium",
            },
            {
                "payment_id": "p3",
                "period_date": "2026-03-31",
                "year": 2026,
                "month": 3,
                "quarter": 1,
                "amount": 300.0,
                "status_group": "in_approval",
                "article_name": "misc",
                "article_code": "A3",
                "vendor_name": "vendor b",
                "contract_name": "contract c",
                "project_name": "infra",
                "department_name": "security",
                "organization_name": "org 2",
                "l1_category": "other_it",
                "l2_category": "unclassified",
                "l3_category": "review_required",
                "classification_confidence": "low",
            },
        ]
    )


def test_build_dashboard_payload_contains_required_sections() -> None:
    """Build a payload with all required top-level sections."""
    payload = build_dashboard_payload(_sample_payments_fact())
    validate_dashboard_payload(payload)

    assert set(payload) == {
        "metadata",
        "filters",
        "kpis",
        "yearly_comparison",
        "monthly_trends",
        "categories_tree",
        "status_breakdown",
        "vendors",
        "organizations",
        "insights",
        "detail_rows",
        "detail_row_index",
    }


def test_detail_row_index_supports_frontend_only_drilldown() -> None:
    """Precompute row slices so the frontend can drill down without a backend."""
    payload = build_dashboard_payload(_sample_payments_fact())

    vendor_key = "vendor:vendor_b"
    year_key = "year:2026"
    category_key = "l1:software_and_licenses"

    assert vendor_key in payload["detail_row_index"]
    assert year_key in payload["detail_row_index"]
    assert category_key in payload["detail_row_index"]
    assert set(payload["detail_row_index"][vendor_key]) == {"p2", "p3"}


def test_payload_uses_id_friendly_fields_and_russian_labels() -> None:
    """Expose id-friendly values and Russian UI labels for the frontend."""
    payload = build_dashboard_payload(_sample_payments_fact())

    assert payload["filters"]["statuses"][0]["label"]
    assert payload["detail_rows"][0]["vendor_id"] == "vendor_a"
    assert payload["detail_rows"][0]["organization_id"] == "org_1"
    assert payload["status_breakdown"][0]["status_label"]


def test_save_dashboard_payload_writes_json_file(tmp_path: Path) -> None:
    """Persist the dashboard payload as JSON."""
    output_path = tmp_path / "dashboard_payload.json"
    save_dashboard_payload(_sample_payments_fact(), output_path=output_path)

    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["detail_rows_count"] == 3
