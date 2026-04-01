"""Build a frontend-friendly JSON payload for the interactive HTML dashboard."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any
import unicodedata

import pandas as pd

from it_spend_dashboard.ingestion.normalize_columns import CYRILLIC_TO_LATIN
from it_spend_dashboard.insights.narratives import build_management_narratives
from it_spend_dashboard.modeling.aggregations import build_aggregations
from it_spend_dashboard.modeling.facts import build_payments_fact
from it_spend_dashboard.utils.schemas import DashboardPayload

STATUS_LABELS = {
    "paid": "Оплачено",
    "approved_not_paid": "Согласовано, не оплачено",
    "in_approval": "На согласовании",
    "rejected": "Отклонено",
    "other": "Прочее",
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


def build_dashboard_payload(
    payments_fact: pd.DataFrame,
    *,
    insights: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    """Build a single frontend-oriented dashboard payload."""
    fact = build_payments_fact(payments_fact) if "payment_id" not in payments_fact.columns else payments_fact.copy()
    aggregations = build_aggregations(fact)
    resolved_insights = insights if insights is not None else build_management_narratives(fact, limit=5)
    detail_row_details = _build_detail_row_details()
    detail_rows = _build_detail_rows(fact, detail_row_details=detail_row_details)

    payload = {
        "metadata": _build_metadata(fact),
        "filters": _build_filters(fact),
        "kpis": _build_kpis(fact),
        "yearly_comparison": aggregations["agg_year_compare_2025_2026"].to_dict(orient="records"),
        "monthly_trends": aggregations["agg_kpi_year_month"].to_dict(orient="records"),
        "categories_tree": _build_categories_tree(fact),
        "status_breakdown": _build_status_breakdown(aggregations["agg_status"]),
        "vendors": _build_entity_aggregate(aggregations["agg_vendors"], "vendor_name"),
        "organizations": _build_entity_aggregate(aggregations["agg_orgs"], "organization_name"),
        "insights": resolved_insights,
        "detail_rows": detail_rows,
        "detail_row_index": _build_detail_row_index(detail_rows),
        "detail_row_details": detail_row_details,
    }
    validate_dashboard_payload(payload)
    return payload


def save_dashboard_payload(
    payments_fact: pd.DataFrame,
    *,
    output_path: Path | None = None,
    insights: list[dict[str, object]] | None = None,
) -> Path:
    """Build and persist the dashboard payload as JSON."""
    base_dir = Path(__file__).resolve().parents[3]
    target = output_path or (base_dir / "data" / "export" / "dashboard_payload.json")
    payload = build_dashboard_payload(payments_fact, insights=insights)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def validate_dashboard_payload(payload: dict[str, Any]) -> DashboardPayload:
    """Validate the dashboard payload structure."""
    return DashboardPayload.model_validate(payload)


def _build_metadata(fact: pd.DataFrame) -> dict[str, Any]:
    """Build dashboard metadata."""
    years = sorted(int(year) for year in fact["year"].dropna().astype(int).unique().tolist())
    return {
        "title": "Дашборд расходов IT-департамента",
        "generated_at": datetime.now(UTC).isoformat(),
        "currency": "RUB",
        "detail_rows_count": len(fact),
        "available_years": years,
    }


def _build_filters(fact: pd.DataFrame) -> dict[str, Any]:
    """Build filter descriptors for the frontend."""
    return {
        "years": _filter_options(sorted(fact["year"].dropna().astype(int).unique().tolist())),
        "months": [
            {"id": str(month), "label": f"{month:02d}"}
            for month in sorted(fact["month"].dropna().astype(int).unique().tolist())
        ],
        "statuses": [
            {"id": status, "label": STATUS_LABELS.get(status, status)}
            for status in sorted(fact["status_group"].fillna("").astype(str).unique().tolist())
            if status
        ],
        "categories_l1": _filter_options(sorted(fact["l1_category"].fillna("").astype(str).unique().tolist())),
        "categories_l2": _filter_options(sorted(fact["l2_category"].fillna("").astype(str).unique().tolist())),
        "categories_l3": _filter_options(sorted(fact["l3_category"].fillna("").astype(str).unique().tolist())),
        "organizations": _filter_options(sorted(fact["organization_name"].fillna("").astype(str).unique().tolist())),
        "vendors": _filter_options(sorted(fact["vendor_name"].fillna("").astype(str).unique().tolist())),
    }


def _build_kpis(fact: pd.DataFrame) -> list[dict[str, Any]]:
    """Build headline KPI cards."""
    total_amount = float(fact["amount"].sum())
    paid_amount = float(fact.loc[fact["status_group"] == "paid", "amount"].sum())
    unpaid_amount = float(fact.loc[fact["status_group"].isin(["approved_not_paid", "in_approval"]), "amount"].sum())
    review_share = float(
        ((fact["l1_category"] == "other_it") | fact["classification_confidence"].isin(["low", "unclassified"])).mean()
    ) if len(fact) else 0.0
    return [
        {"id": "total_amount", "label": "Общая сумма расходов", "value": round(total_amount, 2)},
        {"id": "payments_count", "label": "Количество операций", "value": int(fact["payment_id"].nunique())},
        {"id": "paid_amount", "label": "Оплаченные расходы", "value": round(paid_amount, 2)},
        {"id": "unpaid_amount", "label": "Неоплаченные и в согласовании", "value": round(unpaid_amount, 2)},
        {"id": "review_share", "label": "Доля записей на проверку", "value": f"{review_share:.1%}"},
    ]


def _build_categories_tree(fact: pd.DataFrame) -> list[dict[str, Any]]:
    """Build an L1/L2/L3 category tree with pre-aggregated metrics."""
    tree: list[dict[str, Any]] = []
    grouped_l1 = _aggregate_rows(fact, ["l1_category"])
    for _, l1_row in grouped_l1.iterrows():
        l1_value = str(l1_row["l1_category"])
        l1_scope = fact[fact["l1_category"] == l1_value]
        l2_children: list[dict[str, Any]] = []
        grouped_l2 = _aggregate_rows(l1_scope, ["l2_category"])
        for _, l2_row in grouped_l2.iterrows():
            l2_value = str(l2_row["l2_category"])
            l2_scope = l1_scope[l1_scope["l2_category"] == l2_value]
            l3_children = [
                {
                    "id": _slugify(str(l3_row["l3_category"])),
                    "label": str(l3_row["l3_category"]),
                    "level": "l3",
                    "total_amount": float(l3_row["total_amount"]),
                    "payments_count": int(l3_row["payments_count"]),
                    "children": [],
                }
                for _, l3_row in _aggregate_rows(l2_scope, ["l3_category"]).iterrows()
            ]
            l2_children.append(
                {
                    "id": _slugify(l2_value),
                    "label": l2_value,
                    "level": "l2",
                    "total_amount": float(l2_row["total_amount"]),
                    "payments_count": int(l2_row["payments_count"]),
                    "children": l3_children,
                }
            )
        tree.append(
            {
                "id": _slugify(l1_value),
                "label": l1_value,
                "level": "l1",
                "total_amount": float(l1_row["total_amount"]),
                "payments_count": int(l1_row["payments_count"]),
                "children": l2_children,
            }
        )
    return tree


def _build_status_breakdown(agg_status: pd.DataFrame) -> list[dict[str, Any]]:
    """Build UI-friendly status aggregates with Russian labels."""
    rows: list[dict[str, Any]] = []
    for _, row in agg_status.iterrows():
        status_id = str(row["status_group"])
        rows.append(
            {
                "status_id": status_id,
                "status_label": STATUS_LABELS.get(status_id, status_id),
                "total_amount": float(row["total_amount"]),
                "payments_count": int(row["payments_count"]),
            }
        )
    return rows


def _build_entity_aggregate(aggregation: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    """Build vendor/organization aggregates with id-friendly fields."""
    rows: list[dict[str, Any]] = []
    for _, row in aggregation.iterrows():
        label = str(row[column])
        rows.append(
            {
                "id": _slugify(label),
                "label": label,
                "total_amount": float(row["total_amount"]),
                "payments_count": int(row["payments_count"]),
            }
        )
    return rows


def _build_detail_rows(
    fact: pd.DataFrame,
    *,
    detail_row_details: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build normalized detail rows for frontend-only drill-downs."""
    rows: list[dict[str, Any]] = []
    for row_number, (_, row) in enumerate(fact.iterrows()):
        detail_row_id = f"row_{row_number}"
        rows.append(
            {
                "detail_row_id": detail_row_id,
                "payment_id": str(row["payment_id"]),
                "period_date": _format_date(row["period_date"]),
                "year": _nullable_int(row["year"]),
                "month": _nullable_int(row["month"]),
                "quarter": _nullable_int(row["quarter"]),
                "amount": float(row["amount"]),
                "status_group": str(row["status_group"]),
                "article_name": str(row["article_name"]),
                "article_code": str(row["article_code"]),
                "contract_name": str(row.get("contract_name", "")),
                "expense_subject": _build_expense_subject(row),
                "vendor_id": _slugify(str(row["vendor_name"])),
                "vendor_label": str(row["vendor_name"]),
                "organization_id": _slugify(str(row["organization_name"])),
                "organization_label": str(row["organization_name"]),
                "project_name": str(row["project_name"]),
                "department_name": str(row["department_name"]),
                "l1_category_id": _slugify(str(row["l1_category"])),
                "l1_category_label": str(row["l1_category"]),
                "l2_category_id": _slugify(str(row["l2_category"])),
                "l2_category_label": str(row["l2_category"]),
                "l3_category_id": _slugify(str(row["l3_category"])),
                "l3_category_label": str(row["l3_category"]),
                "classification_confidence": str(row["classification_confidence"]),
                "matched_rule_id": str(row.get("matched_rule_id", "")),
                "matched_keywords": str(row.get("matched_keywords", "")),
                "matched_vendor_pattern": str(row.get("matched_vendor_pattern", "")),
                "matched_article_pattern": str(row.get("matched_article_pattern", "")),
                "classification_reason_human": str(row.get("classification_reason_human", "")),
                "has_transformations": bool(detail_row_details.get(detail_row_id, {}).get("transformations")),
            }
        )
    return rows


