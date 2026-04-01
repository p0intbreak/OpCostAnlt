"""Composable insight generators for dashboard narrative blocks."""

import pandas as pd


def summarize_total_spend(dataframe: pd.DataFrame) -> str:
    """Return a placeholder textual summary for total spend."""
    total = float(dataframe["amount"].sum()) if "amount" in dataframe.columns else 0.0
    return f"Total spend: {total:.2f}"

