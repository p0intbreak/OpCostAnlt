"""Pipeline entrypoint for transforming raw 1C CSV exports into analytical datasets."""

from it_spend_dashboard.cleaning.pipeline import run_cleaning_pipeline
from it_spend_dashboard.classification.pipeline import run_classification_pipeline
from it_spend_dashboard.ingestion.pipeline import run_ingestion_pipeline
from it_spend_dashboard.insights.pipeline import run_insights_pipeline
from it_spend_dashboard.modeling.pipeline import run_modeling_pipeline


def main() -> None:
    """Run the end-to-end data preparation pipeline."""
    dataset = run_ingestion_pipeline()
    cleaned = run_cleaning_pipeline(dataset)
    classified = run_classification_pipeline(cleaned)
    modeled = run_modeling_pipeline(classified)
    run_insights_pipeline(modeled)


if __name__ == "__main__":
    main()

