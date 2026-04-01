"""HTML dashboard renderer using Jinja2, Plotly.js, and vanilla JS."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from it_spend_dashboard.dashboard.payload_builder import build_dashboard_payload


def render_dashboard_html(
    dashboard_payload: dict[str, Any],
    *,
    api_base_url: str = "/api/dashboard",
    template_dir: Path | None = None,
) -> str:
    """Render dashboard HTML from an already-built summary payload."""
    base_dir = Path(__file__).resolve().parents[3]
    templates = template_dir or (base_dir / "src" / "it_spend_dashboard" / "templates")
    assets_dir = base_dir / "src" / "it_spend_dashboard" / "dashboard" / "assets"

    environment = Environment(loader=FileSystemLoader(str(templates)), autoescape=select_autoescape(["html", "xml"]))
    template = environment.get_template("dashboard.html.j2")
    return template.render(
        title=dashboard_payload["metadata"]["title"],
        metadata=dashboard_payload["metadata"],
        dashboard_payload=dashboard_payload,
        dashboard_api_base_url=api_base_url,
        inline_css=(assets_dir / "styles.css").read_text(encoding="utf-8"),
        inline_js=(assets_dir / "app.js").read_text(encoding="utf-8"),
    )


def build_dashboard_html(payments_fact, *, template_dir: Path | None = None, output_path: Path | None = None) -> Path:
    """Render a compact dashboard HTML file that expects backend API support."""
    base_dir = Path(__file__).resolve().parents[3]
    target = output_path or (base_dir / "data" / "export" / "dashboard.html")
    payload = build_dashboard_payload(payments_fact)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_dashboard_html(payload, api_base_url="/api/dashboard", template_dir=template_dir),
        encoding="utf-8",
    )
    return target
