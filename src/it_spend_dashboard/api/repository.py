"""DuckDB-backed repository for dashboard summary, detail rows, and audit modal data."""

from __future__ import annotations

import csv
import io
from functools import cached_property
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from it_spend_dashboard.dashboard.payload_builder import _slugify, build_dashboard_payload
from it_spend_dashboard.modeling.facts import build_payments_fact
from it_spend_dashboard.modeling.grain import add_grain_columns

DETAIL_SORT_MAP = {
    "period_date": "period_date",
    "vendor_label": "vendor_name",
    "organization_label": "organization_name",
    "expense_subject": "expense_subject",
    "project_name": "project_name",
    "classification_confidence": "classification_confidence",
    "classification_reason_human": "classification_reason_human",
    "status_group": "status_group",
    "amount": "amount",
}

AMOUNT_FIELDS = ["summa", "summa_regl", "summa_upr", "summa_vzaimorascheti"]
DATE_FIELDS = [
    "period",
    "quarter_period",
    "bit_zayavka_na_rashodovanie_sredstv_data",
    "bit_platezhnaya_poziciya_data",
]
TEXT_FIELDS = [
    "bit_stati_oborotov_naimenovanie",
    "naznachenie_platezha",
    "kontragenti_naimenovanie",
    "dogovori_kontragentov_naimenovanie",
]
ENTITY_FIELDS = [
    "organizacii_naimenovanie",
    "podrazdeleniya_naimenovanie",
    "proekti_naimenovanie",
    "kontragenti_naimenovanie",
]


