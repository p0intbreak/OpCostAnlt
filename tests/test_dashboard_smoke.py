"""Smoke test for dashboard HTML generation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from it_spend_dashboard.dashboard.builder import build_dashboard


def test_dashboard_html_smoke_generation(tmp_path: Path) -> None:
    """Generate an HTML dashboard artifact without raising errors."""
    dataframe = pd.DataFrame(
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
            }
        ]
    )
    output_path = tmp_path / "dashboard.html"

    result = build_dashboard(dataframe, output_path=output_path)

    assert result.exists()
    assert result.name == "dashboard.html"

