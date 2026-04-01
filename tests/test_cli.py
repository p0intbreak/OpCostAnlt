"""Unit tests for the end-to-end CLI entrypoint."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from it_spend_dashboard import cli


def test_profile_data_command_returns_success(tmp_path: Path) -> None:
    """Profile an input CSV and return a success exit code."""
    csv_path = tmp_path / "payments.csv"
    csv_path.write_text("quarter_period;report_type\n2025Q1;fact\n", encoding="utf-8")

    exit_code = cli.main(["profile-data", "--input", str(csv_path)])

    assert exit_code == 0


def test_missing_input_returns_controlled_error() -> None:
    """Return a controlled non-zero exit code on missing input."""
    exit_code = cli.main(["run-pipeline", "--input", "missing.csv"])
    assert exit_code == 2


def test_build_dashboard_command_uses_processed_fact(tmp_path: Path) -> None:
    """Build dashboard payload from a processed fact parquet file."""
    fact_path = tmp_path / "payments_fact.parquet"
    output_path = tmp_path / "dashboard_payload.json"
    pd.DataFrame(
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
                "period_date": "2026-01-31",
                "year": 2026,
                "month": 1,
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
    ).to_parquet(fact_path, index=False)

    exit_code = cli.main(["build-dashboard", "--input", str(fact_path), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()
