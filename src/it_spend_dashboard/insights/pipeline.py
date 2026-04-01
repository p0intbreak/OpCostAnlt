"""Insight generation pipeline for modeled IT expense data."""

from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from it_spend_dashboard.insights.narratives import build_management_narratives


def run_insights_pipeline(dataframe: pd.DataFrame, export_dir: Path | None = None) -> list[dict[str, object]]:
    """Generate management insights from the modeled payments fact and persist them."""
    base_dir = Path(__file__).resolve().parents[3]
    target_dir = export_dir or (base_dir / "data" / "export")
    target_dir.mkdir(parents=True, exist_ok=True)

    insights = build_management_narratives(dataframe, limit=5)
    (target_dir / "management_insights.json").write_text(
        json.dumps(insights, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return insights
