# IT Spend Dashboard

Production-style Python project for generating an analytical HTML dashboard on top of 1C CSV exports with IT department operating expenses.

## Stack

- Python 3.11+
- pandas
- pyarrow
- Jinja2
- pydantic

## Repository Structure

```text
data/
  raw/         # input CSV exports from 1C
  interim/     # intermediate cleaned datasets
  processed/   # curated analytical datasets
  export/      # rendered dashboard and exports
config/        # pipeline and mapping configs
docs/          # project documentation
notebooks/     # research and ad hoc analysis
scripts/       # entrypoints for pipeline and dashboard build
tests/         # automated tests
src/it_spend_dashboard/
  ingestion/       # reading raw 1C exports
  cleaning/        # standardization and quality checks
  classification/  # cost center and category mapping
  modeling/        # aggregated marts and KPI logic
  insights/        # analytical narratives and diagnostics
  dashboard/       # HTML rendering layer
  utils/           # shared helpers and schemas
```

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
make install
```

3. Put source 1C CSV files into `data/raw/`.
4. Run the analytical pipeline:

```bash
make run-pipeline
```

5. Build the HTML dashboard:

```bash
make build-dashboard
```

6. Run tests:

```bash
make test
```

## Current State

This repository is scaffolded with placeholder modules, scripts, and tests. The structure is ready for implementation of:

- ingestion from 1C CSV exports
- data cleaning and normalization
- spend classification
- analytical marts and KPIs
- insight generation
- Jinja2-based HTML dashboard rendering

## Definition of Done

The project is considered done when all of the following are true:

- CSV is read without manual pre-editing.
- Data for 2025 and 2026 is correctly separated and compared.
- Expenses are classified into L1/L2/L3 categories.
- A classification coverage report is available.
- A single HTML dashboard file is generated.
- All charts are clickable.
- Drill-down opens detailed rows.
- Automatic insights are generated.
- Aggregate totals reconcile with the fact table.
