from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


STRING_COLUMNS = [
    "registrator_status_name",
    "bit_stati_oborotov_naimenovanie",
    "kontragenti_naimenovanie",
    "organizacii_naimenovanie",
    "dogovori_kontragentov_nomer",
    "bit_zayavka_na_rashodovanie_sredstv_nomer",
    "registrator_guid",
    "vid_dvizheniya",
    "podrazdeleniya_naimenovanie",
    "proekti_naimenovanie",
]

DATE_COLUMNS = [
    "period",
    "quarter_period",
    "bit_zayavka_na_rashodovanie_sredstv_data",
    "bit_platezhnaya_poziciya_data",
    "registrator_status_dttm",
]

BUSINESS_SIGNATURE = [
    "period",
    "summa",
    "bit_stati_oborotov_naimenovanie",
    "organizacii_naimenovanie",
    "dogovori_kontragentov_nomer",
    "kontragenti_naimenovanie",
    "registrator_status_name",
]


def _normalize_strings(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in STRING_COLUMNS:
        if col in out.columns:
            out[col] = out[col].astype("string").str.strip().fillna("")
    return out


def _normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in DATE_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")
    return out


def clean_expense_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    cleaned = _normalize_dates(_normalize_strings(df))
    initial_rows = len(cleaned)

    cleaned = cleaned[cleaned["vid_dvizheniya"].eq("Expense")].copy()
    after_expense_rows = len(cleaned)

    cleaned = cleaned[cleaned["summa"].notna()].copy()
    cleaned = cleaned[cleaned["period"].notna()].copy()
    after_required_rows = len(cleaned)

    exact_duplicates = int(cleaned.duplicated(keep=False).sum())
    cleaned = cleaned.drop_duplicates().copy()
    after_exact_rows = len(cleaned)

    cleaned["dup_registrator_line_count"] = cleaned.groupby(["registrator_guid", "nomer_stroki"])["id"].transform("size")
    cleaned["dup_business_signature_count"] = cleaned.groupby(BUSINESS_SIGNATURE)["id"].transform("size")
    cleaned["has_request_number"] = cleaned["bit_zayavka_na_rashodovanie_sredstv_nomer"].ne("")
    cleaned["is_business_duplicate"] = cleaned["dup_business_signature_count"].gt(1)
    cleaned["is_line_duplicate"] = cleaned["dup_registrator_line_count"].gt(1)

    quality = {
        "initial_rows": int(initial_rows),
        "after_expense_filter_rows": int(after_expense_rows),
        "after_required_fields_rows": int(after_required_rows),
        "after_exact_dedup_rows": int(after_exact_rows),
        "rows_removed_by_exact_dedup": int(after_required_rows - after_exact_rows),
        "exact_duplicate_rows_detected": exact_duplicates,
        "business_duplicate_rows": int(cleaned["is_business_duplicate"].sum()),
        "line_duplicate_rows": int(cleaned["is_line_duplicate"].sum()),
        "sum_total": round(float(cleaned["summa"].sum()), 2),
    }
    return cleaned, quality


def build_conservative_dataset(df: pd.DataFrame) -> pd.DataFrame:
    conservative = df.sort_values(["period", "summa", "id"]).drop_duplicates(subset=BUSINESS_SIGNATURE, keep="first").copy()
    conservative["dup_registrator_line_count"] = conservative.groupby(["registrator_guid", "nomer_stroki"])["id"].transform("size")
    conservative["dup_business_signature_count"] = conservative.groupby(BUSINESS_SIGNATURE)["id"].transform("size")
    conservative["has_request_number"] = conservative["bit_zayavka_na_rashodovanie_sredstv_nomer"].ne("")
    conservative["is_business_duplicate"] = conservative["dup_business_signature_count"].gt(1)
    conservative["is_line_duplicate"] = conservative["dup_registrator_line_count"].gt(1)
    return conservative


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    feat = df.copy()
    feat["year"] = feat["period"].dt.year.astype("Int64")
    feat["month"] = feat["period"].dt.month.astype("Int64")
    feat["quarter"] = feat["period"].dt.quarter.astype("Int64")
    feat["day"] = feat["period"].dt.day.astype("Int64")
    feat["year_month"] = feat["period"].dt.strftime("%Y-%m")
    feat["weekofyear"] = feat["period"].dt.isocalendar().week.astype("Int64")
    feat["month_start"] = feat["period"].dt.to_period("M").dt.to_timestamp()
    feat["amount_log1p"] = np.log1p(feat["summa"].clip(lower=0))
    feat["amount_rank_pct"] = feat["summa"].rank(method="average", pct=True)
    feat["is_large_p95"] = feat["amount_rank_pct"].ge(0.95)
    feat["is_large_p99"] = feat["amount_rank_pct"].ge(0.99)

    for group_col, prefix in [
        ("kontragenti_naimenovanie", "vendor"),
        ("bit_stati_oborotov_naimenovanie", "article"),
        ("organizacii_naimenovanie", "org"),
        ("dogovori_kontragentov_nomer", "contract"),
    ]:
        feat[f"{prefix}_rows"] = feat.groupby(group_col)["id"].transform("size")
        feat[f"{prefix}_total_amount"] = feat.groupby(group_col)["summa"].transform("sum")
        feat[f"{prefix}_median_amount"] = feat.groupby(group_col)["summa"].transform("median")
        feat[f"{prefix}_share_of_total"] = feat[f"{prefix}_total_amount"] / feat["summa"].sum()

    feat["vendor_month_total_amount"] = feat.groupby(["kontragenti_naimenovanie", "year_month"])["summa"].transform("sum")
    feat["article_month_total_amount"] = feat.groupby(["bit_stati_oborotov_naimenovanie", "year_month"])["summa"].transform("sum")
    feat["amount_share_of_vendor_month"] = feat["summa"] / feat["vendor_month_total_amount"].replace(0, np.nan)
    feat["amount_share_of_contract"] = feat["summa"] / feat["contract_total_amount"].replace(0, np.nan)

    article_mean = feat.groupby("bit_stati_oborotov_naimenovanie")["summa"].transform("mean")
    article_std = feat.groupby("bit_stati_oborotov_naimenovanie")["summa"].transform("std").replace(0, np.nan)
    feat["article_zscore"] = ((feat["summa"] - article_mean) / article_std).fillna(0.0)

    article_median = feat.groupby("bit_stati_oborotov_naimenovanie")["summa"].transform("median")
    abs_dev = (feat["summa"] - article_median).abs()
    article_mad = abs_dev.groupby(feat["bit_stati_oborotov_naimenovanie"]).transform("median").replace(0, np.nan)
    feat["article_robust_zscore"] = (0.6745 * (feat["summa"] - article_median) / article_mad).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    feat["is_article_anomaly"] = feat["article_robust_zscore"].abs().ge(3.5)
    return feat


def _format_money(value: float) -> str:
    return f"{value:,.2f} руб.".replace(",", " ")


def _records_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_Нет данных_"
    show = frame.copy()
    for col in show.columns:
        if pd.api.types.is_float_dtype(show[col]):
            if "share" in col:
                show[col] = (show[col] * 100).round(2).astype(str) + "%"
            else:
                show[col] = show[col].round(2)
    header = "| " + " | ".join(map(str, show.columns)) + " |"
    sep = "| " + " | ".join(["---"] * len(show.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in show.itertuples(index=False, name=None)]
    return "\n".join([header, sep, *rows])


def build_report(
    cleaned: pd.DataFrame,
    conservative: pd.DataFrame,
    features: pd.DataFrame,
    quality: dict[str, object],
) -> str:
    top_articles = (
        cleaned.groupby("bit_stati_oborotov_naimenovanie")["summa"]
        .agg(rows="size", total="sum")
        .reset_index()
        .sort_values("total", ascending=False)
        .head(10)
    )
    top_articles["share_of_total"] = top_articles["total"] / top_articles["total"].sum()

    top_vendors = (
        cleaned.groupby("kontragenti_naimenovanie")["summa"]
        .agg(rows="size", total="sum")
        .reset_index()
        .sort_values("total", ascending=False)
        .head(10)
    )
    top_vendors["share_of_total"] = top_vendors["total"] / cleaned["summa"].sum()

    monthly_source = cleaned.assign(year_month=cleaned["period"].dt.strftime("%Y-%m"))
    monthly = (
        monthly_source.groupby("year_month")["summa"]
        .agg(rows="size", total="sum")
        .reset_index()
        .sort_values("year_month")
    )
    monthly["share_of_total"] = monthly["total"] / cleaned["summa"].sum()

    duplicate_vendors = (
        cleaned.groupby("kontragenti_naimenovanie")
        .agg(
            rows=("id", "size"),
            total=("summa", "sum"),
            business_dup_rows=("is_business_duplicate", "sum"),
        )
        .reset_index()
    )
    duplicate_vendors["business_dup_share_rows"] = duplicate_vendors["business_dup_rows"] / duplicate_vendors["rows"].replace(0, np.nan)
    duplicate_vendors = duplicate_vendors.sort_values(["business_dup_rows", "total"], ascending=[False, False]).head(15)

    anomalies = (
        features.loc[features["is_article_anomaly"], [
            "period",
            "summa",
            "bit_stati_oborotov_naimenovanie",
            "kontragenti_naimenovanie",
            "organizacii_naimenovanie",
            "dogovori_kontragentov_nomer",
            "article_robust_zscore",
        ]]
        .sort_values(["article_robust_zscore", "summa"], ascending=[False, False])
        .head(20)
    )

    abc = (
        cleaned.groupby("kontragenti_naimenovanie")["summa"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    abc["cum_share"] = abc["summa"].cumsum() / abc["summa"].sum()
    abc["abc_class"] = np.select(
        [abc["cum_share"].le(0.8), abc["cum_share"].le(0.95)],
        ["A", "B"],
        default="C",
    )
    abc_counts = abc["abc_class"].value_counts().sort_index().rename_axis("class").reset_index(name="vendors")

    lines = [
        "# Classical DS Workflow For Expense Dataset",
        "",
        "## 1. Cleaning",
        "",
        f"- Initial rows: {quality['initial_rows']}",
        f"- Rows after `Expense` filter: {quality['after_expense_filter_rows']}",
        f"- Rows after removing missing critical fields: {quality['after_required_fields_rows']}",
        f"- Exact duplicate rows removed: {quality['rows_removed_by_exact_dedup']}",
        f"- Rows flagged as business duplicates: {quality['business_duplicate_rows']}",
        f"- Rows flagged as line duplicates: {quality['line_duplicate_rows']}",
        f"- Cleaned total amount: {_format_money(quality['sum_total'])}",
        f"- Conservative total amount after business-signature dedup: {_format_money(float(conservative['summa'].sum()))}",
        "",
        "## 2. Feature Engineering",
        "",
        "- Calendar features: `year`, `month`, `quarter`, `day`, `year_month`, `weekofyear`",
        "- Amount features: `amount_log1p`, percentile rank, `is_large_p95`, `is_large_p99`",
        "- Entity aggregates: vendor/article/org/contract totals, medians and shares",
        "- Concentration features: vendor-month totals and row share inside vendor-month / contract",
        "- Risk features: `dup_business_signature_count`, `article_zscore`, `article_robust_zscore`, anomaly flag",
        "",
        "## 3. EDA",
        "",
        "### Top Articles",
        "",
        _records_to_markdown(top_articles),
        "",
        "### Top Vendors",
        "",
        _records_to_markdown(top_vendors),
        "",
        "### Monthly Distribution",
        "",
        _records_to_markdown(monthly),
        "",
        "### Vendors With Highest Duplicate Pressure",
        "",
        _records_to_markdown(duplicate_vendors),
        "",
        "### Vendor ABC Segmentation",
        "",
        _records_to_markdown(abc_counts),
        "",
        "## 4. Anomaly Candidates",
        "",
        _records_to_markdown(anomalies),
        "",
        "## 5. Notes",
        "",
        "- `Expense` filter materially changes the interpretation versus the mixed `Receipt/Expense` dataset.",
        "- Conservative dedup should be treated as an upper-bound correction scenario, not as a guaranteed truth for every vendor.",
        "- Vendors with high `business_dup_share_rows` deserve manual audit before contract-level conclusions.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--processed-dir", required=True, type=Path)
    parser.add_argument("--export-dir", required=True, type=Path)
    args = parser.parse_args()

    raw = pd.read_csv(args.input, encoding="utf-8-sig")
    cleaned, quality = clean_expense_dataset(raw)
    conservative = build_conservative_dataset(cleaned)
    features = engineer_features(cleaned)

    args.processed_dir.mkdir(parents=True, exist_ok=True)
    args.export_dir.mkdir(parents=True, exist_ok=True)

    cleaned_path = args.processed_dir / "expense_ds_cleaned.parquet"
    conservative_path = args.processed_dir / "expense_ds_conservative.parquet"
    features_path = args.processed_dir / "expense_ds_features.parquet"
    quality_path = args.export_dir / "expense_ds_quality.json"
    report_path = args.export_dir / "expense_ds_report.md"

    cleaned.to_parquet(cleaned_path, index=False)
    conservative.to_parquet(conservative_path, index=False)
    features.to_parquet(features_path, index=False)
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(build_report(cleaned, conservative, features, quality), encoding="utf-8")

    print(json.dumps({
        "cleaned_path": str(cleaned_path),
        "conservative_path": str(conservative_path),
        "features_path": str(features_path),
        "quality_path": str(quality_path),
        "report_path": str(report_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
