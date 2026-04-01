"""Unit tests for the ingestion layer."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from it_spend_dashboard.ingestion.load_csv import detect_csv_separator, load_payments_csv
from it_spend_dashboard.ingestion.normalize_columns import normalize_columns
from it_spend_dashboard.ingestion.pipeline import run_ingestion_pipeline
from it_spend_dashboard.ingestion.schema import validate_required_columns

CSV_COLUMNS = [
    "quarter_period",
    "report_type",
    "quarter_str",
    "year_month_str",
    "year_num",
    "registrator_status_name",
    "bit_stati_oborotov_naimenovanie",
    "bit_stati_oborotov_kodifikator",
    "summa",
    "period",
    "kontragenti_naimenovanie",
    "dogovori_kontragentov_naimenovanie",
    "proekti_naimenovanie",
    "podrazdeleniya_naimenovanie",
    "organizacii_naimenovanie",
]


def test_detect_csv_separator_for_semicolon_file(tmp_path: Path) -> None:
    """Detect the semicolon delimiter in a 1C-style export."""
    csv_path = tmp_path / "payments.csv"
    csv_path.write_text("quarter_period;report_type\nQ1;fact\n", encoding="utf-8")
    assert detect_csv_separator(csv_path) == ";"


def test_load_payments_csv_logs_profile_and_reads_cp1251(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Read CSV with encoding fallback and emit profile logs."""
    csv_path = tmp_path / "payments.csv"
    csv_path.write_text(
        "quarter_period;report_type;summa\nQ1;fact;100\nQ2;;200\n",
        encoding="cp1251",
    )

    with caplog.at_level(logging.INFO):
        dataframe = load_payments_csv(csv_path)

    assert dataframe.shape == (2, 3)
    assert "Loaded CSV file" in caplog.text
    assert "CSV dtypes" in caplog.text
    assert "CSV null_counts" in caplog.text


def test_normalize_columns_preserves_mapping_and_originals() -> None:
    """Normalize columns to ASCII-safe aliases and preserve the original mapping."""
    amount_column = "\u0421\u0443\u043c\u043c\u0430"
    org_column = (
        "\u041e\u0440\u0433\u0430\u043d\u0438\u0437\u0430\u0446\u0438\u0438 "
        "(\u043d\u0430\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u043d\u0438\u0435)"
    )
    dataframe = pd.DataFrame(columns=[amount_column, org_column, "year num"])

    normalized, mapping = normalize_columns(dataframe)

    assert list(normalized.columns) == ["summa", "organizatsii_naimenovanie", "year_num"]
    assert mapping == {
        amount_column: "summa",
        org_column: "organizatsii_naimenovanie",
        "year num": "year_num",
    }
    assert normalized.attrs["column_mapping"] == mapping


def test_validate_required_columns_raises_on_missing_columns() -> None:
    """Fail validation when mandatory ingestion columns are absent."""
    dataframe = pd.DataFrame({"quarter_period": ["Q1"]})
    with pytest.raises(ValueError, match="Missing required columns"):
        validate_required_columns(dataframe)


def test_run_ingestion_pipeline_writes_parquet(tmp_path: Path) -> None:
    """Write normalized ingestion output to the interim parquet artifact."""
    csv_path = tmp_path / "payments.csv"
    output_path = tmp_path / "payments_clean.parquet"

    header = ";".join(CSV_COLUMNS)
    row = ";".join(
        [
            "2026Q1",
            "fact",
            "Q1 2026",
            "2026-01",
            "2026",
            "posted",
            "Hosting",
            "IT001",
            "1500.50",
            "2026-01-31",
            "Vendor A",
            "Master agreement",
            "Infra",
            "IT Department",
            "Main Org",
        ]
    )
    csv_path.write_text(f"{header}\n{row}\n", encoding="utf-8")

    dataframe = run_ingestion_pipeline(csv_path=csv_path, output_path=output_path)
    restored = pd.read_parquet(output_path)

    assert output_path.exists()
    assert dataframe.shape == (1, len(CSV_COLUMNS))
    assert list(restored.columns) == CSV_COLUMNS
    assert dataframe.attrs["original_columns"]["summa"] == "summa"
