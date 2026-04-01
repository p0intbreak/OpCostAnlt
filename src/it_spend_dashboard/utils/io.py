"""Input and output helpers for project datasets and exports."""

from pathlib import Path


def ensure_directory(path: Path) -> Path:
    """Create a directory if needed and return its path."""
    path.mkdir(parents=True, exist_ok=True)
    return path

