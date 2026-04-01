"""Schema validation for expected 1C ingestion datasets."""

from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict


class PaymentsSchema(BaseModel):
    """Reference schema for normalized 1C payment extracts."""

    model_config = ConfigDict(extra="allow")

    quarter_period: Any | None = None
    report_type: Any | None = None
    quarter_str: Any | None = None
    year_month_str: Any | None = None
    year_num: Any | None = None
    registrator_status_name: Any | None = None
    bit_stati_oborotov_naimenovanie: Any | None = None
    bit_stati_oborotov_kodifikator: Any | None = None
    summa: Any | None = None
    period: Any | None = None
    kontragenti_naimenovanie: Any | None = None
    dogovori_kontragentov_naimenovanie: Any | None = None
    proekti_naimenovanie: Any | None = None
    podrazdeleniya_naimenovanie: Any | None = None
    organizacii_naimenovanie: Any | None = None


REQUIRED_COLUMNS = list(PaymentsSchema.model_fields)


def validate_required_columns(dataframe: pd.DataFrame) -> None:
    """Validate that the dataset contains the required normalized columns."""
    missing = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
