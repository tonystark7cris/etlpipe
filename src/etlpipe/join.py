"""Join — Data blending tools.

**Join** tool palette: inner/outer joins, unions,
find-replace, cross joins, and fuzzy matching.

All methods are static and return **new** DataFrames.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


class Join:
    """Etlpipe **Join** tool palette.

    Provides static methods for merging, stacking, and matching
    DataFrames.
    """

    # ------------------------------------------------------------------ #
    # Join  (L / J / R anchors)
    # ------------------------------------------------------------------ #
    @staticmethod
    def join(
        left: pd.DataFrame,
        right: pd.DataFrame,
        on: str | Sequence[str] | None = None,
        left_on: str | Sequence[str] | None = None,
        right_on: str | Sequence[str] | None = None,
        suffixes: tuple[str, str] = ("_left", "_right"),
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Merge two DataFrames and return all three Etlpipe anchors.

        Args:
            left: Left DataFrame.
            right: Right DataFrame.
            on: Column(s) present in both DataFrames to join on.
            left_on: Left-side join column(s) (when names differ).
            right_on: Right-side join column(s) (when names differ).
            suffixes: Suffixes for overlapping non-key column names.

        Returns:
            A 3-tuple ``(left_unjoined, joined, right_unjoined)``
            matching Etlpipe's **L**, **J**, **R** output anchors.

        Example:
            >>> L, J, R = Join.join(orders, customers, on="CustomerID")
        """
        from etlpipe._config import get_engine

        return get_engine().join(left, right, on, left_on, right_on, suffixes)

    # ------------------------------------------------------------------ #
    # Join Multiple
    # ------------------------------------------------------------------ #
    @staticmethod
    def join_multiple(
        *dfs: pd.DataFrame,
        on: str | Sequence[str] | None = None,
        join_type: str = "outer",
    ) -> pd.DataFrame:
        """Join three or more DataFrames.

        Args:
            *dfs: Two or more DataFrames to join.
            on: Column(s) present in **all** DataFrames.  If ``None``,
                joins on the common columns.
            join_type: ``"inner"`` or ``"outer"``.

        Returns:
            A single merged DataFrame.

        Raises:
            ValueError: If fewer than two DataFrames are provided.

        Example:
            >>> combined = Join.join_multiple(df1, df2, df3, on="ID")
        """
        from etlpipe._config import get_engine

        return get_engine().join_multiple(*dfs, on=on, join_type=join_type)

    # ------------------------------------------------------------------ #
    # Union
    # ------------------------------------------------------------------ #
    @staticmethod
    def union(
        *dfs: pd.DataFrame,
        by: str = "name",
    ) -> pd.DataFrame:
        """Stack DataFrames vertically.

        Args:
            *dfs: Two or more DataFrames.
            by: ``"name"`` aligns by column name (default);
                ``"position"`` aligns by ordinal position.

        Returns:
            A single vertically concatenated DataFrame.

        Example:
            >>> all_data = Join.union(jan_df, feb_df, mar_df)
        """
        from etlpipe._config import get_engine

        return get_engine().union(*dfs, by=by)

    # ------------------------------------------------------------------ #
    # Find Replace
    # ------------------------------------------------------------------ #
    @staticmethod
    def find_replace(
        df: pd.DataFrame,
        find_df: pd.DataFrame,
        find_col: str,
        replace_col: str,
        target_col: str | None = None,
        mode: str = "entire",
        append: bool = False,
    ) -> pd.DataFrame:
        """Find and replace values using a lookup table.

        Args:
            df: The main DataFrame.
            find_df: Lookup DataFrame containing find/replace pairs.
            find_col: Column in *find_df* with values to find.
            replace_col: Column in *find_df* with replacement values.
            target_col: Column in *df* to search against. Defaults to *find_col* if present.
            mode: ``"entire"`` replaces the whole cell value;
                ``"partial"`` performs substring replacement.
            append: If True, appends a new column with the lookup value rather
                than replacing in-place.

        Returns:
            A new DataFrame with replacements applied.

        Example:
            >>> mapping = pd.DataFrame({"State": ["CA", "NY"], "FullName": ["California", "New York"]})
            >>> df = Join.find_replace(df, mapping, "State", "FullName")
        """
        from etlpipe._config import get_engine

        return get_engine().find_replace(df, find_df, find_col, replace_col, target_col, mode, append)

    # ------------------------------------------------------------------ #
    # Make Group
    # ------------------------------------------------------------------ #
    @staticmethod
    def make_group(df: pd.DataFrame, key1: str, key2: str) -> pd.DataFrame:
        """Group data based on relationships.

        Takes pairs of related keys and groups them into connected components.

        Args:
            df: The input DataFrame containing the relationships.
            key1: First key column.
            key2: Second key column.

        Returns:
            A DataFrame with two columns: 'Group' and 'Key'.
        """
        from etlpipe._config import get_engine

        return get_engine().make_group(df, key1, key2)

    # ------------------------------------------------------------------ #
    # Append Fields (Cross Join)
    # ------------------------------------------------------------------ #
    @staticmethod
    def append_fields(
        left: pd.DataFrame,
        right: pd.DataFrame,
    ) -> pd.DataFrame:
        """Cartesian (cross) join of two DataFrames.

        Args:
            left: Left DataFrame.
            right: Right DataFrame.

        Returns:
            A DataFrame with every combination of rows.

        Example:
            >>> product = Join.append_fields(sizes_df, colors_df)
        """
        from etlpipe._config import get_engine

        return get_engine().append_fields(left, right)

    # ------------------------------------------------------------------ #
    # Fuzzy Match
    # ------------------------------------------------------------------ #
    @staticmethod
    def fuzzy_match(
        left: pd.DataFrame,
        right: pd.DataFrame,
        left_on: str,
        right_on: str,
        threshold: float = 0.6,
        score_column: str = "MatchScore",
    ) -> pd.DataFrame:
        """Approximate string matching between two DataFrames.

        Uses ``difflib.SequenceMatcher`` ratio to score similarity.

        Args:
            left: Left DataFrame.
            right: Right DataFrame.
            left_on: String column in *left* to match.
            right_on: String column in *right* to match.
            threshold: Minimum similarity score (0.0 – 1.0) for a match.
            score_column: Name of the output score column.

        Returns:
            A DataFrame containing matched pairs and their scores.

        Example:
            >>> matches = Join.fuzzy_match(df1, df2, "CompanyName", "Name", threshold=0.7)
        """
        from etlpipe._config import get_engine

        return get_engine().fuzzy_match(left, right, left_on, right_on, threshold, score_column)
