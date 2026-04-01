"""Dashboard builder for rendering a Jinja2-based HTML report."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from it_spend_dashboard.dashboard.html_builder import build_dashboard_html


def build_dashboard(payments_fact: pd.DataFrame | None = None, output_path: Path | None = None) -> Path:
    """Render the interactive dashboard and return the export path."""
    base_dir = Path(__file__).resolve().parents[3]
    fact = payments_fact
    if fact is None:
        default_fact_path = base_dir / "data" / "processed" / "payments_fact.parquet"
        if default_fact_path.exists():
            fact = pd.read_parquet(default_fact_path)
        else:
            fact = _empty_payments_fact()
    return build_dashboard_html(fact, output_path=output_path)


def _empty_payments_fact() -> pd.DataFrame:
    """Return an empty but schema-complete payments fact for smoke rendering."""
    return pd.DataFrame(
        columns=[
            "payment_id",
            "period_date",
            "year",
            "month",
            "quarter",
            "amount",
            "status_raw",
            "status_group",
            "article_name",
            "article_code",
            "vendor_name",
            "contract_name",
            "project_name",
            "department_name",
            "organization_name",
            "l1_category",
            "l2_category",
            "l3_category",
            "classification_confidence",
            "matched_rule_id",
            "matched_keywords",
            "matched_vendor_pattern",
            "matched_article_pattern",
            "classification_reason_human",
        ]
    )
