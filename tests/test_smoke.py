"""Smoke tests for the project scaffold."""

from it_spend_dashboard.dashboard.builder import build_dashboard


def test_dashboard_builder_returns_output_path() -> None:
    """Verify the dashboard builder placeholder returns the target output path."""
    output_path = build_dashboard()
    assert output_path.name == "dashboard.html"
