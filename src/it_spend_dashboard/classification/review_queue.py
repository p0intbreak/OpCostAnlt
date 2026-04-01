"""Helpers for assembling and exporting a manual review queue for weak classifications."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REVIEW_COLUMNS = [
    "raw_article",
    "raw_description",
    "raw_vendor",
    "suggested_l1",
    "suggested_l2",
    "suggested_l3",
    "confidence",
    "reason",
]


def build_review_queue(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return only low-confidence and unclassified rows in training-sample format."""
    if "classification_confidence" not in dataframe.columns:
        return pd.DataFrame(columns=REVIEW_COLUMNS)

    queue = dataframe[
        dataframe["classification_confidence"].isin(["low", "unclassified"])
    ].copy()
    export = pd.DataFrame(
        {
            "raw_article": _column_or_default(queue, "article_name", "bit_stati_oborotov_naimenovanie"),
            "raw_description": _column_or_default(queue, "naznachenie_platezha"),
            "raw_vendor": _column_or_default(queue, "vendor_name", "kontragenti_naimenovanie"),
            "suggested_l1": _column_or_default(queue, "l1_category"),
            "suggested_l2": _column_or_default(queue, "l2_category"),
            "suggested_l3": _column_or_default(queue, "l3_category"),
            "confidence": _column_or_default(queue, "classification_confidence"),
            "reason": _column_or_default(queue, "classification_reason"),
        }
    )
    return export.loc[:, REVIEW_COLUMNS]


def save_review_queue(dataframe: pd.DataFrame, output_path: Path) -> Path:
    """Persist the review queue as a CSV training sample."""
    queue = build_review_queue(dataframe)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    queue.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def _column_or_default(dataframe: pd.DataFrame, *candidates: str) -> pd.Series:
    """Return the first existing string column or an empty fallback series."""
    for column in candidates:
        if column in dataframe.columns:
            return dataframe[column].astype("string").fillna("")
    return pd.Series([""] * len(dataframe), index=dataframe.index, dtype="string")
