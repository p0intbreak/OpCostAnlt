"""Automatic insight generators for the IT spend dashboard."""

from __future__ import annotations

from typing import TypedDict

import pandas as pd


class Insight(TypedDict):
    """Single dashboard insight payload for the UI."""

    title: str
    metric: str
    explanation: str
    severity: str
    supporting_filters: dict[str, object]


def top_spend_categories(payments_fact: pd.DataFrame) -> Insight:
    """Highlight the largest spend category across the fact table."""
    grouped = (
        payments_fact.groupby("l1_category", as_index=False)
        .agg(total_amount=("amount", "sum"))
        .sort_values("total_amount", ascending=False)
        .reset_index(drop=True)
    )
    if grouped.empty:
        return _empty_insight("Крупнейшая категория расходов")

    top_row = grouped.iloc[0]
    total = float(grouped["total_amount"].sum())
    share = float(top_row["total_amount"] / total) if total else 0.0
    severity = "warning" if share >= 0.35 else "info"
    return {
        "title": "Крупнейшая категория расходов",
        "metric": f"{top_row['l1_category']}: {top_row['total_amount']:.2f} ({share:.1%})",
        "explanation": (
            f"Наибольшая доля затрат приходится на категорию "
            f"«{top_row['l1_category']}». Ее удельный вес составляет {share:.1%} "
            f"от общего объема расходов, что важно учитывать при бюджетном контроле."
        ),
        "severity": severity,
        "supporting_filters": {"l1_category": top_row["l1_category"]},
    }


def yoy_growth_categories(payments_fact: pd.DataFrame) -> Insight:
    """Compare category spend between 2025 and 2026 and highlight top growth."""
    filtered = payments_fact[payments_fact["year"].isin([2025, 2026])].copy()
    grouped = (
        filtered.groupby(["l1_category", "year"], as_index=False)
        .agg(total_amount=("amount", "sum"))
    )
    pivot = grouped.pivot(index="l1_category", columns="year", values="total_amount").fillna(0.0)
    if pivot.empty or 2025 not in pivot.columns or 2026 not in pivot.columns:
        return _empty_insight("Рост расходов год к году")

    pivot["delta"] = pivot[2026] - pivot[2025]
    pivot["growth_rate"] = pivot.apply(
        lambda row: (row[2026] / row[2025] - 1.0) if row[2025] > 0 else float("inf") if row[2026] > 0 else 0.0,
        axis=1,
    )
    top_category = pivot.sort_values(["delta", "growth_rate"], ascending=False).head(1)
    if top_category.empty:
        return _empty_insight("Рост расходов год к году")

    category_name = str(top_category.index[0])
    row = top_category.iloc[0]
    growth_text = "новая категория расходов" if row["growth_rate"] == float("inf") else f"{row['growth_rate']:.1%}"
    severity = "critical" if row["delta"] > 0 and (row["growth_rate"] == float("inf") or row["growth_rate"] >= 0.5) else "warning"
    return {
        "title": "Рост расходов год к году",
        "metric": f"{category_name}: {row['delta']:.2f} ({growth_text})",
        "explanation": (
            f"По сравнению с 2025 годом максимальный прирост в 2026 году наблюдается "
            f"в категории «{category_name}». Абсолютное изменение составляет {row['delta']:.2f}, "
            f"что указывает на необходимость проверки драйверов роста и бюджетных лимитов."
        ),
        "severity": severity,
        "supporting_filters": {"l1_category": category_name, "year": [2025, 2026]},
    }


def status_bottlenecks(payments_fact: pd.DataFrame) -> Insight:
    """Highlight the most material unpaid approval bottleneck."""
    statuses = ["approved_not_paid", "in_approval"]
    backlog = payments_fact[payments_fact["status_group"].isin(statuses)].copy()
    if backlog.empty:
        return {
            "title": "Статусные узкие места",
            "metric": "0.00",
            "explanation": "Существенных зависших сумм в статусах согласования и ожидания оплаты не выявлено.",
            "severity": "info",
            "supporting_filters": {"status_group": statuses},
        }

    grouped = (
        backlog.groupby("status_group", as_index=False)
        .agg(total_amount=("amount", "sum"), payments_count=("payment_id", "nunique"))
        .sort_values("total_amount", ascending=False)
        .reset_index(drop=True)
    )
    top_row = grouped.iloc[0]
    severity = "critical" if top_row["status_group"] == "approved_not_paid" else "warning"
    return {
        "title": "Статусные узкие места",
        "metric": f"{top_row['status_group']}: {top_row['total_amount']:.2f}",
        "explanation": (
            f"Наибольший объем зависших расходов находится в статусе "
            f"«{top_row['status_group']}». В этом статусе сосредоточено "
            f"{top_row['payments_count']} операций на сумму {top_row['total_amount']:.2f}."
        ),
        "severity": severity,
        "supporting_filters": {"status_group": top_row["status_group"]},
    }


