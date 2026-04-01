"""Context builders for passing analytical data into templates."""

from typing import Any


def build_dashboard_context() -> dict[str, Any]:
    """Return a placeholder dashboard rendering context."""
    return {"title": "IT Spend Dashboard"}

