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
        fact = pd.read_parquet(base_dir / "data" / "processed" / "payments_fact.parquet")
    return build_dashboard_html(fact, output_path=output_path)