def _build_detail_row_index(detail_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Build pre-indexed slices for frontend drill-down by click target."""
    index: dict[str, list[str]] = {}
    for row in detail_rows:
        detail_row_id = str(row["detail_row_id"])
        keys = {
            f"year:{row['year']}",
            f"month:{row['month']}",
            f"status:{row['status_group']}",
            f"organization:{row['organization_id']}",
            f"vendor:{row['vendor_id']}",
            f"l1:{row['l1_category_id']}",
            f"l2:{row['l2_category_id']}",
            f"l3:{row['l3_category_id']}",
        }
        for key in keys:
            index.setdefault(key, []).append(detail_row_id)
    return index


def _build_detail_row_details() -> dict[str, dict[str, Any]]:
    """Build a row-level audit trail from interim artifacts."""
    base_dir = Path(__file__).resolve().parents[3]
    interim_dir = base_dir / "data" / "interim"
    ingested_path = interim_dir / "payments_ingested.parquet"
    classified_path = interim_dir / "payments_classified.parquet"
    cleaned_path = interim_dir / "payments_clean.parquet"

    if not ingested_path.exists():
        return {}

    raw = pd.read_parquet(ingested_path)
    if classified_path.exists():
        post = pd.read_parquet(classified_path)
    elif cleaned_path.exists():
        post = pd.read_parquet(cleaned_path)
    else:
        return {}

    details: dict[str, dict[str, Any]] = {}
    record_count = min(len(raw), len(post))
    for row_number in range(record_count):
        detail_row_id = f"row_{row_number}"
        raw_row = raw.iloc[row_number]
        post_row = post.iloc[row_number]
        details[detail_row_id] = {
            "detail_row_id": detail_row_id,
            "raw_attributes": _serialize_raw_attributes(raw_row),
            "pipeline_attributes": _serialize_pipeline_attributes(post_row),
            "transformations": _build_transformation_log(raw_row, post_row),
        }
    return details


def _aggregate_rows(fact: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    """Aggregate a fact table by selected dimensions."""
    return (
        fact.groupby(dimensions, dropna=False, as_index=False)
        .agg(total_amount=("amount", "sum"), payments_count=("payment_id", "nunique"))
        .sort_values(dimensions)
        .reset_index(drop=True)
    )


def _filter_options(values: list[object]) -> list[dict[str, str]]:
    """Build id/label pairs for filter controls."""
    return [{"id": _slugify(str(value)), "label": str(value)} for value in values if str(value)]


def _slugify(value: str) -> str:
    """Convert raw values into stable frontend ids."""
    raw_value = value.strip().lower()
    transliterated = raw_value.translate(CYRILLIC_TO_LATIN)
    normalized_ascii = unicodedata.normalize("NFKD", transliterated).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", normalized_ascii).strip("_")
    if normalized:
        return normalized
    unicode_fallback = "_".join(f"{ord(char):x}" for char in raw_value if not char.isspace())
    return f"u_{unicode_fallback}" if unicode_fallback else "unknown"


def _format_date(value: object) -> str:
    """Format date-like values for payload serialization."""
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).date().isoformat()


def _nullable_int(value: object) -> int | None:
    """Convert nullable numeric values to Python integers."""
    if pd.isna(value):
        return None
    return int(value)


def _build_expense_subject(row: pd.Series) -> str:
    """Build a more business-friendly subject label for detail rows."""
    contract_name = str(row.get("contract_name", "") or "").strip()
    article_name = str(row.get("article_name", "") or "").strip()
    if contract_name and article_name and contract_name.lower() != article_name.lower():
        return f"{contract_name} / {article_name}"
    return contract_name or article_name


def _serialize_raw_attributes(row: pd.Series) -> dict[str, str]:
    """Serialize non-empty original row attributes for the audit modal."""
    attributes: dict[str, str] = {}
    for column, value in row.items():
        serialized = _serialize_value(value)
        if serialized:
            attributes[str(column)] = serialized
    return attributes


def _serialize_pipeline_attributes(row: pd.Series) -> dict[str, str]:
    """Serialize important post-pipeline attributes for the audit modal."""
    fields = [
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
    output: dict[str, str] = {}
    for field in fields:
        if field in row.index:
            serialized = _serialize_value(row[field])
            if serialized:
                output[field] = serialized
    return output


def _build_transformation_log(raw_row: pd.Series, post_row: pd.Series) -> list[dict[str, str]]:
    """Build a row-level list of cleaning and normalization changes."""
    changes: list[dict[str, str]] = []

    for field in AMOUNT_FIELDS:
        _append_change(changes, raw_row, post_row, field, "amount_numeric_parse", "Парсинг числовой суммы")
    for field in DATE_FIELDS:
        _append_change(changes, raw_row, post_row, field, "date_normalization", "Нормализация даты")
    for field in TEXT_FIELDS:
        _append_change(changes, raw_row, post_row, field, "text_cleanup", "Нормализация текстового поля")
    for field in ENTITY_FIELDS:
        _append_change(changes, raw_row, post_row, field, "entity_normalization", "Нормализация справочника сущностей")

    raw_status = _serialize_value(raw_row.get("registrator_status_name"))
    mapped_status = _serialize_value(post_row.get("business_status"))
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
        derived_value = _serialize_value(post_row.get(field))
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
    post_row: pd.Series,
    field: str,
    rule_id: str,
    rule_label: str,
) -> None:
    """Append a before/after change record when a field value was transformed."""
    if field not in raw_row.index or field not in post_row.index:
        return
    before = _serialize_value(raw_row[field])
    after = _serialize_value(post_row[field])
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


def _serialize_value(value: object) -> str:
    """Convert scalar values into UI-friendly strings."""
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)
