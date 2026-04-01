"""Business grain helpers for collapsing raw 1C lines into document and position entities."""

from __future__ import annotations

import hashlib

import pandas as pd


def add_grain_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Attach stable document, position, and source-line identifiers to a dataset."""
    enriched = dataframe.copy()
    enriched["payment_document_id"] = enriched.apply(_build_document_id, axis=1)
    enriched["payment_position_id"] = enriched.apply(_build_position_id, axis=1)
    enriched["payment_source_line_id"] = enriched.apply(_build_source_line_id, axis=1)
    return enriched


def collapse_to_position_grain(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Collapse exact duplicate source lines so the fact table grain is one payment position."""
    enriched = add_grain_columns(dataframe)
    counts = (
        enriched.groupby("payment_position_id", as_index=False)
        .agg(
            source_line_count=("payment_source_line_id", "size"),
            source_line_unique_count=("payment_source_line_id", "nunique"),
        )
    )
    representative = enriched.drop_duplicates(subset=["payment_position_id"], keep="first").copy()
    collapsed = representative.merge(counts, on="payment_position_id", how="left")
    collapsed["has_source_duplicates"] = collapsed["source_line_count"].fillna(1).astype(int) > 1
    return collapsed


def _build_document_id(row: pd.Series) -> str:
    """Build a stable document-level key."""
    for column in ("registrator_guid", "guid_link", "link"):
        value = _stringify(row.get(column, ""))
        if value:
            return _compose_id("doc", [value])
    return _compose_id("doc", [_stringify(row.get("registrator", "")), _stringify(row.get("period", ""))])


def _build_position_id(row: pd.Series) -> str:
    """Build a stable position-level key."""
    registrator_guid = _stringify(row.get("registrator_guid", ""))
    line_id = _stringify(row.get("id", ""))
    if registrator_guid and line_id:
        return _compose_id("pos", [registrator_guid, line_id])
    return _compose_id(
        "pos",
        [
            registrator_guid,
            line_id,
            _stringify(row.get("period", "")),
            _stringify(row.get("summa", "")),
            _stringify(row.get("bit_stati_oborotov_naimenovanie", "")),
            _stringify(row.get("kontragenti_naimenovanie", "")),
            _stringify(row.get("dogovori_kontragentov_naimenovanie", "")),
        ],
    )


def _build_source_line_id(row: pd.Series) -> str:
    """Build a source-line fingerprint over the full row contents."""
    parts = [f"{column}={_stringify(value)}" for column, value in row.items()]
    return _compose_id("src", parts)


def _compose_id(prefix: str, parts: list[str]) -> str:
    """Create a compact md5-based identifier."""
    payload = "|".join(parts)
    return f"{prefix}_{hashlib.md5(payload.encode('utf-8')).hexdigest()}"


def _stringify(value: object) -> str:
    """Convert nullable values into stable key fragments."""
    if pd.isna(value):
        return ""
    return str(value).strip()
