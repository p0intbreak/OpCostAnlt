"""Pipeline entrypoint for transforming raw 1C CSV exports into analytical datasets."""

from pathlib import Path
import sys

from it_spend_dashboard.cli import main as cli_main


def main() -> int:
    """Run the end-to-end pipeline via the shared CLI."""
    default_input = Path("data/raw/payments.csv")
    return cli_main(["run-pipeline", "--input", str(default_input)])


if __name__ == "__main__":
    sys.exit(main())
