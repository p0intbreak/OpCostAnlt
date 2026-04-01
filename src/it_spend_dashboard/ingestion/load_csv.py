"""CSV loading utilities for raw 1C exports."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import pandas as pd

LOGGER = logging.getLogger(__name__)
DEFAULT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1251")


def detect_csv_separator(path: Path, sample_size: int = 4096) -> str | None:
    """Detect the delimiter from a small sample of a CSV file when possible."""
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:sample_size]
    if not sample.strip():
        return None

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t")
    except csv.Error:
        return None
    return str(dialect.delimiter)


def load_payments_csv(path: Path, separator: str | None = None) -> pd.DataFrame:
    """Read a 1C CSV export with safe encoding fallback and basic profiling logs."""
    resolved_separator = separator if separator is not None else detect_csv_separator(path)
    last_error: UnicodeDecodeError | None = None

    for encoding in DEFAULT_ENCODINGS:
        try:
            dataframe = pd.read_csv(
                path,
                sep=resolved_separator or None,
                engine="python",
                encoding=encoding,
            )
            _log_dataframe_profile(dataframe=dataframe, path=path, encoding=encoding, separator=resolved_separator)
            return dataframe
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to read CSV file: {path}")


def _log_dataframe_profile(
    dataframe: pd.DataFrame,
    path: Path,
    encoding: str,
    separator: str | None,
) -> None:
    """Log basic dataset profiling information for observability."""
    profile = build_dataframe_profile(dataframe)
    LOGGER.info(
        "Loaded CSV file '%s' with shape=%s encoding=%s separator=%s",
        path,
        dataframe.shape,
        encoding,
        separator or "auto",
    )
    LOGGER.info("CSV dtypes: %s", profile["dtypes"])
    LOGGER.info("CSV null_counts: %s", profile["null_counts"])


def build_dataframe_profile(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Build a compact profile summary for a DataFrame."""
    return {
        "shape": [int(dataframe.shape[0]), int(dataframe.shape[1])],
        "columns": [str(column) for column in dataframe.columns],
        "dtypes": {column: str(dtype) for column, dtype in dataframe.dtypes.items()},
        "null_counts": {column: int(count) for column, count in dataframe.isna().sum().to_dict().items()},
    }
