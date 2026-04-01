"""Pydantic schemas for validated records and dashboard payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpendRecord(BaseModel):
    """Validated spend record schema for a single expense transaction."""

    source_file: str = Field(default="placeholder.csv")
    operation_date: str = Field(default="2026-01-01")
    amount: float = Field(default=0.0)
    vendor: str = Field(default="UNKNOWN")


class DashboardMetadata(BaseModel):
    """Metadata section for the dashboard payload."""

    model_config = ConfigDict(extra="forbid")

    title: str
    generated_at: str
    currency: str
    detail_rows_count: int
    available_years: list[int]


class DashboardFilterOption(BaseModel):
    """Single filter option for the frontend UI."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str


class DashboardFilters(BaseModel):
    """Filter configuration for interactive frontend controls."""

    model_config = ConfigDict(extra="forbid")

    years: list[DashboardFilterOption]
    months: list[DashboardFilterOption]
    statuses: list[DashboardFilterOption]
    categories_l1: list[DashboardFilterOption]
    categories_l2: list[DashboardFilterOption]
    categories_l3: list[DashboardFilterOption]
    organizations: list[DashboardFilterOption]
    vendors: list[DashboardFilterOption]


class DashboardKpi(BaseModel):
    """Single KPI card payload."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    value: float | int | str


class DashboardYearComparisonRow(BaseModel):
    """Yearly comparison row for 2025 versus 2026."""

    model_config = ConfigDict(extra="forbid")

    year: int
    total_amount: float
    payments_count: int


class DashboardMonthlyTrendRow(BaseModel):
    """Monthly trend row payload."""

    model_config = ConfigDict(extra="forbid")

    year: int
    month: int
    year_month: str
    total_amount: float
    payments_count: int


class DashboardCategoryNode(BaseModel):
    """Hierarchical category node for drill-down navigation."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    level: str
    total_amount: float
    payments_count: int
    children: list["DashboardCategoryNode"] = Field(default_factory=list)


class DashboardStatusRow(BaseModel):
    """Status breakdown row payload."""

    model_config = ConfigDict(extra="forbid")

    status_id: str
    status_label: str
    total_amount: float
    payments_count: int


class DashboardEntityRow(BaseModel):
    """Vendor or organization aggregate row payload."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    total_amount: float
    payments_count: int


class DashboardInsight(BaseModel):
    """Validated insight payload for the dashboard UI."""

    model_config = ConfigDict(extra="forbid")

    title: str
    metric: str
    explanation: str
    severity: str
    supporting_filters: dict[str, Any]


class DashboardDetailRow(BaseModel):
    """Detail row payload used for frontend-only drill-downs."""

    model_config = ConfigDict(extra="forbid")

    payment_id: str
    period_date: str
    year: int | None = None
    month: int | None = None
    quarter: int | None = None
    amount: float
    status_group: str
    article_name: str
    article_code: str
    contract_name: str
    expense_subject: str
    vendor_id: str
    vendor_label: str
    organization_id: str
    organization_label: str
    project_name: str
    department_name: str
    l1_category_id: str
    l1_category_label: str
    l2_category_id: str
    l2_category_label: str
    l3_category_id: str
    l3_category_label: str
    classification_confidence: str
    matched_rule_id: str
    matched_keywords: str
    matched_vendor_pattern: str
    matched_article_pattern: str
    classification_reason_human: str


class DashboardPayload(BaseModel):
    """Validated top-level dashboard payload."""

    model_config = ConfigDict(extra="forbid")

    metadata: DashboardMetadata
    filters: DashboardFilters
    kpis: list[DashboardKpi]
    yearly_comparison: list[DashboardYearComparisonRow]
    monthly_trends: list[DashboardMonthlyTrendRow]
    categories_tree: list[DashboardCategoryNode]
    status_breakdown: list[DashboardStatusRow]
    vendors: list[DashboardEntityRow]
    organizations: list[DashboardEntityRow]
    insights: list[DashboardInsight]
    detail_rows: list[DashboardDetailRow]
    detail_row_index: dict[str, list[str]]
