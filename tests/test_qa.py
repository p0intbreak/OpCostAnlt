"""Unit tests for the QA layer."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from it_spend_dashboard.qa.checks import (
    build_qa_report,
    check_amounts_parsed,
    check_classification_coverage,
    check_required_fields_not_catastrophically_null,
    check_status_mapping_coverage,
    check_year_bounds,
)


def _sample_fact() -> pd.DataFrame:
    """Create a representative fact table for QA tests."""
    return pd.DataFrame(
        [
            {
                "payment_id": "p1",
                "period_date": "2025-01-31",
                "year": 2025,
                "amount": 100.0,
                "status_raw": "paid raw",
                "status_group": "paid",
                "vendor_name": "vendor a",
                "organization_name": "org 1",
                "l1_category": "infrastructure",
                "classification_confidence": "high",
            },
            {
                "payment_id": "p2",
                "period_date": "2026-01-31",
                "year": 2026,
                "amount": 250.0,
                "status_raw": "approved raw",
                "status_group": "approved_not_paid",
                "vendor_name": "vendor b",
                "organization_name": "org 2",
                "l1_category": "software_and_licenses",
                "classification_confidence": "medium",
            },
        ]
    )


def test_required_fields_null_check_passes_for_valid_fact() -> None:
    """Pass when required fields are materially complete."""
    result = check_required_fields_not_catastrophically_null(_sample_fact())
    assert result.passed
    assert result.metric == 0


def test_amounts_parse_check_flags_invalid_values() -> None:
    """Flag non-numeric amount values."""
    dataframe = pd.DataFrame({"amount": [100.0, None, "bad"]})
    result = check_amounts_parsed(dataframe, min_parse_rate=0.8)
    assert not result.passed
    assert result.severity == "critical"


def test_year_bounds_flags_unexpected_years() -> None:
    """Warn when years outside 2025-2026 are present."""
    dataframe = _sample_fact().copy()
    dataframe.loc[1, "year"] = 2027
    result = check_year_bounds(dataframe)
    assert not result.passed
    assert result.details["unexpected_years"] == [2027]


def test_status_mapping_coverage_and_classification_report() -> None:
    """Measure status coverage and classification confidence distribution."""
    fact = _sample_fact()
    status_result = check_status_mapping_coverage(fact)
    classification_result = check_classification_coverage(fact)

    assert status_result.passed
    assert classification_result.passed
    assert "high" in classification_result.details["confidence_distribution"]


def test_build_qa_report_persists_json(tmp_path: Path) -> None:
    """Persist a QA report with known limitations and TODOs."""
    output_path = tmp_path / "qa_report.json"
    report = build_qa_report(_sample_fact(), output_path=output_path)

    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["summary"]["total_checks"] == 5
    assert payload["known_limitations"]
    assert payload["todo"]