def vendor_concentration(payments_fact: pd.DataFrame) -> Insight:
    """Measure concentration of spend in the largest vendor."""
    grouped = (
        payments_fact.groupby("vendor_name", as_index=False)
        .agg(total_amount=("amount", "sum"))
        .sort_values("total_amount", ascending=False)
        .reset_index(drop=True)
    )
    if grouped.empty:
        return _empty_insight("Концентрация на поставщиках")

    top_row = grouped.iloc[0]
    total = float(grouped["total_amount"].sum())
    share = float(top_row["total_amount"] / total) if total else 0.0
    severity = "critical" if share >= 0.5 else "warning" if share >= 0.3 else "info"
    return {
        "title": "Концентрация на поставщиках",
        "metric": f"{top_row['vendor_name']}: {share:.1%}",
        "explanation": (
            f"На одного поставщика приходится {share:.1%} всех расходов. "
            f"Крупнейший контрагент «{top_row['vendor_name']}» формирует затраты "
            f"на сумму {top_row['total_amount']:.2f}, что отражает уровень зависимости от поставщика."
        ),
        "severity": severity,
        "supporting_filters": {"vendor_name": top_row["vendor_name"]},
    }


def large_unpaid_items(payments_fact: pd.DataFrame) -> Insight:
    """Highlight the largest unpaid or in-approval expense item."""
    unpaid = payments_fact[payments_fact["status_group"].isin(["approved_not_paid", "in_approval"])].copy()
    if unpaid.empty:
        return {
            "title": "Крупные неоплаченные позиции",
            "metric": "0.00",
            "explanation": "Крупные неоплаченные позиции не обнаружены.",
            "severity": "info",
            "supporting_filters": {"status_group": ["approved_not_paid", "in_approval"]},
        }

    row = unpaid.sort_values("amount", ascending=False).iloc[0]
    severity = "critical" if row["amount"] >= float(unpaid["amount"].median()) * 2 else "warning"
    return {
        "title": "Крупные неоплаченные позиции",
        "metric": f"{row['amount']:.2f}",
        "explanation": (
            f"Крупнейшая зависшая сумма составляет {row['amount']:.2f}. "
            f"Операция относится к категории «{row['l1_category']} / {row['l2_category']}» "
            f"и контрагенту «{row['vendor_name']}»."
        ),
        "severity": severity,
        "supporting_filters": {
            "payment_id": row["payment_id"],
            "status_group": row["status_group"],
            "vendor_name": row["vendor_name"],
        },
    }


def uncategorized_share(payments_fact: pd.DataFrame) -> Insight:
    """Measure the share of records that remain uncategorized or weakly classified."""
    mask = (payments_fact["l1_category"] == "other_it") | (
        payments_fact["classification_confidence"].isin(["low", "unclassified"])
    )
    share = float(mask.mean()) if len(payments_fact) else 0.0
    count = int(mask.sum())
    severity = "critical" if share >= 0.2 else "warning" if share >= 0.1 else "info"
    return {
        "title": "Доля неклассифицированных расходов",
        "metric": f"{count} записей ({share:.1%})",
        "explanation": (
            f"Доля расходов, требующих ручной проверки или уточнения категории, "
            f"составляет {share:.1%}. Высокое значение этого показателя снижает "
            f"качество управленческой отчетности и требует пополнения правил классификации."
        ),
        "severity": severity,
        "supporting_filters": {"review_required": True},
    }


def anomaly_candidates(payments_fact: pd.DataFrame) -> Insight:
    """Detect simple amount anomalies using a category-level IQR rule."""
    if payments_fact.empty:
        return _empty_insight("Потенциальные аномалии")

    candidates: list[pd.DataFrame] = []
    for _, group in payments_fact.groupby("l1_category"):
        if len(group) < 4:
            continue
        q1 = group["amount"].quantile(0.25)
        q3 = group["amount"].quantile(0.75)
        iqr = q3 - q1
        upper_bound = q3 + 1.5 * iqr
        abnormal = group[group["amount"] > upper_bound]
        if not abnormal.empty:
            candidates.append(abnormal)

    if not candidates:
        return {
            "title": "Потенциальные аномалии",
            "metric": "0",
            "explanation": "Выраженных аномалий по суммам внутри категорий не выявлено.",
            "severity": "info",
            "supporting_filters": {},
        }

    anomalies = pd.concat(candidates, ignore_index=True)
    top_row = anomalies.sort_values("amount", ascending=False).iloc[0]
    return {
        "title": "Потенциальные аномалии",
        "metric": f"{len(anomalies)} кандидатов",
        "explanation": (
            f"Обнаружены операции с нетипично высокой суммой относительно своей категории. "
            f"Максимальное отклонение наблюдается по записи на {top_row['amount']:.2f} "
            f"в категории «{top_row['l1_category']}»."
        ),
        "severity": "warning",
        "supporting_filters": {"l1_category": top_row["l1_category"], "payment_id": top_row["payment_id"]},
    }


def _empty_insight(title: str) -> Insight:
    """Return a neutral empty-state insight."""
    return {
        "title": title,
        "metric": "0",
        "explanation": "Недостаточно данных для формирования управленческого вывода.",
        "severity": "info",
        "supporting_filters": {},
    }

