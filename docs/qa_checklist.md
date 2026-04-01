# QA Checklist

## Data Checks

- Required fact fields do not have catastrophic null rates.
- Amount fields are parsed into numeric values without material loss.
- Reporting years are limited to 2025 and 2026, or unexpected years are explicitly flagged.
- Status mapping coverage remains above 95%.
- Classification coverage is monitored together with confidence distribution.

## Test Scope

- Unit tests for ingestion, cleaning, classification, modeling, payload, insights, CLI, and QA checks.
- Snapshot test for `dashboard_payload.json` with normalized timestamp.
- Smoke test for `dashboard.html` generation.

## Release Gate

- Run `make test`.
- Review `data/export/qa_report.json` or the in-memory QA report after pipeline execution.
- Inspect `management_insights.json`, `dashboard_payload.json`, and `dashboard.html`.
- Confirm low-confidence and uncategorized slices are acceptable for the reporting period.

## Known Limitations

- Local execution of tests and CLI is not confirmed in the current assistant runtime because `python.exe` is unavailable here.
- Rule-based classification quality depends on YAML coverage and may under-classify long-tail expense patterns.
- Frontend drill-down is fully client-side and may require optimization for very large detailed datasets.
- Snapshot coverage validates payload shape and representative content, not pixel-perfect HTML rendering.

## TODO

- Add an integration fixture with a realistic anonymized 1C export and expected processed artifacts.
- Add performance tests for large `detail_rows` payloads in the HTML dashboard.
- Add contract tests for backward-compatible payload schema evolution.
- Add QA thresholds for vendor concentration, anomaly rates, and insight completeness.

