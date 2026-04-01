"""Data quality checks and QA reporting for the analytics pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_FACT_FIELDS = [
    "payment_id",
    "period_date",
    "year",
    "amount",
    "status_group",
    "vendor_name",
    "organization_name",
    "l1_category",
    "classification_confidence",
]
ALLOWED_YEARS = {2025, 2026}


@dataclass(frozen=True)
class QACheckResult:
    """Result of a single QA check."""

    check_id: str
    passed: bool
    severity: str
    metric: float | int | str
    threshold: float | int | str
    details: dict[str, Any]


def check_required_fields_not_catastrophically_null(
    dataframe: pd.DataFrame,
    required_fields: list[str] | None = None,
    *,
    max_null_share: float = 0.2,
) -> QACheckResult:
    """Ensure required fields do not have catastrophic null rates."""
    fields = required_fields or REQUIRED_FACT_FIELDS
    null_shares: dict[str, float] = {}
    catastrophic_fields: list[str] = []
    for field in fields:
        if field not in dataframe.columns:
            null_shares[field] = 1.0
            catastrophic_fields.append(field)
            continue
        share = float(dataframe[field].isna().mean())
        null_shares[field] = share
        if share > max_null_share:
            catastrophic_fields.append(field)
    return QACheckResult(
        check_id="required_fields_nulls",
        passed=not catastrophic_fields,
        severity="critical" if catastrophic_fields else "info",
        metric=len(catastrophic_fields),
        threshold=max_null_share,
        details={"null_shares": null_shares, "catastrophic_fields": catastrophic_fields},
    )


def check_amounts_parsed(
    dataframe: pd.DataFrame,
    *,
    amount_column: str = "amount",
    raw_amount_column: str | None = None,
    min_parse_rate: float = 0.99,
) -> QACheckResult:
    """Check that amounts are numeric and parseable."""
    if amount_column not in dataframe.columns:
        return QACheckResult(
            check_id="amounts_parsed",
            passed=False,
            severity="critical",
            metric=0.0,
            threshold=min_parse_rate,
            details={"error": f"Missing amount column '{amount_column}'."},
        )

    numeric = pd.to_numeric(dataframe[amount_column], errors="coerce")
    if raw_amount_column and raw_amount_column in dataframe.columns:
        raw_present = dataframe[raw_amount_column].notna() & (dataframe[raw_amount_column].astype("string").str.strip() != "")
        parse_rate = float(numeric[raw_present].notna().mean()) if raw_present.any() else 1.0
    else:
        parse_rate = float(numeric.notna().mean())
    return QACheckResult(
        check_id="amounts_parsed",
        passed=parse_rate >= min_parse_rate,
        severity="critical" if parse_rate < min_parse_rate else "info",
        metric=round(parse_rate, 4),
        threshold=min_parse_rate,
        details={"non_numeric_rows": int(numeric.isna().sum())},
    )


def check_year_bounds(
    dataframe: pd.DataFrame,
    *,
    allowed_years: set[int] | None = None,
) -> QACheckResult:
    """Validate that years are limited to allowed years or clearly flagged."""
    allowed = allowed_years or ALLOWED_YEARS
    available_years = set(dataframe["year"].dropna().astype(int).tolist()) if "year" in dataframe.columns else set()
    unexpected = sorted(year for year in available_years if year not in allowed)
    return QACheckResult(
        check_id="year_bounds",
        passed=not unexpected,
        severity="warning" if unexpected else "info",
        metric=len(unexpected),
        threshold=0,
        details={"available_years": sorted(available_years), "unexpected_years": unexpected},
    )


def check_status_mapping_coverage(
    dataframe: pd.DataFrame,
    *,
    raw_column: str = "status_raw",
    mapped_column: str = "status_group",
    min_coverage: float = 0.95,
) -> QACheckResult:
    """Measure status mapping coverage."""
    if mapped_column not in dataframe.columns:
        return QACheckResult(
            check_id="status_mapping_coverage",
            passed=False,
            severity="critical",
            metric=0.0,
            threshold=min_coverage,
            details={"error": f"Missing mapped status column '{mapped_column}'."},
        )

    mapped = dataframe[mapped_column].astype("string").fillna("")
    raw = dataframe[raw_column].astype("string").fillna("") if raw_column in dataframe.columns else pd.Series([""] * len(dataframe))
    eligible = raw.str.strip() != ""
    covered = eligible & ~mapped.isin(["", "other"])
    coverage = float(covered.sum() / eligible.sum()) if eligible.any() else 1.0
    return QACheckResult(
        check_id="status_mapping_coverage",
        passed=coverage >= min_coverage,
        severity="warning" if coverage < min_coverage else "info",
        metric=round(coverage, 4),
        threshold=min_coverage,
        details={"eligible_rows": int(eligible.sum()), "covered_rows": int(covered.sum())},
    )


def check_classification_coverage(
    dataframe: pd.DataFrame,
    *,
    min_coverage: float = 0.8,
) -> QACheckResult:
    """Build classification coverage and confidence distribution report."""
    classified = ~dataframe["l1_category"].astype("string").fillna("other_it").isin(["", "other_it"])
    coverage = float(classified.mean()) if len(dataframe) else 0.0
    confidence_distribution = (
        dataframe["classification_confidence"]
        .astype("string")
        .fillna("unclassified")
        .value_counts(normalize=True)
        .sort_index()
        .round(4)
        .to_dict()
    )
    return QACheckResult(
        check_id="classification_coverage",
        passed=coverage >= min_coverage,
        severity="warning" if coverage < min_coverage else "info",
        metric=round(coverage, 4),
        threshold=min_coverage,
        details={"confidence_distribution": confidence_distribution},
    )


def build_qa_report(
    dataframe: pd.DataFrame,
    *,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run all QA checks and optionally persist the report as JSON."""
    checks = [
        check_required_fields_not_catastrophically_null(dataframe),
        check_amounts_parsed(dataframe),
        check_year_bounds(dataframe),
        check_status_mapping_coverage(dataframe),
        check_classification_coverage(dataframe),
    ]
    report = {
        "summary": {
            "total_checks": len(checks),
            "passed_checks": sum(1 for check in checks if check.passed),
            "failed_checks": sum(1 for check in checks if not check.passed),
        },
        "checks": [asdict(check) for check in checks],
        "known_limitations": [
            "Локальные тесты и прогон CLI не подтверждены рантаймом, так как в текущей среде недоступен рабочий python.exe.",
            "Rule-based классификация зависит от полноты YAML-правил и может отправлять нетипичные записи в review queue.",
            "Клиентский drill-down в HTML рассчитан на умеренный объем detail rows; для очень больших выгрузок потребуется оптимизация фронта.",
        ],
        "todo": [
            "Добавить golden-data integration test для полного run-pipeline на реалистичном CSV.",
            "Добавить schema versioning для dashboard payload и миграции фронта.",
            "Добавить QA-порог по качеству классификации на уровне L2/L3, а не только L1 coverage.",
        ],
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

