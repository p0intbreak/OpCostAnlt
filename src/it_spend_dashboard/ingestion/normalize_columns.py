"""Column normalization utilities for 1C CSV exports."""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

CYRILLIC_TO_LATIN = str.maketrans(
    {
        "\u0430": "a",
        "\u0431": "b",
        "\u0432": "v",
        "\u0433": "g",
        "\u0434": "d",
        "\u0435": "e",
        "\u0451": "e",
        "\u0436": "zh",
        "\u0437": "z",
        "\u0438": "i",
        "\u0439": "i",
        "\u043a": "k",
        "\u043b": "l",
        "\u043c": "m",
        "\u043d": "n",
        "\u043e": "o",
        "\u043f": "p",
        "\u0440": "r",
        "\u0441": "s",
        "\u0442": "t",
        "\u0443": "u",
        "\u0444": "f",
        "\u0445": "h",
        "\u0446": "ts",
        "\u0447": "ch",
        "\u0448": "sh",
        "\u0449": "sch",
        "\u044a": "",
        "\u044b": "y",
        "\u044c": "",
        "\u044d": "e",
        "\u044e": "yu",
        "\u044f": "ya",
    }
)


def normalize_columns(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Normalize source column names into ASCII-safe snake_case aliases."""
    mapping: dict[str, str] = {}
    normalized_columns: list[str] = []
    seen_aliases: dict[str, int] = {}

    for original_name in dataframe.columns:
        alias = _to_ascii_snake_case(str(original_name))
        count = seen_aliases.get(alias, 0)
        unique_alias = alias if count == 0 else f"{alias}_{count}"
        seen_aliases[alias] = count + 1
        mapping[str(original_name)] = unique_alias
        normalized_columns.append(unique_alias)

    normalized = dataframe.copy()
    normalized.columns = normalized_columns
    normalized.attrs["column_mapping"] = mapping
    normalized.attrs["original_columns"] = {
        alias: original_name
        for original_name, alias in mapping.items()
    }
    return normalized, mapping


def _to_ascii_snake_case(value: str) -> str:
    """Convert a column name to an ASCII-safe snake_case alias."""
    transliterated = value.lower().translate(CYRILLIC_TO_LATIN)
    normalized = unicodedata.normalize("NFKD", transliterated)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    collapsed = re.sub(r"[^0-9a-zA-Z]+", "_", ascii_value).strip("_").lower()
    if not collapsed:
        return "column"
    if collapsed[0].isdigit():
        return f"column_{collapsed}"
    return collapsed
