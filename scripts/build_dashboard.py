"""Dashboard build entrypoint for rendering the analytical HTML report."""

import sys

from it_spend_dashboard.cli import main as cli_main


def main() -> int:
    """Render the dashboard into the export directory via the shared CLI."""
    return cli_main(["export-html"])


if __name__ == "__main__":
    sys.exit(main())
