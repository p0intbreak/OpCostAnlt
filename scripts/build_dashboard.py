"""Dashboard build entrypoint for rendering the analytical HTML report."""

from it_spend_dashboard.dashboard.builder import build_dashboard


def main() -> None:
    """Render the dashboard into the export directory."""
    build_dashboard()


if __name__ == "__main__":
    main()

