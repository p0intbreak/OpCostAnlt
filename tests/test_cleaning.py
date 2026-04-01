"""Unit tests for the cleaning layer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from it_spend_dashboard.cleaning.amounts import normalize_amount_columns
from it_spend_dashboard.cleaning.dates import ensure_reporting_years_present, normalize_date_columns
from it_spend_dashboard.cleaning.entities import normalize_entity_columns
from it_spend_dashboard.cleaning.pipeline import clean_payments
from it_spend_dashboard.cleaning.statuses import normalize_statuses
from it_spend_dashboard.cleaning.text import clean_text_series, tokenize_text


def test_normalize_amount_columns_parses_locale_values() -> None:
    """Parse amount columns with spaces, commas, and missing values."""
    dataframe = pd.DataFrame(
        {
            "summa": ["1 234,56", " ", None],
            "summa_regl": ["10", "nan", "5,5"],
            "summa_upr": ["1\u00a0000,00", "2,25", ""],
            "summa_vzaimorascheti": ["3 333", "4.75", "<NA>"],
        }
    )

    normalized = normalize_amount_columns(dataframe)

    assert normalized["summa"].tolist()[0] == pytest.approx(1234.56)
    assert pd.isna(normalized["summa"].tolist()[1])
    assert normalized["summa_regl"].tolist()[2] == pytest.approx(5.5)
    assert normalized["summa_upr"].tolist()[0] == pytest.approx(1000.0)
    assert normalized["summa_vzaimorascheti"].tolist()[1] == pytest.approx(4.75)


def test_normalize_statuses_maps_to_business_statuses() -> None:
    """Normalize registrator statuses into business buckets."""
    paid_status = "\u041e\u043f\u043b\u0430\u0447\u0435\u043d \u043f\u043e\u043b\u043d\u043e\u0441\u0442\u044c\u044e"
    approved_status = "\u0423\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d"
    in_approval_status = "\u041d\u0430 \u0441\u043e\u0433\u043b\u0430\u0441\u043e\u0432\u0430\u043d\u0438\u0438"
    rejected_status = "\u041e\u0442\u043a\u043b\u043e\u043d\u0435\u043d"
    unknown_status = "\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e"
    dataframe = pd.DataFrame(
        {
            "registrator_status_name": [
                paid_status,
                approved_status,
                in_approval_status,
                rejected_status,
                unknown_status,
            ]
        }
    )

    normalized = normalize_statuses(dataframe, config_dir=Path("config"))

    assert normalized["business_status"].tolist() == [
        "paid",
        "approved_not_paid",
        "in_approval",
        "rejected",
        "other",
    ]


def test_normalize_date_columns_derives_reporting_fields() -> None:
    """Normalize source dates and derive year, month, quarter, and year_month."""
    dataframe = pd.DataFrame(
        {
            "period": ["2025-01-31", "2026-04-15"],
            "quarter_period": ["2025-03-31", "2026-06-30"],
            "bit_zayavka_na_rashodovanie_sredstv_data": ["31.01.2025", "15.04.2026"],
            "bit_platezhnaya_poziciya_data": ["2025-01-28", "2026-04-10"],
        }
    )

    normalized = normalize_date_columns(dataframe)

    assert str(normalized.loc[0, "period"].date()) == "2025-01-31"
    assert normalized["year"].tolist() == [2025, 2026]
    assert normalized["month"].tolist() == [1, 4]
    assert normalized["quarter"].tolist() == [1, 2]
    assert normalized["year_month"].tolist() == ["2025-01", "2026-04"]


def test_ensure_reporting_years_present_raises_when_year_missing() -> None:
    """Fail when one of the required reporting years is not present."""
    dataframe = pd.DataFrame({"year": pd.Series([2025], dtype="Int64")})

    with pytest.raises(ValueError, match="Missing required reporting years"):
        ensure_reporting_years_present(dataframe, required_years=(2025, 2026))


def test_text_and_entities_normalization_cleans_values() -> None:
    """Normalize text fields and key entities to a stable comparable form."""
    spend_name = "  \u041e\u0431\u043b\u0430\u0447\u043d\u0430\u044f  \u0418\u043d\u0444\u0440\u0430\u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0430  "
    vendor_name = "  \u041e\u041e\u041e   \u0420\u043e\u043c\u0430\u0448\u043a\u0430 "
    contract_name = "  \u0414\u043e\u0433\u043e\u0432\u043e\u0440   1 "
    org_name = "  \u041a\u043e\u043c\u043f\u0430\u043d\u0438\u044f   \u0410 "
    dataframe = pd.DataFrame(
        {
            "bit_stati_oborotov_naimenovanie": [spend_name],
            "kontragenti_naimenovanie": [vendor_name],
            "dogovori_kontragentov_naimenovanie": [contract_name],
            "organizacii_naimenovanie": [org_name],
            "podrazdeleniya_naimenovanie": [" IT   Department "],
            "proekti_naimenovanie": ["  Project   X "],
        }
    )

    texts = clean_text_series(dataframe["bit_stati_oborotov_naimenovanie"])
    entities = normalize_entity_columns(dataframe)

    assert texts.tolist() == ["\u043e\u0431\u043b\u0430\u0447\u043d\u0430\u044f \u0438\u043d\u0444\u0440\u0430\u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0430"]
    assert tokenize_text("Cloud, Infra 2026!") == ["cloud", "infra", "2026"]
    assert entities["kontragenti_naimenovanie"].tolist() == ["\u043e\u043e\u043e \u0440\u043e\u043c\u0430\u0448\u043a\u0430"]
    assert entities["organizacii_naimenovanie"].tolist() == ["\u043a\u043e\u043c\u043f\u0430\u043d\u0438\u044f \u0430"]


def test_clean_payments_runs_full_pipeline() -> None:
    """Run the composed cleaning pipeline over a representative dataset."""
    dataframe = pd.DataFrame(
        {
            "summa": ["1 500,50", "250,00"],
            "registrator_status_name": [
                "\u041e\u043f\u043b\u0430\u0447\u0435\u043d",
                "\u0423\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d",
            ],
            "period": ["2025-12-31", "2026-01-31"],
            "quarter_period": ["2025-12-31", "2026-03-31"],
            "bit_zayavka_na_rashodovanie_sredstv_data": ["2025-12-01", "2026-01-15"],
            "bit_platezhnaya_poziciya_data": ["2025-12-05", "2026-01-20"],
            "bit_stati_oborotov_naimenovanie": ["  SaaS ", "  Hosting  "],
            "kontragenti_naimenovanie": [" Vendor   A ", " Vendor B "],
            "dogovori_kontragentov_naimenovanie": [" Contract 1 ", " Contract 2 "],
            "organizacii_naimenovanie": [" Org A ", " Org B "],
            "podrazdeleniya_naimenovanie": [" IT Ops ", " Finance IT "],
            "proekti_naimenovanie": [" ERP ", " CRM "],
        }
    )

    cleaned = clean_payments(dataframe, config_dir=Path("config"))

    assert cleaned["summa"].tolist() == [pytest.approx(1500.5), pytest.approx(250.0)]
    assert cleaned["business_status"].tolist() == ["paid", "approved_not_paid"]
    assert cleaned["year_month"].tolist() == ["2025-12", "2026-01"]
    assert cleaned["kontragenti_naimenovanie"].tolist() == ["vendor a", "vendor b"]
