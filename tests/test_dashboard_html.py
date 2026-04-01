"""Unit tests for interactive dashboard HTML generation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from it_spend_dashboard.dashboard.builder import build_dashboard


def _sample_payments_fact() -> pd.DataFrame:
    """Create a minimal payments fact dataset for HTML rendering tests."""
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
                "article_name": "licenses",
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
        ]
    )


def test_build_dashboard_renders_single_html_file(tmp_path: Path) -> None:
    """Render a single dashboard HTML file with inline assets and payload."""
    output_path = tmp_path / "dashboard.html"
    build_dashboard(_sample_payments_fact(), output_path=output_path)
    html = output_path.read_text(encoding="utf-8")
    detail_table_title = "\u0414\u0435\u0442\u0430\u043b\u044c\u043d\u0430\u044f \u0442\u0430\u0431\u043b\u0438\u0446\u0430"

    assert output_path.exists()
    assert "window.dashboardPayload" in html
    assert "plotly-2.35.2.min.js" in html
    assert detail_table_title in html
