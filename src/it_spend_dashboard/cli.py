"""Command-line interface for the IT spend analytics pipeline and backend dashboard."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

import pandas as pd
import uvicorn

from it_spend_dashboard.api.app import create_app
from it_spend_dashboard.classification.pipeline import run_classification_pipeline
from it_spend_dashboard.cleaning.pipeline import run_cleaning_pipeline
from it_spend_dashboard.dashboard.html_builder import build_dashboard_html
from it_spend_dashboard.dashboard.payload_builder import save_dashboard_payload
from it_spend_dashboard.ingestion.load_csv import build_dataframe_profile, load_payments_csv
from it_spend_dashboard.ingestion.pipeline import run_ingestion_pipeline
from it_spend_dashboard.insights.pipeline import run_insights_pipeline
from it_spend_dashboard.modeling.pipeline import run_modeling_pipeline
from it_spend_dashboard.qa.checks import build_qa_report

LOGGER = logging.getLogger("it_spend_dashboard.cli")


class CliError(RuntimeError):
    """Controlled CLI error with a user-friendly message."""


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)

    try:
        return args.handler(args)
    except CliError as exc:
        LOGGER.error("%s", exc)
        return 2
    except FileNotFoundError as exc:
        LOGGER.error("Файл не найден: %s", exc.filename or exc)
        return 2
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Неожиданная ошибка выполнения пайплайна: %s", exc)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level CLI parser."""
    parser = argparse.ArgumentParser(prog="python -m it_spend_dashboard.cli")
    parser.add_argument("--verbose", action="store_true", help="Подробный logging.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    profile_parser = subparsers.add_parser("profile-data", help="Профилировать входной CSV 1С.")
    profile_parser.add_argument("--input", required=True, type=Path, help="Путь до CSV файла.")
    profile_parser.set_defaults(handler=handle_profile_data)

    run_parser = subparsers.add_parser("run-pipeline", help="Запустить полный end-to-end пайплайн.")
    run_parser.add_argument("--input", required=True, type=Path, help="Путь до входного CSV файла.")
    run_parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Корень проекта с data/config.")
    run_parser.set_defaults(handler=handle_run_pipeline)

    build_parser_cmd = subparsers.add_parser("build-dashboard", help="Собрать compact dashboard_payload.json из facts.")
    build_parser_cmd.add_argument("--input", type=Path, help="Путь до payments_fact.parquet.")
    build_parser_cmd.add_argument("--output", type=Path, help="Путь до dashboard_payload.json.")
    build_parser_cmd.add_argument("--project-root", type=Path, default=Path.cwd(), help="Корень проекта с data/.")
    build_parser_cmd.set_defaults(handler=handle_build_dashboard)

    export_parser = subparsers.add_parser("export-html", help="Собрать HTML shell для backend-backed дашборда.")
    export_parser.add_argument("--input", type=Path, help="Путь до payments_fact.parquet.")
    export_parser.add_argument("--output", type=Path, help="Путь до dashboard.html.")
    export_parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Корень проекта с data/.")
    export_parser.set_defaults(handler=handle_export_html)

    serve_parser = subparsers.add_parser("serve-dashboard", help="Запустить FastAPI backend для дашборда.")
    serve_parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Корень проекта с data/.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host для uvicorn.")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port для uvicorn.")
    serve_parser.set_defaults(handler=handle_serve_dashboard)
    return parser


def configure_logging(*, verbose: bool) -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def handle_profile_data(args: argparse.Namespace) -> int:
    """Profile the raw CSV input and print a JSON summary."""
    input_path = _resolve_existing_path(args.input)
    LOGGER.info("Профилирование CSV: %s", input_path)
    dataframe = load_payments_csv(input_path)
    profile = build_dataframe_profile(dataframe)
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return 0


