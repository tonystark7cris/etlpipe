"""Transform — Reshape and aggregate tools.

**Transform** tool palette: summarise, transpose,
cross-tab, running totals, and counting.

All methods are static and return **new** DataFrames.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pandas as pd


class Transform:
    """Etlpipe **Transform** tool palette.

    Provides static methods for aggregation, pivoting, and other
    reshape operations.
    """

    # ------------------------------------------------------------------ #
    # Aggregation Resolver
    # ------------------------------------------------------------------ #
    @staticmethod
    def _resolve_aggregation(agg_name: str | Callable) -> str | Callable:
        """Resolve custom aggregation strings to pandas logic."""
        from etlpipe._config import get_engine

        return get_engine()._resolve_aggregation(agg_name)

    # ------------------------------------------------------------------ #
    # Summarize
    # ------------------------------------------------------------------ #
    @staticmethod
    def summarize(
        df: pd.DataFrame,
        group_by: str | Sequence[str] | None = None,
        aggregations: dict[str, str | list[str]] | None = None,
    ) -> pd.DataFrame:
        """Group and aggregate a DataFrame.

        Output columns are named ``{Action}_{Column}`` (e.g.
        ``Sum_Sales``, ``Count_ID``).

        Args:
            df: The input DataFrame.
            group_by: Column(s) to group by.  ``None`` aggregates the
                entire DataFrame.
            aggregations: ``{column: agg_func}`` or
                ``{column: [agg_func, …]}`` dict passed to
                ``DataFrame.agg()``.  Common values: ``"sum"``,
                ``"mean"``, ``"count"``, ``"min"``, ``"max"``,
                ``"first"``, ``"last"``, ``"std"``, ``"median"``.

        Returns:
            An aggregated DataFrame.

        Example:
            >>> summary = Transform.summarize(
            ...     df, group_by="Region",
            ...     aggregations={"Sales": ["sum", "mean"], "Quantity": "sum"}
            ... )
        """
        from etlpipe._config import get_engine

        return get_engine().summarize(df, group_by, aggregations)

    # ------------------------------------------------------------------ #
    # Transpose (wide → long)
    # ------------------------------------------------------------------ #
    @staticmethod
    def transpose(
        df: pd.DataFrame,
        key_columns: str | Sequence[str],
        data_columns: str | Sequence[str] | None = None,
        var_name: str = "Name",
        value_name: str = "Value",
    ) -> pd.DataFrame:
        """Unpivot (melt) a DataFrame from wide to long format.

        Args:
            df: The input DataFrame.
            key_columns: Column(s) to keep as identifiers.
            data_columns: Column(s) to unpivot.  ``None`` unpivots all
                columns not in *key_columns*.
            var_name: Name for the variable (header) column.
            value_name: Name for the value column.

        Returns:
            A long-format DataFrame.

        Example:
            >>> long = Transform.transpose(df, key_columns="ID", data_columns=["Q1", "Q2", "Q3"])
        """
        from etlpipe._config import get_engine

        return get_engine().transpose(df, key_columns, data_columns, var_name, value_name)

    # ------------------------------------------------------------------ #
    # Cross Tab (long → wide)
    # ------------------------------------------------------------------ #
    @staticmethod
    def cross_tab(
        df: pd.DataFrame,
        group_by: str | Sequence[str],
        pivot_col: str,
        value_col: str,
        agg: str = "sum",
    ) -> pd.DataFrame:
        """Pivot a DataFrame from long to wide format.

        Args:
            df: The input DataFrame.
            group_by: Row identifier column(s).
            pivot_col: Column whose unique values become new columns.
            value_col: Column to aggregate.
            agg: Aggregation function (e.g. ``"sum"``, ``"mean"``).

        Returns:
            A wide-format DataFrame.

        Example:
            >>> wide = Transform.cross_tab(df, "Region", "Quarter", "Revenue", "sum")
        """
        from etlpipe._config import get_engine

        return get_engine().cross_tab(df, group_by, pivot_col, value_col, agg)

    # ------------------------------------------------------------------ #
    # Running Total
    # ------------------------------------------------------------------ #
    @staticmethod
    def running_total(
        df: pd.DataFrame,
        column: str,
        group_by: str | Sequence[str] | None = None,
        output_column: str | None = None,
    ) -> pd.DataFrame:
        """Compute a cumulative sum.

        Args:
            df: The input DataFrame.
            column: Column to accumulate.
            group_by: Optional grouping column(s) for partitioned sums.
            output_column: Name for the running-total column.  Defaults
                to ``RunningTotal_{column}``.

        Returns:
            A new DataFrame with the running total column appended.

        Example:
            >>> df = Transform.running_total(df, "Sales", group_by="Region")
        """
        from etlpipe._config import get_engine

        return get_engine().running_total(df, column, group_by, output_column)

    # ------------------------------------------------------------------ #
    # Count Records
    # ------------------------------------------------------------------ #
    @staticmethod
    def count_records(
        df: pd.DataFrame,
        output_col: str = "Count",
    ) -> pd.DataFrame:
        """Return the total row count as a single-row DataFrame.

        Args:
            df: The input DataFrame.
            output_col: Name of the count column.

        Returns:
            A single-row DataFrame.

        Example:
            >>> count_df = Transform.count_records(df)
        """
        from etlpipe._config import get_engine

        return get_engine().count_records(df, output_col)

    # ------------------------------------------------------------------ #
    # Arrange
    # ------------------------------------------------------------------ #
    @staticmethod
    def arrange(
        df: pd.DataFrame,
        key_columns: str | Sequence[str] | None = None,
        output_mapping: dict[str, Sequence[str]] | None = None,
    ) -> pd.DataFrame:
        """Manually transpose and rearrange columns.

        Args:
            df: The input DataFrame.
            key_columns: Columns to keep as identifiers for each unpivoted row.
            output_mapping: A dictionary where keys are new column names and
                values are lists of existing columns that will populate them.
                All lists in the mapping must have the same length.

        Returns:
            A rearranged DataFrame.
        """
        from etlpipe._config import get_engine

        return get_engine().arrange(df, key_columns, output_mapping)

    # ------------------------------------------------------------------ #
    # Make Columns
    # ------------------------------------------------------------------ #
    @staticmethod
    def make_columns(
        df: pd.DataFrame,
        num_columns: int,
    ) -> pd.DataFrame:
        """Wrap rows of data into multiple columns.

        Args:
            df: The input DataFrame.
            num_columns: The number of column groups to create.

        Returns:
            A wider, shorter DataFrame with wrapped rows.
        """
        from etlpipe._config import get_engine

        return get_engine().make_columns(df, num_columns)

    # ------------------------------------------------------------------ #
    # Weighted Average
    # ------------------------------------------------------------------ #
    @staticmethod
    def weighted_average(
        df: pd.DataFrame,
        value_column: str,
        weight_column: str,
        group_by: str | Sequence[str] | None = None,
        output_column: str = "WeightedAverage",
    ) -> pd.DataFrame:
        """Calculate a weighted average.

        Args:
            df: The input DataFrame.
            value_column: The column containing values to average.
            weight_column: The column containing weights.
            group_by: Optional column(s) to group by.
            output_column: Name of the output column.

        Returns:
            A DataFrame with the calculated weighted average.
        """
        from etlpipe._config import get_engine

        return get_engine().weighted_average(df, value_column, weight_column, group_by, output_column)
