"""Shared input validation helpers for etlpipe tool functions.

Every public tool function validates its inputs through these helpers
to provide clear, consistent error messages across the library.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd


def validate_dataframe(df: Any, param_name: str = "df") -> None:
    """Ensure the given object is a pandas DataFrame.

    Args:
        df: The object to validate.
        param_name: Name of the parameter (for error messages).

    Raises:
        TypeError: If *df* is not a ``pandas.DataFrame``.
    """
    valid_types = (pd.DataFrame,)
    try:
        from pyspark.sql import DataFrame as SparkDF

        valid_types = (pd.DataFrame, SparkDF)
    except ImportError:
        pass
    if not isinstance(df, valid_types):
        raise TypeError(f"'{param_name}' must be a pandas or PySpark DataFrame, got {type(df).__name__}.")


def validate_columns(
    df: Any,
    columns: str | Sequence[str],
    param_name: str = "columns",
) -> list[str]:
    """Ensure the specified columns exist in the DataFrame.

    Accepts a single column name (``str``) or a sequence of names and
    always returns a ``list[str]`` for uniform downstream handling.

    Args:
        df: The DataFrame to check against.
        columns: Column name(s) to validate.
        param_name: Name of the parameter (for error messages).

    Returns:
        A list of validated column names.

    Raises:
        TypeError: If *columns* is not a string or sequence of strings.
        KeyError: If any column is missing from *df*.
    """
    if isinstance(columns, str):
        columns = [columns]
    elif not isinstance(columns, (list, tuple)):
        raise TypeError(f"'{param_name}' must be a string or list of strings, got {type(columns).__name__}.")

    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise KeyError(f"Column(s) not found in DataFrame: {missing}. Available columns: {list(df.columns)}")
    return list(columns)


def validate_not_empty(df: Any, param_name: str = "df") -> None:
    """Ensure the DataFrame is not empty.

    Args:
        df: The DataFrame to check.
        param_name: Name of the parameter (for error messages).

    Raises:
        ValueError: If *df* has zero rows.
    """
    if isinstance(df, pd.DataFrame):
        if df.empty:
            raise ValueError(f"'{param_name}' must not be an empty DataFrame.")
    else:
        # For PySpark, check if at least 1 row exists without counting all
        if len(df.head(1)) == 0:
            raise ValueError(f"'{param_name}' must not be an empty DataFrame.")