def handle_run_pipeline(args: argparse.Namespace) -> int:
    """Run the full pipeline from raw CSV to HTML export."""
    project_root = args.project_root.resolve()
    input_path = _resolve_existing_path(args.input)
    config_dir = project_root / "config"
    interim_dir = project_root / "data" / "interim"
    processed_dir = project_root / "data" / "processed"
    export_dir = project_root / "data" / "export"

    LOGGER.info("Старт пайплайна для файла: %s", input_path)
    LOGGER.info("Шаг 1/7: ingestion")
    ingested = run_ingestion_pipeline(csv_path=input_path, output_path=interim_dir / "payments_ingested.parquet")

    LOGGER.info("Шаг 2/7: cleaning")
    cleaned = run_cleaning_pipeline(ingested, output_path=interim_dir / "payments_clean.parquet", config_dir=config_dir)

    LOGGER.info("Шаг 3/7: classification")
    classified = run_classification_pipeline(cleaned, config_dir=config_dir)
    (interim_dir / "payments_classified.parquet").parent.mkdir(parents=True, exist_ok=True)
    classified.to_parquet(interim_dir / "payments_classified.parquet", index=False)

    LOGGER.info("Шаг 4/7: modeling")
    payments_fact = run_modeling_pipeline(classified, output_dir=processed_dir)

    LOGGER.info("Шаг 5/7: insights")
    insights = run_insights_pipeline(payments_fact, export_dir=export_dir)

    LOGGER.info("Шаг 6/7: payload building")
    payload_path = save_dashboard_payload(payments_fact, output_path=export_dir / "dashboard_payload.json", insights=insights)

    LOGGER.info("Шаг 7/7: html export")
    html_path = build_dashboard_html(payments_fact, output_path=export_dir / "dashboard.html")
    qa_report = build_qa_report(payments_fact, output_path=export_dir / "qa_report.json")

    LOGGER.info("Пайплайн завершен успешно.")
    LOGGER.info("Payload: %s", payload_path)
    LOGGER.info("HTML: %s", html_path)
    LOGGER.info("QA: passed=%s failed=%s", qa_report["summary"]["passed_checks"], qa_report["summary"]["failed_checks"])
    return 0


def handle_build_dashboard(args: argparse.Namespace) -> int:
    """Build the dashboard summary payload from processed facts."""
    project_root = args.project_root.resolve()
    fact_path = args.input.resolve() if args.input else project_root / "data" / "processed" / "payments_fact.parquet"
    output_path = args.output.resolve() if args.output else project_root / "data" / "export" / "dashboard_payload.json"
    _resolve_existing_path(fact_path)

    LOGGER.info("Сборка dashboard summary payload из %s", fact_path)
    payments_fact = pd.read_parquet(fact_path)
    insights = run_insights_pipeline(payments_fact, export_dir=output_path.parent)
    saved_path = save_dashboard_payload(payments_fact, output_path=output_path, insights=insights)
    LOGGER.info("Payload сохранен: %s", saved_path)
    return 0


def handle_export_html(args: argparse.Namespace) -> int:
    """Render the backend-backed HTML dashboard shell from processed facts."""
    project_root = args.project_root.resolve()
    fact_path = args.input.resolve() if args.input else project_root / "data" / "processed" / "payments_fact.parquet"
    output_path = args.output.resolve() if args.output else project_root / "data" / "export" / "dashboard.html"
    _resolve_existing_path(fact_path)

    LOGGER.info("Рендер HTML дашборда из %s", fact_path)
    payments_fact = pd.read_parquet(fact_path)
    saved_path = build_dashboard_html(payments_fact, output_path=output_path)
    LOGGER.info("HTML сохранен: %s", saved_path)
    return 0


def handle_serve_dashboard(args: argparse.Namespace) -> int:
    """Run the FastAPI backend for the dashboard."""
    project_root = args.project_root.resolve()
    app = create_app(project_root)
    LOGGER.info("Запуск backend дашборда: http://%s:%s", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def _resolve_existing_path(path: Path) -> Path:
    """Resolve a path and ensure it exists."""
    resolved = path.resolve()
    if not resolved.exists():
        raise CliError(f"Указанный путь не существует: {resolved}")
    return resolved


if __name__ == "__main__":
    sys.exit(main())
