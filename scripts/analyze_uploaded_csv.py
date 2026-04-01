from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from it_spend_dashboard.cleaning.amounts import normalize_amount_columns
from it_spend_dashboard.cleaning.dates import normalize_date_columns
from it_spend_dashboard.ingestion.load_csv import load_payments_csv


TOP_N = 10


def build_summary(df: pd.DataFrame) -> dict[str, object]:
    work = normalize_date_columns(normalize_amount_columns(df))
    amount = work["summa"] if "summa" in work.columns else pd.Series(dtype="float64")
    period = work["period"] if "period" in work.columns else pd.Series(dtype="datetime64[ns]")

    missing = (
        work.isna()
        .sum()
        .sort_values(ascending=False)
        .rename("null_count")
        .to_frame()
    )
    missing["null_share"] = (missing["null_count"] / len(work)).round(4)
    missing = missing[missing["null_count"] > 0]

    def grouped_stats(group_col: str, label_col: str | None = None) -> list[dict[str, object]]:
        if group_col not in work.columns:
            return []
        label = label_col or group_col
        grouped = (
            work.groupby(group_col, dropna=False)
            .agg(
                rows=("id", "size"),
                total_amount=("summa", "sum"),
                median_amount=("summa", "median"),
            )
            .sort_values("total_amount", ascending=False)
            .head(TOP_N)
            .reset_index()
            .rename(columns={group_col: label})
        )
        grouped["share_of_total"] = (
            grouped["total_amount"] / max(float(amount.sum()), 1.0)
        ).round(4)
        return _records(grouped)

    monthly = []
    if "year_month" in work.columns:
        monthly_df = (
            work.groupby("year_month", dropna=False)
            .agg(
                rows=("id", "size"),
                total_amount=("summa", "sum"),
                paid_amount=("summa", lambda s: s[work.loc[s.index, "registrator_status_name"].eq("Оплачен")].sum()),
            )
            .sort_values("year_month")
            .reset_index()
        )
        monthly_df["avg_amount"] = (monthly_df["total_amount"] / monthly_df["rows"]).round(2)
        monthly = _records(monthly_df)

    status = []
    if "registrator_status_name" in work.columns:
        status_df = (
            work.groupby("registrator_status_name", dropna=False)
            .agg(rows=("id", "size"), total_amount=("summa", "sum"))
            .sort_values("total_amount", ascending=False)
            .reset_index()
        )
        status_df["share_of_total"] = (status_df["total_amount"] / max(float(amount.sum()), 1.0)).round(4)
        status = _records(status_df)

    top_transactions = []
    transaction_cols = [
        col
        for col in [
            "bit_zayavka_na_rashodovanie_sredstv_nomer",
            "period",
            "summa",
            "registrator_status_name",
            "bit_stati_oborotov_naimenovanie",
            "kontragenti_naimenovanie",
            "organizacii_naimenovanie",
            "podrazdeleniya_naimenovanie",
        ]
        if col in work.columns
    ]
    if transaction_cols:
        top_transactions = _records(
            work[transaction_cols]
            .sort_values("summa", ascending=False)
            .head(TOP_N)
        )

    duplicate_metrics = {}
    for col in ("id", "registrator_guid", "guid_link", "bit_zayavka_na_rashodovanie_sredstv_nomer"):
        if col in work.columns:
            duplicate_metrics[col] = int(work[col].duplicated(keep=False).sum())

    amount_quantiles = amount.quantile([0.5, 0.9, 0.95, 0.99]).round(2).to_dict() if not amount.empty else {}
    p99 = float(amount.quantile(0.99)) if len(amount) else 0.0
    large_items_count = int((amount >= p99).sum()) if p99 else 0

    return {
        "overview": {
            "rows": int(len(work)),
            "columns": int(work.shape[1]),
            "period_min": None if period.dropna().empty else str(period.min().date()),
            "period_max": None if period.dropna().empty else str(period.max().date()),
            "total_amount": round(float(amount.sum()), 2),
            "mean_amount": round(float(amount.mean()), 2),
            "median_amount": round(float(amount.median()), 2),
            "p99_amount": round(p99, 2),
            "large_items_count_at_or_above_p99": large_items_count,
        },
        "quality": {
            "duplicate_metrics": duplicate_metrics,
            "top_missing_columns": _records(missing.head(10).reset_index().rename(columns={"index": "column"})),
            "amount_quantiles": amount_quantiles,
        },
        "status_breakdown": status,
        "monthly_trend": monthly,
        "top_categories": grouped_stats("bit_stati_oborotov_naimenovanie", "category"),
        "top_vendors": grouped_stats("kontragenti_naimenovanie", "vendor"),
        "top_organizations": grouped_stats("organizacii_naimenovanie", "organization"),
        "top_departments": grouped_stats("podrazdeleniya_naimenovanie", "department"),
        "top_transactions": top_transactions,
    }


