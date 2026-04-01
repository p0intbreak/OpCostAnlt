"""Snapshot test for dashboard payload generation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from it_spend_dashboard.dashboard.payload_builder import build_dashboard_payload


def _sample_payments_fact() -> pd.DataFrame:
    """Create a deterministic payments fact for snapshot testing."""
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


def test_dashboard_payload_snapshot_matches_expected() -> None:
    """Match the generated payload against the checked-in snapshot."""
    payload = build_dashboard_payload(_sample_payments_fact(), insights=[])
    payload["metadata"]["generated_at"] = "SNAPSHOT"
    snapshot_path = Path("tests") / "snapshots" / "dashboard_payload_snapshot.json"
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload == expected
