"""Developer — Utility and advanced tools.

**Developer** tool palette: base64 encoding,
HTTP downloads, schema inspection, and dynamic renaming.

All methods are static and return **new** DataFrames.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd


class Developer:
    """Etlpipe **Developer** tool palette.

    Provides static methods for encoding, downloading, schema
    inspection, and dynamic column renaming.
    """

    # ------------------------------------------------------------------ #
    # Base64 Encode
    # ------------------------------------------------------------------ #
    @staticmethod
    def base64_encode(
        df: pd.DataFrame,
        column: str,
        output_column: str | None = None,
    ) -> pd.DataFrame:
        """Encode a column's values to Base64.

        Args:
            df: The input DataFrame.
            column: Column to encode.
            output_column: Name for the encoded column.  Defaults to
                ``{column}_Base64``.

        Returns:
            A new DataFrame with the encoded column.

        Example:
            >>> df = Developer.base64_encode(df, "Password")
        """
        from etlpipe._config import get_engine

        return get_engine().base64_encode(df, column, output_column)

    # ------------------------------------------------------------------ #
    # Base64 Decode
    # ------------------------------------------------------------------ #
    @staticmethod
    def base64_decode(
        df: pd.DataFrame,
        column: str,
        output_column: str | None = None,
    ) -> pd.DataFrame:
        """Decode a Base64-encoded column.

        Args:
            df: The input DataFrame.
            column: Column to decode.
            output_column: Name for the decoded column.  Defaults to
                ``{column}_Decoded``.

        Returns:
            A new DataFrame with the decoded column.

        Example:
            >>> df = Developer.base64_decode(df, "Password_Base64")
        """
        from etlpipe._config import get_engine

        return get_engine().base64_decode(df, column, output_column)

    # ------------------------------------------------------------------ #
    # Download
    # ------------------------------------------------------------------ #
    @staticmethod
    def download(
        url: str,
        params: dict[str, Any] | None = None,
        output_column: str = "DownloadData",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> pd.DataFrame:
        """Fetch data from a URL.

        Attempts to parse the response as JSON.  If that fails, the raw
        text is returned in a single-column DataFrame.

        Includes automatic retry with exponential backoff for transient
        network failures (``URLError``, ``TimeoutError``, HTTP 5xx).

        **Note**: This uses ``urllib`` from the standard library to avoid
        adding ``requests`` as a hard dependency.

        Args:
            url: The URL to fetch.
            params: Optional query parameters.
            output_column: Name of the output column.
            max_retries: Maximum number of retry attempts (default 3).
            retry_delay: Base delay in seconds between retries (default 1.0).
                Uses exponential backoff: delay × 2^(attempt-1).

        Returns:
            A DataFrame containing the downloaded data.

        Example:
            >>> df = Developer.download("https://api.example.com/data")
            >>> df = Developer.download("https://api.example.com/data", max_retries=5)
        """
        from etlpipe._config import get_engine

        return get_engine().download(url, params, output_column, max_retries, retry_delay)

    # ------------------------------------------------------------------ #
    # Column Info
    # ------------------------------------------------------------------ #
    @staticmethod
    def column_info(df: pd.DataFrame) -> pd.DataFrame:
        """Return schema/metadata about a DataFrame.

        Args:
            df: The input DataFrame.

        Returns:
            A DataFrame with columns ``Name``, ``Type``, ``Size``,
            ``NonNullCount``, ``NullCount``, ``UniqueCount``.

        Example:
            >>> schema = Developer.column_info(df)
        """
        from etlpipe._config import get_engine

        return get_engine().column_info(df)

    # ------------------------------------------------------------------ #
    # Dynamic Rename
    # ------------------------------------------------------------------ #
    @staticmethod
    def dynamic_rename(
        df: pd.DataFrame,
        rename_df: pd.DataFrame,
        key_col: str = "OldName",
        new_name_col: str = "NewName",
        mode: str = "mapping",
    ) -> pd.DataFrame:
        """Rename columns dynamically using a lookup table.

        Args:
            df: The DataFrame whose columns will be renamed.
            rename_df: A lookup DataFrame with the rename mapping.
            key_col: Column in *rename_df* containing current column names.
            new_name_col: Column in *rename_df* containing new names.
            mode: ``"mapping"`` uses the lookup table;
                ``"prefix"`` adds a prefix from a single-value
                *rename_df*;
                ``"suffix"`` adds a suffix from a single-value
                *rename_df*.

        Returns:
            A DataFrame with renamed columns.

        Example:
            >>> mapping = pd.DataFrame({"OldName": ["col_a"], "NewName": ["Column A"]})
            >>> df = Developer.dynamic_rename(df, mapping)
        """
        from etlpipe._config import get_engine

        return get_engine().dynamic_rename(df, rename_df, key_col, new_name_col, mode)

    # ------------------------------------------------------------------ #
    # JSON Parse
    # ------------------------------------------------------------------ #
    @staticmethod
    def json_parse(
        df: pd.DataFrame,
        column: str,
        prefix: str | None = None,
    ) -> pd.DataFrame:
        """Parse a JSON string column into separate columns.

        Args:
            df: The input DataFrame.
            column: The column containing JSON strings.
            prefix: Optional prefix for new columns. Defaults to the original column name.

        Returns:
            A new DataFrame with the parsed JSON fields expanded as new columns.

        Example:
            >>> df = Developer.json_parse(df, "JSON_Data")
        """
        from etlpipe._config import get_engine

        return get_engine().json_parse(df, column, prefix)

    # ------------------------------------------------------------------ #
    # Dynamic Select
    # ------------------------------------------------------------------ #
    @staticmethod
    def dynamic_select(
        df: pd.DataFrame,
        dtype_include: Any | None = None,
        dtype_exclude: Any | None = None,
        pattern: str | None = None,
    ) -> pd.DataFrame:
        """Select columns dynamically based on data type or pattern.

        Args:
            df: The input DataFrame.
            dtype_include: Data types to include (e.g., 'number', 'object').
            dtype_exclude: Data types to exclude.
            pattern: A regex pattern to match column names against.

        Returns:
            A new DataFrame containing only the selected columns.

        Example:
            >>> df_num = Developer.dynamic_select(df, dtype_include="number")
            >>> df_sales = Developer.dynamic_select(df, pattern="^Sales_")
        """
        from etlpipe._config import get_engine

        return get_engine().dynamic_select(df, dtype_include, dtype_exclude, pattern)

    # ------------------------------------------------------------------ #
    # Test
    # ------------------------------------------------------------------ #
    @staticmethod
    def test(
        df: pd.DataFrame,
        condition_func: Callable,
        error_msg: str = "Test condition failed",
    ) -> pd.DataFrame:
        """Verify data using a custom condition.

        Evaluates `condition_func(df)`. If it returns False, raises a ValueError.

        Args:
            df: The input DataFrame.
            condition_func: A callable taking the DataFrame and returning a boolean.
            error_msg: Error message to raise on failure.

        Returns:
            The original DataFrame if the test passes.

        Raises:
            ValueError: If the condition is false.

        Example:
            >>> Developer.test(df, lambda d: d["Sales"].sum() > 0, "No sales!")
        """
        from etlpipe._config import get_engine

        return get_engine().test(df, condition_func, error_msg)

    # ------------------------------------------------------------------ #
    # Test Equal
    # ------------------------------------------------------------------ #
    @staticmethod
    def test_equal(
        df_left: pd.DataFrame,
        df_right: pd.DataFrame,
        **kwargs: Any,
    ) -> None:
        """Test if two data streams are identical.

        Wraps `pandas.testing.assert_frame_equal`. Raises AssertionError if they differ.

        Args:
            df_left: The first DataFrame.
            df_right: The second DataFrame.
            **kwargs: Additional arguments to `pd.testing.assert_frame_equal`.

        Raises:
            AssertionError: If the DataFrames do not match.

        Example:
            >>> Developer.test_equal(df1, df2)
        """
        from etlpipe._config import get_engine

        return get_engine().test_equal(df_left, df_right, **kwargs)
