"""InOut — Input / Output tools.

**In/Out** tool palette: reading, writing, browsing,
and generating data from external sources.

All methods are static — no hidden instance state.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

# Security: Pickle deserialization is an arbitrary code execution vector (CWE-502).
# Pickle support has been permanently removed. Use Parquet or Feather format instead.
class PickleRemovedError(ValueError):
    """Raised when a pickle file path is used.

    Pickle deserialization allows arbitrary code execution (CWE-502) and has
    been permanently removed from etlpipe for banking/enterprise compliance.
    Migrate to Parquet (``.parquet``) or Feather (``.feather``) format.
    """

    def __init__(self, path: str) -> None:
        super().__init__(
            f"Pickle format is permanently disabled for security (CWE-502): '{path}'. "
            "Migrate to Parquet or Feather format: "
            "InOut.output_data(df, 'file.parquet') / InOut.input_data('file.parquet')"
        )


# Mapping from file extension to pandas reader / writer pairs.
_READERS: dict[str, str] = {
    ".csv": "read_csv",
    ".tsv": "read_csv",
    ".xlsx": "read_excel",
    ".xls": "read_excel",
    ".json": "read_json",
    ".parquet": "read_parquet",
    ".feather": "read_feather",
    ".html": "read_html",
    ".sas7bdat": "read_sas",
    ".xpt": "read_sas",
    ".dta": "read_stata",
    ".sav": "read_spss",
}

_WRITERS: dict[str, str] = {
    ".csv": "to_csv",
    ".tsv": "to_csv",
    ".xlsx": "to_excel",
    ".xls": "to_excel",
    ".json": "to_json",
    ".parquet": "to_parquet",
    ".feather": "to_feather",
    ".html": "to_html",
    ".dta": "to_stata",
}

# Blocked formats — any path matching these extensions raises PickleRemovedError
_BLOCKED_EXTENSIONS: frozenset[str] = frozenset({".pkl", ".pickle"})


class InOut:
    """Etlpipe **In/Out** tool palette.

    Provides static methods for reading, writing, browsing, and creating
    DataFrames from various data sources.
    """

    # ------------------------------------------------------------------ #
    # Input Data
    # ------------------------------------------------------------------ #
    @staticmethod
    def input_data(path: str | Path, **kwargs: Any) -> pd.DataFrame:
        """Read data from a file into a DataFrame.

        The file format is auto-detected from the extension.  Any extra
        keyword arguments are forwarded to the underlying pandas reader.

        Args:
            path: Path to the data file.
            **kwargs: Passed through to the pandas reader function.

        Returns:
            A new ``DataFrame`` with the file contents.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is not supported.

        Example:
            >>> df = InOut.input_data("sales.csv")
            >>> df = InOut.input_data("report.xlsx", sheet_name="Q1")
        """
        ext = Path(str(path)).suffix.lower()
        if ext in _BLOCKED_EXTENSIONS:
            raise PickleRemovedError(str(path))
        from etlpipe._config import get_engine

        return get_engine().input_data(path, **kwargs)

    # ------------------------------------------------------------------ #
    # Output Data
    # ------------------------------------------------------------------ #
    @staticmethod
    def output_data(df: pd.DataFrame, path: str | Path, **kwargs: Any) -> None:
        """Write a DataFrame to a file.

        The file format is auto-detected from the extension.  Any extra
        keyword arguments are forwarded to the underlying pandas writer.

        Args:
            df: The DataFrame to write.
            path: Destination file path.
            **kwargs: Passed through to the pandas writer method.

        Raises:
            TypeError: If *df* is not a DataFrame.
            ValueError: If the file extension is not supported.

        Example:
            >>> InOut.output_data(df, "output.parquet")
            >>> InOut.output_data(df, "report.xlsx", index=False)
        """
        ext = Path(str(path)).suffix.lower()
        if ext in _BLOCKED_EXTENSIONS:
            raise PickleRemovedError(str(path))
        from etlpipe._config import get_engine

        return get_engine().output_data(df, path, **kwargs)

    # ------------------------------------------------------------------ #
    # Text Input
    # ------------------------------------------------------------------ #
    @staticmethod
    def text_input(
        data: dict[str, list] | list[dict] | list[list | tuple],
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Create a DataFrame from inline data.

        Args:
            data: Data supplied as:
                - ``dict[str, list]`` — column-oriented
                - ``list[dict]`` — row-oriented records
                - ``list[list | tuple]`` — rows (requires *columns*)
            columns: Column names when *data* is a list of lists/tuples.

        Returns:
            A new ``DataFrame``.

        Raises:
            ValueError: If *columns* is required but not provided.

        Example:
            >>> df = InOut.text_input({"Name": ["Alice", "Bob"], "Age": [30, 25]})
        """
        from etlpipe._config import get_engine

        return get_engine().text_input(data, columns)

    # ------------------------------------------------------------------ #
    # Browse
    # ------------------------------------------------------------------ #
    @staticmethod
    def browse(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
        """Display summary information about a DataFrame.

        Prints shape, column types, null counts, descriptive statistics,
        and the first *n* rows to stdout, then returns the original
        DataFrame unchanged (so it can be used mid-pipeline).

        Args:
            df: The DataFrame to inspect.
            n: Number of head rows to display.

        Returns:
            The same *df* (unmodified).

        Example:
            >>> result = InOut.browse(df)
        """
        from etlpipe._config import get_engine

        return get_engine().browse(df, n)

    # ------------------------------------------------------------------ #
    # Directory
    # ------------------------------------------------------------------ #
    @staticmethod
    def directory(path: str | Path, pattern: str = "*") -> pd.DataFrame:
        """List files in a directory.

        Returns a DataFrame containing metadata about each file that
        matches the given glob *pattern*.

        Args:
            path: Directory to scan.
            pattern: Glob pattern (e.g. ``"*.csv"``).

        Returns:
            DataFrame with columns ``FullPath``, ``Directory``,
            ``FileName``, ``ShortFileName``, ``CreationTime``,
            ``LastWriteTime``, ``LastAccessTime``, ``Size``.

        Raises:
            FileNotFoundError: If *path* does not exist or is not a directory.

        Example:
            >>> files_df = InOut.directory("./data", "*.csv")
        """
        from etlpipe._config import get_engine

        return get_engine().directory(path, pattern)

    # ------------------------------------------------------------------ #
    # Date Time Now
    # ------------------------------------------------------------------ #
    @staticmethod
    def date_time_now() -> pd.DataFrame:
        """Return the current date/time as a single-row DataFrame.

        Returns:
            A DataFrame with one row and one column ``DateTime``.

        Example:
            >>> now_df = InOut.date_time_now()
        """
        from etlpipe._config import get_engine

        return get_engine().date_time_now()
