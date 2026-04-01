"""Narrative assembly for top management insights in the dashboard UI."""

from __future__ import annotations

import pandas as pd

from it_spend_dashboard.insights.generators import (
    Insight,
    anomaly_candidates,
    large_unpaid_items,
    status_bottlenecks,
    top_spend_categories,
    uncategorized_share,
    vendor_concentration,
    yoy_growth_categories,
)

SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def build_management_narratives(payments_fact: pd.DataFrame, limit: int = 5) -> list[Insight]:
    """Build and rank the top management insights for the dashboard UI."""
    insights = [
        top_spend_categories(payments_fact),
        yoy_growth_categories(payments_fact),
        status_bottlenecks(payments_fact),
        vendor_concentration(payments_fact),
        large_unpaid_items(payments_fact),
        uncategorized_share(payments_fact),
        anomaly_candidates(payments_fact),
    ]
    ranked = sorted(insights, key=_sort_key)
    return ranked[:limit]


def _sort_key(insight: Insight) -> tuple[int, str]:
    """Sort insights by severity and title for deterministic output."""
    return (SEVERITY_RANK.get(insight["severity"], 99), insight["title"])
