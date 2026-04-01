"""Context builders for passing analytical data into templates."""

from __future__ import annotations

from typing import Any

import pandas as pd

from it_spend_dashboard.dashboard.payload_builder import build_dashboard_payload


def build_dashboard_context(payments_fact: pd.DataFrame | None = None) -> dict[str, Any]:
    """Build template context with the serialized dashboard payload."""
    if payments_fact is None:
        return {"title": "IT Spend Dashboard", "dashboard_payload": {}}
    return {
        "title": "IT Spend Dashboard",
        "dashboard_payload": build_dashboard_payload(payments_fact),
    }
