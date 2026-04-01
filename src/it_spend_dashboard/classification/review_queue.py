"""Helpers for assembling a manual review queue for weak classifications."""

from __future__ import annotations

import pandas as pd

REVIEW_COLUMNS = [
    "bit_stati_oborotov_naimenovanie",
    "bit_stati_oborotov_kodifikator",
    "kontragenti_naimenovanie",
    "dogovori_kontragentov_naimenovanie",
    "proekti_naimenovanie",
    "podrazdeleniya_naimenovanie",
    "l1_category",
    "l2_category",
    "l3_category",
    "classification_reason",
    "classification_confidence",
]


def build_review_queue(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return only low-confidence and unclassified rows for manual review."""
    if "classification_confidence" not in dataframe.columns:
        return pd.DataFrame(columns=REVIEW_COLUMNS)

    queue = dataframe[
        dataframe["classification_confidence"].isin(["low", "unclassified"])
    ].copy()
    queue["review_reason"] = queue["classification_confidence"].map(
        {
            "low": "Low-confidence rule-based classification",
            "unclassified": "No matching classification rule",
        }
    )
    ordered_columns = [column for column in REVIEW_COLUMNS if column in queue.columns] + ["review_reason"]
    return queue.loc[:, ordered_columns]

