"""Build a frontend-friendly JSON payload for the interactive HTML dashboard."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd

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


def build_dashboard_payload(
    payments_fact: pd.DataFrame,
    *,
    insights: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    """Build a single frontend-oriented dashboard payload."""
    fact = build_payments_fact(payments_fact) if "payment_id" not in payments_fact.columns else payments_fact.copy()
    aggregations = build_aggregations(fact)
    resolved_insights = insights or build_management_narratives(fact, limit=5)
    detail_rows = _build_detail_rows(fact)

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


def _build_detail_rows(fact: pd.DataFrame) -> list[dict[str, Any]]:
    """Build normalized detail rows for frontend-only drill-downs."""
    rows: list[dict[str, Any]] = []
    for _, row in fact.iterrows():
        rows.append(
            {
                "payment_id": str(row["payment_id"]),
                "period_date": _format_date(row["period_date"]),
                "year": _nullable_int(row["year"]),
                "month": _nullable_int(row["month"]),
                "quarter": _nullable_int(row["quarter"]),
                "amount": float(row["amount"]),
                "status_group": str(row["status_group"]),
                "article_name": str(row["article_name"]),
                "article_code": str(row["article_code"]),
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
            }
        )
    return rows


def _build_detail_row_index(detail_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Build pre-indexed slices for frontend drill-down by click target."""
    index: dict[str, list[str]] = {}
    for row in detail_rows:
        payment_id = str(row["payment_id"])
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
            index.setdefault(key, []).append(payment_id)
    return index


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
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", value.strip().lower()).strip("_")
    return normalized or "unknown"


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
