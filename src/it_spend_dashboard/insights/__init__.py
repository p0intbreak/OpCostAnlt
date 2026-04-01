"""Insights package for narrative findings and anomaly checks."""

from it_spend_dashboard.insights.generators import (
    anomaly_candidates,
    large_unpaid_items,
    status_bottlenecks,
    top_spend_categories,
    uncategorized_share,
    vendor_concentration,
    yoy_growth_categories,
)
from it_spend_dashboard.insights.narratives import build_management_narratives
from it_spend_dashboard.insights.pipeline import run_insights_pipeline

__all__ = [
    "anomaly_candidates",
    "build_management_narratives",
    "large_unpaid_items",
    "run_insights_pipeline",
    "status_bottlenecks",
    "top_spend_categories",
    "uncategorized_share",
    "vendor_concentration",
    "yoy_growth_categories",
]
