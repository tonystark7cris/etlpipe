"""Preparation â€” Data preparation tools.

**Preparation** tool palette: filtering, sorting,
cleaning, formulas, sampling, tiling, imputation and more.

All methods are static and return **new** DataFrames â€” originals are
never mutated.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd


class Preparation:
    """etlpipe **Preparation** tool palette.

    Provides static methods for data cleansing, filtering, sorting,
    sampling, formula evaluation, and other row/column transformations.
    """

    # ------------------------------------------------------------------ #
    # Filter  (T / F anchors)
    # ------------------------------------------------------------------ #
    @staticmethod
    def filter(
        df: pd.DataFrame,
        condition: str | Callable[[pd.DataFrame], pd.Series] | None = None,
        *,
        column: str | None = None,
        operator: str | None = None,
        value: Any = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Split a DataFrame into rows that match and don't match a condition.

        Can be used in two modes:
        - **Custom Filter**: Provide a `condition` string or callable.
        - **Basic Filter**: Provide `column`, `operator`, and optionally `value`.

        Args:
            df: The input DataFrame.
            condition: A pandas query string (e.g. ``"Age > 30"``) or a
                callable that returns a boolean Series.
            column: The column to filter by (for Basic filter).
            operator: The operator to apply (e.g. ``"=="``, ``">"``, ``"contains"``, ``"is null"``).
            value: The value to compare against (for Basic filter).

        Returns:
            A tuple ``(true_df, false_df)`` matching the tool's **T** and **F** output anchors.

        Example:
            >>> t, f = Preparation.filter(df, "Revenue > 1000")
            >>> t, f = Preparation.filter(df, column="Status", operator="==", value="Active")
        """
        from etlpipe._config import get_engine

        return get_engine().filter(df, condition, column=column, operator=operator, value=value)

    # ------------------------------------------------------------------ #
    # Formula
    # ------------------------------------------------------------------ #
    @staticmethod
    def formula(
        df: pd.DataFrame,
        column: str,
        expression: str | Callable[[pd.DataFrame], pd.Series],
    ) -> pd.DataFrame:
        """Create or update a column using an expression.

        Args:
            df: The input DataFrame.
            column: Name of the column to create or update.
            expression: A Python expression string evaluated with
                ``df.eval()`` (can reference existing columns) **or** a
                callable ``f(df) -> Series``.

        Returns:
            A new DataFrame with the computed column.

        Example:
            >>> df = Preparation.formula(df, "Profit", "Revenue - Cost")
            >>> df = Preparation.formula(df, "Upper", lambda d: d["Name"].str.upper())
        """
        from etlpipe._config import get_engine

        return get_engine().formula(df, column, expression)

    # ------------------------------------------------------------------ #
    # Select
    # ------------------------------------------------------------------ #
    @staticmethod
    def select(
        df: pd.DataFrame,
        columns: Sequence[str] | None = None,
        renames: dict[str, str] | None = None,
        dtypes: dict[str, str | type] | None = None,
    ) -> pd.DataFrame:
        """Select, rename, and retype columns.

        Args:
            df: The input DataFrame.
            columns: Columns to keep (in order). ``None`` keeps all.
            renames: ``{old_name: new_name}`` mapping.
            dtypes: ``{column: dtype}`` mapping applied after renaming.

        Returns:
            A new DataFrame with the requested columns, renames, and types.

        Example:
            >>> df2 = Preparation.select(df, ["Name", "Age"], renames={"Name": "FullName"})
        """
        from etlpipe._config import get_engine

        return get_engine().select(df, columns, renames, dtypes)

    # ------------------------------------------------------------------ #
    # Data Cleansing
    # ------------------------------------------------------------------ #
    @staticmethod
    def data_cleansing(
        df: pd.DataFrame,
        columns: Sequence[str] | None = None,
        remove_null_rows: bool = False,
        replace_nulls_with: Any | None = None,
        strip_whitespace: bool = True,
        remove_letters: bool = False,
        remove_numbers: bool = False,
        remove_punctuation: bool = False,
        modify_case: str | None = None,
    ) -> pd.DataFrame:
        """Clean data values in specified columns.

        Args:
            df: The input DataFrame.
            columns: Columns to clean. ``None`` applies to all string columns.
            remove_null_rows: Drop rows where *any* selected column is null.
            replace_nulls_with: Value to fill nulls with (applied before
                string operations).
            strip_whitespace: Remove leading/trailing whitespace.
            remove_letters: Remove all alphabetic characters.
            remove_numbers: Remove all digits.
            remove_punctuation: Remove punctuation characters.
            modify_case: ``"lower"``, ``"upper"``, or ``"title"``.

        Returns:
            A cleaned DataFrame.

        Example:
            >>> clean = Preparation.data_cleansing(df, ["Name"], strip_whitespace=True)
        """
        from etlpipe._config import get_engine

        return get_engine().data_cleansing(
            df,
            columns,
            remove_null_rows,
            replace_nulls_with,
            strip_whitespace,
            remove_letters,
            remove_numbers,
            remove_punctuation,
            modify_case,
        )

    # ------------------------------------------------------------------ #
    # Sort
    # ------------------------------------------------------------------ #
    @staticmethod
    def sort(
        df: pd.DataFrame,
        columns: str | Sequence[str],
        ascending: bool | Sequence[bool] = True,
    ) -> pd.DataFrame:
        """Sort a DataFrame by one or more columns.

        Args:
            df: The input DataFrame.
            columns: Column(s) to sort by.
            ascending: Sort direction(s). A single bool applies to all
                columns; a list must match the length of *columns*.

        Returns:
            A sorted DataFrame.

        Example:
            >>> df = Preparation.sort(df, ["Region", "Sales"], ascending=[True, False])
        """
        from etlpipe._config import get_engine

        return get_engine().sort(df, columns, ascending)

    # ------------------------------------------------------------------ #
    # Unique  (U / D anchors)
    # ------------------------------------------------------------------ #
    @staticmethod
    def unique(
        df: pd.DataFrame,
        columns: str | Sequence[str],
        ignore_case: bool = False,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Split into unique and duplicate rows.

        Args:
            df: The input DataFrame.
            columns: Column(s) used to determine uniqueness.
            ignore_case: Whether to ignore case for string columns.

        Returns:
            A tuple ``(unique_df, duplicate_df)`` matching etlpipe's
            **U** and **D** output anchors.

        Example:
            >>> uniq, dups = Preparation.unique(df, "Email")
        """
        from etlpipe._config import get_engine

        return get_engine().unique(df, columns, ignore_case)

    # ------------------------------------------------------------------ #
    # Sample
    # ------------------------------------------------------------------ #
    @staticmethod
    def sample(
        df: pd.DataFrame,
        n: int | None = None,
        pct: float | None = None,
        random: bool = False,
        position: str = "first",
        random_state: int | None = None,
    ) -> pd.DataFrame:
        """Return a sample of rows.

        Args:
            df: The input DataFrame.
            n: Number of rows. Mutually exclusive with *pct*.
            pct: Fraction of rows (0.0 â€“ 1.0). Mutually exclusive with *n*.
            random: If ``True`` and *n* is set, sample randomly.
            position: ``"first"`` (default) or ``"last"`` â€” ignored when
                *random* is ``True``.
            random_state: Seed for reproducible random sampling.

        Returns:
            A sampled DataFrame.

        Raises:
            ValueError: If neither *n* nor *pct* is specified.

        Example:
            >>> top5 = Preparation.sample(df, n=5)
            >>> rand_10pct = Preparation.sample(df, pct=0.10, random=True)
        """
        from etlpipe._config import get_engine

        return get_engine().sample(df, n, pct, random, position, random_state)

    # ------------------------------------------------------------------ #
    # Record ID
    # ------------------------------------------------------------------ #
    @staticmethod
    def record_id(
        df: pd.DataFrame,
        column_name: str = "RecordID",
        start: int = 1,
    ) -> pd.DataFrame:
        """Add an auto-incrementing ID column.

        Args:
            df: The input DataFrame.
            column_name: Name of the new ID column.
            start: Starting value.

        Returns:
            A new DataFrame with the ID column prepended.

        Example:
            >>> df = Preparation.record_id(df, "RowNum")
        """
        from etlpipe._config import get_engine

        return get_engine().record_id(df, column_name, start)

    # ------------------------------------------------------------------ #
    # Generate Rows
    # ------------------------------------------------------------------ #
    @staticmethod
    def generate_rows(
        count: int,
        expression: Callable[[int], dict[str, Any]] | None = None,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Generate rows programmatically.

        Args:
            count: Number of rows to generate.
            expression: A callable ``f(row_index) -> dict`` that produces
                one row's data.  If ``None``, a single ``RowNum`` column
                is created with values ``0 .. count-1``.
            columns: Column names when *expression* returns a ``dict``.
                Only used to enforce column order.

        Returns:
            A new DataFrame with the generated rows.

        Example:
            >>> df = Preparation.generate_rows(5, lambda i: {"x": i, "y": i**2})
        """
        from etlpipe._config import get_engine

        return get_engine().generate_rows(count, expression, columns)

    # ------------------------------------------------------------------ #
    # Auto Field
    # ------------------------------------------------------------------ #
    @staticmethod
    def auto_field(df: pd.DataFrame) -> pd.DataFrame:
        """Optimize column data types automatically.

        Down-casts integers, floats, and converts ``object`` columns to
        ``category`` when the cardinality is low (< 50% unique values).

        Args:
            df: The input DataFrame.

        Returns:
            A dtype-optimized DataFrame.

        Example:
            >>> optimized = Preparation.auto_field(df)
        """
        from etlpipe._config import get_engine

        return get_engine().auto_field(df)

    # ------------------------------------------------------------------ #
    # Multi-Field Formula
    # ------------------------------------------------------------------ #
    @staticmethod
    def multi_field_formula(
        df: pd.DataFrame,
        columns: Sequence[str],
        expression: Callable[[pd.Series], pd.Series],
    ) -> pd.DataFrame:
        """Apply the same transformation to multiple columns.

        Args:
            df: The input DataFrame.
            columns: List of columns to transform.
            expression: A callable ``f(series) -> series`` applied to
                each column independently.

        Returns:
            A new DataFrame with the transformed columns.

        Example:
            >>> df = Preparation.multi_field_formula(df, ["A", "B"], lambda s: s * 2)
        """
        from etlpipe._config import get_engine

        return get_engine().multi_field_formula(df, columns, expression)

    # ------------------------------------------------------------------ #
    # Multi-Row Formula
    # ------------------------------------------------------------------ #
    @staticmethod
    def multi_row_formula(
        df: pd.DataFrame,
        column: str,
        expression: Callable[[pd.Series, pd.Series], pd.Series],
        rows_back: int = 1,
        group_by: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Apply a formula referencing other rows.

        Args:
            df: The input DataFrame.
            column: Column to compute.
            expression: ``f(current_series, offset_series) -> series``.
                *current_series* is the current column values,
                *offset_series* is the shifted column.
            rows_back: Number of rows to shift (positive = look back,
                negative = look forward).
            group_by: Optional grouping column(s) for the shift.

        Returns:
            A new DataFrame with the computed column.

        Example:
            >>> df = Preparation.multi_row_formula(
            ...     df, "Delta",
            ...     lambda cur, prev: cur - prev,
            ...     rows_back=1
            ... )
        """
        from etlpipe._config import get_engine

        return get_engine().multi_row_formula(df, column, expression, rows_back, group_by)

    # ------------------------------------------------------------------ #
    # Tile
    # ------------------------------------------------------------------ #
    @staticmethod
    def tile(
        df: pd.DataFrame,
        column: str,
        n_tiles: int,
        method: str = "equal_records",
        output_column: str = "Tile",
    ) -> pd.DataFrame:
        """Assign tile / quantile groups.

        Args:
            df: The input DataFrame.
            column: Column to tile on.
            n_tiles: Number of tiles (groups).
            method: ``"equal_records"`` (quantile-based) or
                ``"equal_range"`` (equal-width bins).
            output_column: Name of the new tile column.

        Returns:
            A new DataFrame with the tile column appended.

        Example:
            >>> df = Preparation.tile(df, "Sales", 4)
        """
        from etlpipe._config import get_engine

        return get_engine().tile(df, column, n_tiles, method, output_column)

    # ------------------------------------------------------------------ #
    # Imputation
    # ------------------------------------------------------------------ #
    @staticmethod
    def imputation(
        df: pd.DataFrame,
        columns: str | Sequence[str],
        method: str = "mean",
        replacement_value: Any | None = None,
        add_indicator: bool = True,
    ) -> pd.DataFrame:
        """Fill missing values.

        Args:
            df: The input DataFrame.
            columns: Column(s) to impute.
            method: One of ``"mean"``, ``"median"``, ``"mode"``, or
                ``"value"`` (requires *replacement_value*).
            replacement_value: Custom fill value when ``method="value"``.
            add_indicator: If ``True``, adds a boolean column
                ``{col}_WasImputed`` for each imputed column.

        Returns:
            A new DataFrame with missing values filled.

        Example:
            >>> df = Preparation.imputation(df, "Salary", method="median")
        """
        from etlpipe._config import get_engine

        return get_engine().imputation(df, columns, method, replacement_value, add_indicator)

    # ------------------------------------------------------------------ #
    # Create Samples
    # ------------------------------------------------------------------ #
    @staticmethod
    def create_samples(
        df: pd.DataFrame,
        estimation_pct: float,
        validation_pct: float,
        holdout_pct: float,
        random_state: int | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split data into Estimation, Validation, and Holdout samples.

        Args:
            df: The input DataFrame.
            estimation_pct: Fraction of data for the estimation set.
            validation_pct: Fraction of data for the validation set.
            holdout_pct: Fraction of data for the holdout set.
            random_state: Seed for reproducible sampling.

        Returns:
            A tuple ``(estimation_df, validation_df, holdout_df)``.
        """
        from etlpipe._config import get_engine

        return get_engine().create_samples(df, estimation_pct, validation_pct, holdout_pct, random_state)

    # ------------------------------------------------------------------ #
    # Date Filter
    # ------------------------------------------------------------------ #
    @staticmethod
    def date_filter(
        df: pd.DataFrame,
        column: str,
        start_date: str | pd.Timestamp | None = None,
        end_date: str | pd.Timestamp | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Filter records based on date/time criteria.

        Args:
            df: The input DataFrame.
            column: The datetime column to filter on.
            start_date: The inclusive start date.
            end_date: The inclusive end date.

        Returns:
            A tuple ``(true_df, false_df)`` matching the tool's **T** and **F** anchors.
        """
        from etlpipe._config import get_engine

        return get_engine().date_filter(df, column, start_date, end_date)

    # ------------------------------------------------------------------ #
    # Oversample Field
    # ------------------------------------------------------------------ #
    @staticmethod
    def oversample_field(
        df: pd.DataFrame,
        column: str,
        value: Any,
        target_pct: float = 0.5,
        random_state: int | None = None,
    ) -> pd.DataFrame:
        """Sample a specific class more frequently.

        Args:
            df: The input DataFrame.
            column: The column containing the target class.
            value: The specific class value to oversample.
            target_pct: The desired percentage of the target class in the output (0.0 to 1.0).
            random_state: Seed for reproducible sampling.

        Returns:
            A DataFrame with the target class oversampled.
        """
        from etlpipe._config import get_engine

        return get_engine().oversample_field(df, column, value, target_pct, random_state)

    # ------------------------------------------------------------------ #
    # Rank
    # ------------------------------------------------------------------ #
    @staticmethod
    def rank(
        df: pd.DataFrame,
        column: str,
        group_by: str | Sequence[str] | None = None,
        ascending: bool = False,
        method: str = "min",
        output_column: str = "Rank",
    ) -> pd.DataFrame:
        """Provide ranking functionality.

        Args:
            df: The input DataFrame.
            column: The column to rank.
            group_by: Optional column(s) to group the ranking by.
            ascending: If True, smallest values get rank 1. If False (default), largest get rank 1.
            method: How to handle equal values ('min', 'dense', 'first', 'average', 'max').
            output_column: The name of the new column containing the rank.

        Returns:
            A DataFrame with the rank column appended.
        """
        from etlpipe._config import get_engine

        return get_engine().rank(df, column, group_by, ascending, method, output_column)
