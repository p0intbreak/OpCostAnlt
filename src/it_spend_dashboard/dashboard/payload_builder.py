"""Build a compact frontend-friendly payload for the dashboard summary view."""

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


def build_dashboard_payload(
    payments_fact: pd.DataFrame,
    *,
    insights: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    """Build a compact summary payload for the dashboard frontend."""
    fact = build_payments_fact(payments_fact) if "payment_id" not in payments_fact.columns else payments_fact.copy()
    aggregations = build_aggregations(fact)
    resolved_insights = insights if insights is not None else build_management_narratives(fact, limit=5)

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
        "departments": _build_entity_aggregate(aggregations["agg_department"], "department_name"),
        "category_yoy": _build_category_yoy(fact),
        "insights": resolved_insights,
        "detail_rows": [],
        "detail_row_index": {},
        "detail_row_details": {},
    }
    validate_dashboard_payload(payload)
    return payload


def save_dashboard_payload(
    payments_fact: pd.DataFrame,
    *,
    output_path: Path | None = None,
    insights: list[dict[str, object]] | None = None,
) -> Path:
    """Build and persist the dashboard summary payload as JSON."""
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
    years = sorted(int(year) for year in fact["year"].dropna().astype(int).unique().tolist())
    return {
        "title": "Дашборд расходов IT-департамента",
        "generated_at": datetime.now(UTC).isoformat(),
        "currency": "RUB",
        "detail_rows_count": len(fact),
        "available_years": years,
    }


def _build_filters(fact: pd.DataFrame) -> dict[str, Any]:
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


def _build_category_yoy(fact: pd.DataFrame) -> list[dict[str, Any]]:
    years = sorted(int(year) for year in fact["year"].dropna().astype(int).unique().tolist())
    if len(years) < 2:
        return []
    left_year, right_year = years[0], years[-1]
    grouped = (
        fact[fact["year"].isin([left_year, right_year])]
        .groupby(["l1_category", "year"], as_index=False)
        .agg(total_amount=("amount", "sum"))
    )
    pivot = grouped.pivot(index="l1_category", columns="year", values="total_amount").fillna(0.0).reset_index()
    rows: list[dict[str, Any]] = []
    for _, row in pivot.iterrows():
        previous_amount = float(row.get(left_year, 0.0))
        current_amount = float(row.get(right_year, 0.0))
        delta_amount = current_amount - previous_amount
        rows.append(
            {
                "id": _slugify(str(row["l1_category"])),
                "label": str(row["l1_category"]),
                "left_year": left_year,
                "right_year": right_year,
                "previous_amount": previous_amount,
                "current_amount": current_amount,
                "delta_amount": delta_amount,
                "delta_share": (delta_amount / previous_amount) if previous_amount else 1.0,
            }
        )
    return sorted(rows, key=lambda item: abs(float(item["delta_amount"])), reverse=True)


def _aggregate_rows(fact: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    return (
        fact.groupby(dimensions, dropna=False, as_index=False)
        .agg(total_amount=("amount", "sum"), payments_count=("payment_id", "nunique"))
        .sort_values(dimensions)
        .reset_index(drop=True)
    )


def _filter_options(values: list[object]) -> list[dict[str, str]]:
    return [{"id": _slugify(str(value)), "label": str(value)} for value in values if str(value)]


def _slugify(value: str) -> str:
    raw_value = value.strip().lower()
    transliterated = raw_value.translate(CYRILLIC_TO_LATIN)
    normalized_ascii = unicodedata.normalize("NFKD", transliterated).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", normalized_ascii).strip("_")
    return normalized or "unknown"
