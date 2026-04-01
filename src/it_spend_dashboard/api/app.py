"""FastAPI app for serving the dashboard summary, detail rows, and audit trail."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from it_spend_dashboard.api.repository import DashboardRepository
from it_spend_dashboard.dashboard.html_builder import render_dashboard_html


def create_app(project_root: Path | None = None) -> FastAPI:
    """Create the FastAPI application."""
    root = (project_root or Path.cwd()).resolve()
    repository = DashboardRepository(root)
    app = FastAPI(title="IT Spend Dashboard API")

    @app.get("/", response_class=HTMLResponse)
    def dashboard_page() -> str:
        summary = repository.get_summary_payload()
        return render_dashboard_html(summary, api_base_url="/api/dashboard")

    @app.get("/api/dashboard/summary")
    def dashboard_summary() -> dict:
        return repository.get_summary_payload()

    @app.get("/api/dashboard/vendor-drilldown")
    def dashboard_vendor_drilldown(
        year: str = "",
        status_group: str = "",
        l1_category_id: str = "",
        l2_category_id: str = "",
        l3_category_id: str = "",
        organization_id: str = "",
        classification_confidence: str = "",
        selected_vendor_id: str = "",
        selected_month: str = "",
    ) -> dict:
        return repository.get_vendor_drilldown(
            year=year,
            status_group=status_group,
            l1_category_id=l1_category_id,
            l2_category_id=l2_category_id,
            l3_category_id=l3_category_id,
            organization_id=organization_id,
            classification_confidence=classification_confidence,
            selected_vendor_id=selected_vendor_id,
            selected_month=selected_month,
        )

    @app.get("/api/dashboard/details")
    def dashboard_details(
        year: str = "",
        month: str = "",
        status_group: str = "",
        l1_category_id: str = "",
        l2_category_id: str = "",
        l3_category_id: str = "",
        vendor_id: str = "",
        organization_id: str = "",
        classification_confidence: str = "",
        search: str = "",
        sort_key: str = Query(default="amount"),
        sort_direction: str = Query(default="desc"),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=500),
    ) -> dict:
        return repository.list_details(
            year=year,
            month=month,
            status_group=status_group,
            l1_category_id=l1_category_id,
            l2_category_id=l2_category_id,
            l3_category_id=l3_category_id,
            vendor_id=vendor_id,
            organization_id=organization_id,
            classification_confidence=classification_confidence,
            search=search,
            sort_key=sort_key,
            sort_direction=sort_direction,
            page=page,
            page_size=page_size,
        )

    @app.get("/api/dashboard/rows/{detail_row_id}")
    def dashboard_row(detail_row_id: str) -> dict:
        try:
            return repository.get_row_details(detail_row_id)
        except (KeyError, ValueError):
            raise HTTPException(status_code=404, detail="Row not found") from None

    @app.get("/api/dashboard/export.csv", response_class=PlainTextResponse)
    def dashboard_export_csv(
        year: str = "",
        month: str = "",
        status_group: str = "",
        l1_category_id: str = "",
        l2_category_id: str = "",
        l3_category_id: str = "",
        vendor_id: str = "",
        organization_id: str = "",
        classification_confidence: str = "",
        search: str = "",
        sort_key: str = Query(default="amount"),
        sort_direction: str = Query(default="desc"),
    ) -> PlainTextResponse:
        csv_text = repository.export_details_csv(
            year=year,
            month=month,
            status_group=status_group,
            l1_category_id=l1_category_id,
            l2_category_id=l2_category_id,
            l3_category_id=l3_category_id,
            vendor_id=vendor_id,
            organization_id=organization_id,
            classification_confidence=classification_confidence,
            search=search,
            sort_key=sort_key,
            sort_direction=sort_direction,
        )
        headers = {"Content-Disposition": 'attachment; filename="dashboard_selection.csv"'}
        return PlainTextResponse(csv_text, headers=headers, media_type="text/csv; charset=utf-8")

    return app
