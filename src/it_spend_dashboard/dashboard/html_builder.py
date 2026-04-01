"""Single-file HTML dashboard builder using Jinja2, Plotly.js, and vanilla JS."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from it_spend_dashboard.dashboard.payload_builder import build_dashboard_payload


def build_dashboard_html(payments_fact, *, template_dir: Path | None = None, output_path: Path | None = None) -> Path:
    """Render a single-file interactive HTML dashboard."""
    base_dir = Path(__file__).resolve().parents[3]
    templates = template_dir or (base_dir / "src" / "it_spend_dashboard" / "templates")
    assets_dir = base_dir / "src" / "it_spend_dashboard" / "dashboard" / "assets"
    target = output_path or (base_dir / "data" / "export" / "dashboard.html")

    environment = Environment(loader=FileSystemLoader(str(templates)), autoescape=select_autoescape(["html", "xml"]))
    template = environment.get_template("dashboard.html.j2")
    payload = build_dashboard_payload(payments_fact)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        template.render(
            title=payload["metadata"]["title"],
            metadata=payload["metadata"],
            dashboard_payload=payload,
            inline_css=(assets_dir / "styles.css").read_text(encoding="utf-8"),
            inline_js=(assets_dir / "app.js").read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    return target
