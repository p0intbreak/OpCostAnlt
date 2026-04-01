"""Dashboard builder for rendering a Jinja2-based HTML report."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def build_dashboard(
    template_dir: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """Render a placeholder HTML dashboard and return the output path."""
    base_dir = Path(__file__).resolve().parents[3]
    templates = template_dir or (base_dir / "src" / "it_spend_dashboard" / "templates")
    target = output_path or (base_dir / "data" / "export" / "dashboard.html")

    environment = Environment(
        loader=FileSystemLoader(str(templates)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = environment.get_template("dashboard.html.j2")
    target.write_text(
        template.render(title="IT Spend Dashboard", generated_at="placeholder"),
        encoding="utf-8",
    )
    return target