class DashboardRepository:
    """Serve dashboard data from processed/interim parquet artifacts."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    @cached_property
    def fact_path(self) -> Path:
        return self.project_root / "data" / "processed" / "payments_fact.parquet"

    @cached_property
    def raw_path(self) -> Path:
        return self.project_root / "data" / "interim" / "payments_ingested.parquet"

    @cached_property
    def classified_path(self) -> Path:
        return self.project_root / "data" / "interim" / "payments_classified.parquet"

    @cached_property
    def cleaned_path(self) -> Path:
        return self.project_root / "data" / "interim" / "payments_clean.parquet"

    @cached_property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(database=":memory:")

    @cached_property
    def fact_df(self) -> pd.DataFrame:
        dataframe = pd.read_parquet(self.fact_path).copy()
        required_columns = {"payment_position_id", "payment_document_id", "source_line_count", "has_source_duplicates"}
        if not required_columns.issubset(set(dataframe.columns)) and self.classified_path.exists():
            dataframe = build_payments_fact(pd.read_parquet(self.classified_path)).copy()
        dataframe.insert(0, "detail_row_number", range(len(dataframe)))
        dataframe["expense_subject"] = dataframe.apply(_build_expense_subject, axis=1)
        if "year_month" not in dataframe.columns:
            dataframe["year_month"] = dataframe.apply(
                lambda row: f"{int(row['year']):04d}-{int(row['month']):02d}"
                if pd.notna(row.get("year")) and pd.notna(row.get("month"))
                else "",
                axis=1,
            )
        dataframe["vendor_id"] = dataframe["vendor_name"].astype("string").fillna("").map(_slugify)
        dataframe["organization_id"] = dataframe["organization_name"].astype("string").fillna("").map(_slugify)
        dataframe["l1_category_id"] = dataframe["l1_category"].astype("string").fillna("").map(_slugify)
        dataframe["l2_category_id"] = dataframe["l2_category"].astype("string").fillna("").map(_slugify)
        dataframe["l3_category_id"] = dataframe["l3_category"].astype("string").fillna("").map(_slugify)
        return dataframe

    @cached_property
    def raw_df(self) -> pd.DataFrame:
        return add_grain_columns(pd.read_parquet(self.raw_path).copy())

    @cached_property
    def pipeline_df(self) -> pd.DataFrame:
        source = self.classified_path if self.classified_path.exists() else self.cleaned_path
        return add_grain_columns(pd.read_parquet(source).copy())

    def get_summary_payload(self) -> dict[str, Any]:
        """Build a compact summary payload for first paint."""
        return build_dashboard_payload(self.fact_df.drop(columns=["detail_row_number"]))

    def get_vendor_drilldown(
        self,
        *,
        year: str = "",
        status_group: str = "",
        l1_category_id: str = "",
        l2_category_id: str = "",
        l3_category_id: str = "",
        organization_id: str = "",
        classification_confidence: str = "",
        selected_vendor_id: str = "",
        selected_month: str = "",
    ) -> dict[str, Any]:
        """Return linked annual, monthly, and monthly-component views for vendors."""
        scoped = self._filter_fact_dataframe(
            year=year,
            month="",
            status_group=status_group,
            l1_category_id=l1_category_id,
            l2_category_id=l2_category_id,
            l3_category_id=l3_category_id,
            vendor_id="",
            organization_id=organization_id,
            classification_confidence=classification_confidence,
            search="",
        )

        if scoped.empty:
            return {
                "selected_year": "",
                "selected_vendor_id": "",
                "selected_vendor_label": "",
                "selected_month": "",
                "top_vendors": [],
                "vendor_monthly": [],
                "month_components": [],
            }

        available_years = sorted(
            {int(value) for value in scoped["year"].dropna().tolist()},
        )
        resolved_year = int(year) if year else (max(available_years) if available_years else 0)
        scoped = scoped[scoped["year"].fillna(0).astype(int) == resolved_year].copy()
        if scoped.empty:
            return {
                "selected_year": str(resolved_year) if resolved_year else "",
                "selected_vendor_id": "",
                "selected_vendor_label": "",
                "selected_month": "",
                "top_vendors": [],
                "vendor_monthly": [],
                "month_components": [],
            }

        annual = (
            scoped.groupby(["vendor_id", "vendor_name"], dropna=False, as_index=False)
            .agg(total_amount=("amount", "sum"))
            .sort_values("total_amount", ascending=False)
            .head(10)
        )
        top_vendors = [
            {
                "id": _format_scalar(row.get("vendor_id")),
                "label": _format_scalar(row.get("vendor_name")),
                "total_amount": float(row.get("total_amount", 0.0) or 0.0),
            }
            for _, row in annual.iterrows()
            if _format_scalar(row.get("vendor_id"))
        ]

        available_vendor_ids = [item["id"] for item in top_vendors]
        resolved_vendor_id = selected_vendor_id if selected_vendor_id in available_vendor_ids else (available_vendor_ids[0] if available_vendor_ids else "")
        vendor_label = next((item["label"] for item in top_vendors if item["id"] == resolved_vendor_id), "")

        vendor_scoped = scoped[scoped["vendor_id"] == resolved_vendor_id].copy() if resolved_vendor_id else scoped.iloc[0:0].copy()
        monthly = (
            vendor_scoped.groupby(["month", "year_month"], dropna=False, as_index=False)
            .agg(total_amount=("amount", "sum"))
            .sort_values(["month", "year_month"], ascending=[True, True])
        )
        vendor_monthly = [
            {
                "month": int(row["month"]),
                "year_month": _format_scalar(row.get("year_month")),
                "total_amount": float(row.get("total_amount", 0.0) or 0.0),
            }
            for _, row in monthly.iterrows()
            if pd.notna(row.get("month"))
        ]

        available_months = [str(item["month"]) for item in vendor_monthly]
        resolved_month = selected_month if selected_month in available_months else (available_months[-1] if available_months else "")
        month_scoped = vendor_scoped[vendor_scoped["month"].fillna(0).astype(int) == int(resolved_month)] if resolved_month else vendor_scoped.iloc[0:0].copy()
        month_scoped = month_scoped.copy()
        month_scoped["component_label"] = month_scoped["expense_subject"].astype("string").fillna("").replace("", pd.NA)
        month_scoped["component_label"] = month_scoped["component_label"].fillna(month_scoped["article_name"].astype("string").fillna(""))
        components = (
            month_scoped.groupby("component_label", dropna=False, as_index=False)
            .agg(total_amount=("amount", "sum"))
            .sort_values("total_amount", ascending=False)
            .head(12)
        )
        month_components = [
            {
                "label": _format_scalar(row.get("component_label")) or "Без названия",
                "total_amount": float(row.get("total_amount", 0.0) or 0.0),
            }
            for _, row in components.iterrows()
        ]
        return {
            "selected_year": str(resolved_year) if resolved_year else "",
            "selected_vendor_id": resolved_vendor_id,
            "selected_vendor_label": vendor_label,
            "selected_month": resolved_month,
            "top_vendors": top_vendors,
            "vendor_monthly": vendor_monthly,
            "month_components": month_components,
        }

    def list_details(
        self,
        *,
        year: str = "",
        month: str = "",
        status_group: str = "",
        l1_category_id: str = "",
        l2_category_id: str = "",
        l3_category_id: str = "",
        vendor_id: str = "",
        organization_id: str = "",
        classification_confidence: str = "",
        search: str = "",
        sort_key: str = "amount",
        sort_direction: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        """Return paginated detail rows for the current filter state."""
        dataframe = self._filter_fact_dataframe(
            year=year,
            month=month,
            status_group=status_group,
            l1_category_id=l1_category_id,
            l2_category_id=l2_category_id,
            l3_category_id=l3_category_id,
            vendor_id=vendor_id,
            organization_id=organization_id,
            classification_confidence=classification_confidence,
            search=search,
        )

        sort_column = DETAIL_SORT_MAP.get(sort_key, "amount")
        ascending = sort_direction == "asc"
        dataframe = dataframe.sort_values(sort_column, ascending=ascending, kind="mergesort")
        total_rows = len(dataframe)
        start = max(page - 1, 0) * max(page_size, 1)
        paged = dataframe.iloc[start : start + max(page_size, 1)].copy()
        rows = [self._serialize_detail_row(row) for _, row in paged.iterrows()]
        return {
            "rows": rows,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": max((total_rows + page_size - 1) // max(page_size, 1), 1),
        }

    def _filter_fact_dataframe(
        self,
        *,
        year: str = "",
        month: str = "",
        status_group: str = "",
        l1_category_id: str = "",
        l2_category_id: str = "",
        l3_category_id: str = "",
        vendor_id: str = "",
        organization_id: str = "",
        classification_confidence: str = "",
        search: str = "",
    ) -> pd.DataFrame:
        """Apply the common dashboard filters to facts."""
        dataframe = self.fact_df.copy()
        if year:
            dataframe = dataframe[dataframe["year"].astype("string") == str(year)]
        if month:
            dataframe = dataframe[dataframe["month"].astype("string") == str(month)]
        if status_group:
            dataframe = dataframe[dataframe["status_group"].astype("string") == status_group]
        if l1_category_id:
            dataframe = dataframe[dataframe["l1_category_id"] == l1_category_id]
        if l2_category_id:
            dataframe = dataframe[dataframe["l2_category_id"] == l2_category_id]
        if l3_category_id:
            dataframe = dataframe[dataframe["l3_category_id"] == l3_category_id]
        if vendor_id:
            dataframe = dataframe[dataframe["vendor_id"] == vendor_id]
        if organization_id:
            dataframe = dataframe[dataframe["organization_id"] == organization_id]
        if classification_confidence:
            dataframe = dataframe[dataframe["classification_confidence"].astype("string") == classification_confidence]
        if search:
            search_value = str(search).strip().lower()
            haystack = (
                dataframe[
                    [
                        "vendor_name",
                        "organization_name",
                        "expense_subject",
                        "article_name",
                        "contract_name",
                        "project_name",
                        "department_name",
                        "classification_reason_human",
                    ]
                ]
                .astype("string")
                .fillna("")
                .agg(" ".join, axis=1)
                .str.lower()
            )
            dataframe = dataframe[haystack.str.contains(search_value, na=False)]
        return dataframe

    def get_row_details(self, detail_row_id: str) -> dict[str, Any]:
        """Return raw row attributes, pipeline attributes, and transformation log for a row."""
        row_number = _parse_detail_row_id(detail_row_id)
        if row_number < 0 or row_number >= len(self.fact_df):
            raise KeyError(detail_row_id)

        fact_row = self.fact_df.iloc[row_number]
        position_id = str(fact_row.get("payment_position_id", ""))
        raw_rows = self.raw_df[self.raw_df["payment_position_id"] == position_id].copy()
        pipeline_rows = self.pipeline_df[self.pipeline_df["payment_position_id"] == position_id].copy()
        representative_raw_row = raw_rows.iloc[0] if not raw_rows.empty else pd.Series(dtype="object")
        representative_pipeline_row = pipeline_rows.iloc[0] if not pipeline_rows.empty else pd.Series(dtype="object")
        return {
            "detail_row_id": detail_row_id,
            "summary": {
                "period_date": _format_scalar(fact_row.get("period_date")),
                "vendor_name": _format_scalar(fact_row.get("vendor_name")),
                "organization_name": _format_scalar(fact_row.get("organization_name")),
                "amount": float(fact_row.get("amount", 0.0) or 0.0),
                "status_group": _format_scalar(fact_row.get("status_group")),
                "source_line_count": int(fact_row.get("source_line_count", 1) or 1),
            },
            "raw_attributes": _serialize_non_empty(representative_raw_row.to_dict()) if not representative_raw_row.empty else {},
            "pipeline_attributes": _serialize_non_empty(
                {
                    key: representative_pipeline_row.get(key)
                    for key in [
                        "business_status",
                        "year",
                        "month",
                        "quarter",
                        "year_month",
                        "l1_category",
                        "l2_category",
                        "l3_category",
                        "classification_confidence",
                        "classification_confidence_score",
                        "matched_rule_id",
                        "matched_keywords",
                        "matched_vendor_pattern",
                        "matched_article_pattern",
                        "classification_reason_human",
                    ]
                }
            ),
            "transformations": _build_transformation_log(representative_raw_row, representative_pipeline_row)
            if not representative_raw_row.empty and not representative_pipeline_row.empty
            else [],
            "raw_lines": [_serialize_non_empty(record) for record in raw_rows.to_dict(orient="records")],
            "pipeline_lines": [_serialize_non_empty(record) for record in pipeline_rows.to_dict(orient="records")],
        }

    def export_details_csv(self, **filters: Any) -> str:
        """Export the current detail selection to CSV."""
        normalized_filters = dict(filters)
        normalized_filters.pop("page", None)
        normalized_filters.pop("page_size", None)
        listing = self.list_details(page=1, page_size=1_000_000, **normalized_filters)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        columns = [
            "period_date",
            "vendor_label",
            "organization_label",
            "expense_subject",
            "project_name",
            "classification_confidence",
            "classification_reason_human",
            "status_group",
            "amount",
        ]
        writer.writerow(columns)
        for row in listing["rows"]:
            writer.writerow([row.get(column, "") for column in columns])
        return buffer.getvalue()

    def _serialize_detail_row(self, row: pd.Series) -> dict[str, Any]:
        return {
            "detail_row_id": f"row_{int(row['detail_row_number'])}",
            "payment_id": str(row["payment_id"]),
            "payment_document_id": _format_scalar(row.get("payment_document_id")),
            "payment_position_id": _format_scalar(row.get("payment_position_id")),
            "period_date": _format_scalar(row.get("period_date")),
            "year": _nullable_int(row.get("year")),
            "month": _nullable_int(row.get("month")),
            "quarter": _nullable_int(row.get("quarter")),
            "amount": float(row.get("amount", 0.0) or 0.0),
            "source_line_count": int(row.get("source_line_count", 1) or 1),
            "source_line_unique_count": int(row.get("source_line_unique_count", 1) or 1),
            "has_source_duplicates": bool(row.get("has_source_duplicates", False)),
            "status_group": _format_scalar(row.get("status_group")),
            "article_name": _format_scalar(row.get("article_name")),
            "article_code": _format_scalar(row.get("article_code")),
            "contract_name": _format_scalar(row.get("contract_name")),
            "expense_subject": _format_scalar(row.get("expense_subject")),
            "vendor_id": _format_scalar(row.get("vendor_id")),
            "vendor_label": _format_scalar(row.get("vendor_name")),
            "organization_id": _format_scalar(row.get("organization_id")),
            "organization_label": _format_scalar(row.get("organization_name")),
            "project_name": _format_scalar(row.get("project_name")),
            "department_name": _format_scalar(row.get("department_name")),
            "l1_category_id": _format_scalar(row.get("l1_category_id")),
            "l1_category_label": _format_scalar(row.get("l1_category")),
            "l2_category_id": _format_scalar(row.get("l2_category_id")),
            "l2_category_label": _format_scalar(row.get("l2_category")),
            "l3_category_id": _format_scalar(row.get("l3_category_id")),
            "l3_category_label": _format_scalar(row.get("l3_category")),
            "classification_confidence": _format_scalar(row.get("classification_confidence")),
            "matched_rule_id": _format_scalar(row.get("matched_rule_id")),
            "matched_keywords": _format_scalar(row.get("matched_keywords")),
            "matched_vendor_pattern": _format_scalar(row.get("matched_vendor_pattern")),
            "matched_article_pattern": _format_scalar(row.get("matched_article_pattern")),
            "classification_reason_human": _format_scalar(row.get("classification_reason_human")),
            "has_transformations": True,
        }


def _build_expense_subject(row: pd.Series) -> str:
    contract_name = str(row.get("contract_name", "") or "").strip()
    article_name = str(row.get("article_name", "") or "").strip()
    if contract_name and article_name and contract_name.lower() != article_name.lower():
        return f"{contract_name} / {article_name}"
    return contract_name or article_name


def _parse_detail_row_id(detail_row_id: str) -> int:
    value = str(detail_row_id).replace("row_", "", 1)
    return int(value)


def _nullable_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _format_scalar(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return str(value)


def _serialize_non_empty(values: dict[str, object]) -> dict[str, str]:
    output: dict[str, str] = {}
    for key, value in values.items():
        formatted = _format_scalar(value)
        if formatted:
            output[str(key)] = formatted
    return output


def _build_transformation_log(raw_row: pd.Series, pipeline_row: pd.Series) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for field in AMOUNT_FIELDS:
        _append_change(changes, raw_row, pipeline_row, field, "amount_numeric_parse", "Парсинг числовой суммы")
    for field in DATE_FIELDS:
        _append_change(changes, raw_row, pipeline_row, field, "date_normalization", "Нормализация даты")
    for field in TEXT_FIELDS:
        _append_change(changes, raw_row, pipeline_row, field, "text_cleanup", "Нормализация текстового поля")
    for field in ENTITY_FIELDS:
        _append_change(changes, raw_row, pipeline_row, field, "entity_normalization", "Нормализация справочника сущностей")

    raw_status = _format_scalar(raw_row.get("registrator_status_name"))
    mapped_status = _format_scalar(pipeline_row.get("business_status"))
    if mapped_status and raw_status != mapped_status:
        changes.append(
            {
                "rule_id": "status_mapping",
                "rule_label": "Маппинг статуса в бизнес-статус",
                "field": "business_status",
                "before": raw_status,
                "after": mapped_status,
            }
        )

    for field in ("year", "month", "quarter", "year_month"):
        derived_value = _format_scalar(pipeline_row.get(field))
        if derived_value:
            changes.append(
                {
                    "rule_id": "date_derived_fields",
                    "rule_label": "Расчет производных полей отчетного периода",
                    "field": field,
                    "before": "",
                    "after": derived_value,
                }
            )
    return changes


def _append_change(
    changes: list[dict[str, str]],
    raw_row: pd.Series,
    pipeline_row: pd.Series,
    field: str,
    rule_id: str,
    rule_label: str,
) -> None:
    if field not in raw_row.index or field not in pipeline_row.index:
        return
    before = _format_scalar(raw_row[field])
    after = _format_scalar(pipeline_row[field])
    if before == after:
        return
    changes.append(
        {
            "rule_id": rule_id,
            "rule_label": rule_label,
            "field": field,
            "before": before,
            "after": after,
        }
    )