def build_markdown(summary: dict[str, object], source_path: Path) -> str:
    overview = summary["overview"]
    quality = summary["quality"]
    lines = [
        "# Анализ выгрузки 1С",
        "",
        f"Источник: `{source_path}`",
        "",
        "## Кратко",
        "",
        f"- Строк: {overview['rows']:,}".replace(",", " "),
        f"- Колонок: {overview['columns']}",
        f"- Период данных: {overview['period_min']} .. {overview['period_max']}",
        f"- Общая сумма: {format_money(overview['total_amount'])}",
        f"- Средняя сумма заявки: {format_money(overview['mean_amount'])}",
        f"- Медианная сумма заявки: {format_money(overview['median_amount'])}",
        f"- 99-й перцентиль суммы: {format_money(overview['p99_amount'])}",
        f"- Число крупных заявок (>= P99): {overview['large_items_count_at_or_above_p99']}",
        "",
        "## Качество данных",
        "",
        f"- Потенциальные дубликаты по `id`: {quality['duplicate_metrics'].get('id', 'n/a')}",
        f"- Потенциальные дубликаты по `registrator_guid`: {quality['duplicate_metrics'].get('registrator_guid', 'n/a')}",
        f"- Потенциальные дубликаты по номеру заявки: {quality['duplicate_metrics'].get('bit_zayavka_na_rashodovanie_sredstv_nomer', 'n/a')}",
        "",
        "### Колонки с наибольшей долей пропусков",
        "",
        render_table(summary["quality"]["top_missing_columns"]),
        "",
        "### Статусы",
        "",
        render_table(summary["status_breakdown"][:TOP_N]),
        "",
        "### Топ статьи затрат",
        "",
        render_table(summary["top_categories"]),
        "",
        "### Топ контрагенты",
        "",
        render_table(summary["top_vendors"]),
        "",
        "### Топ организации",
        "",
        render_table(summary["top_organizations"]),
        "",
        "### Топ подразделения",
        "",
        render_table(summary["top_departments"]),
        "",
        "### Помесячная динамика",
        "",
        render_table(summary["monthly_trend"]),
        "",
        "### Крупнейшие заявки",
        "",
        render_table(summary["top_transactions"]),
        "",
    ]
    return "\n".join(lines)


def render_table(records: list[dict[str, object]]) -> str:
    if not records:
        return "_Нет данных_"

    headers = list(records[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for record in records:
        values = []
        for header in headers:
            value = record.get(header, "")
            if isinstance(value, float):
                if "share" in header:
                    values.append(f"{value:.2%}")
                else:
                    values.append(f"{value:,.2f}".replace(",", " "))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    records = frame.copy()
    for column in records.columns:
        if pd.api.types.is_datetime64_any_dtype(records[column]):
            records[column] = records[column].dt.strftime("%Y-%m-%d")
    return records.where(records.notna(), None).to_dict(orient="records")


def format_money(value: float) -> str:
    return f"{value:,.2f} руб.".replace(",", " ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    df = load_payments_csv(args.input)
    summary = build_summary(df)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "uploaded_csv_analysis.json"
    md_path = args.output_dir / "uploaded_csv_analysis.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(summary, args.input), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
