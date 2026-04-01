"""Pydantic schemas for validated project configuration and records."""

from pydantic import BaseModel, Field


class SpendRecord(BaseModel):
    """Validated spend record schema for a single expense transaction."""

    source_file: str = Field(default="placeholder.csv")
    operation_date: str = Field(default="2026-01-01")
    amount: float = Field(default=0.0)
    vendor: str = Field(default="UNKNOWN")

