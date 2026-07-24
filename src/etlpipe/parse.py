"""Parse â€” Text and date parsing tools.

**Parse** tool palette: date/time formatting,
regular expressions, text splitting, and XML parsing.

All methods are static and return **new** DataFrames.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


class Parse:
    """etlpipe **Parse** tool palette.

    Provides static methods for date/time conversion, regex operations,
    text splitting, and XML extraction.
    """

    # ------------------------------------------------------------------ #
    # DateTime
    # ------------------------------------------------------------------ #
    @staticmethod
    def date_time(
        df: pd.DataFrame,
        column: str,
        input_fmt: str | None = None,
        output_fmt: str | None = None,
    ) -> pd.DataFrame:
        """Convert date/time formats.

        Args:
            df: The input DataFrame.
            column: Column containing date/time values.
            input_fmt: ``strftime``-style format of the existing values.
                ``None`` lets pandas infer.
            output_fmt: Desired output format string.  ``None`` keeps
                as ``datetime64``.

        Returns:
            A new DataFrame with the reformatted column.

        Example:
            >>> df = Parse.date_time(df, "Date", input_fmt="%m/%d/%Y", output_fmt="%Y-%m-%d")
        """
        from etlpipe._config import get_engine

        return get_engine().date_time(df, column, input_fmt, output_fmt)

    # ------------------------------------------------------------------ #
    # RegEx Match
    # ------------------------------------------------------------------ #
    @staticmethod
    def regex_match(
        df: pd.DataFrame,
        column: str,
        pattern: str,
        output_column: str = "Match",
    ) -> pd.DataFrame:
        """Flag rows that match a regex pattern.

        Args:
            df: The input DataFrame.
            column: Column to test.
            pattern: Regular expression pattern.
            output_column: Name of the boolean result column.

        Returns:
            A new DataFrame with the match indicator column.

        Example:
            >>> df = Parse.regex_match(df, "Email", r"^[\\w.]+@[\\w.]+$")
        """
        from etlpipe._config import get_engine

        return get_engine().regex_match(df, column, pattern, output_column)

    # ------------------------------------------------------------------ #
    # RegEx Parse
    # ------------------------------------------------------------------ #
    @staticmethod
    def regex_parse(
        df: pd.DataFrame,
        column: str,
        pattern: str,
        output_cols: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Extract capture groups into new columns.

        Args:
            df: The input DataFrame.
            column: Column to parse.
            pattern: Regex with capturing groups.
            output_cols: Names for the extracted columns. Must match the
                number of groups.  ``None`` uses ``Group_1``, ``Group_2``, etc.

        Returns:
            A new DataFrame with the extracted columns appended.

        Example:
            >>> df = Parse.regex_parse(df, "FullName", r"(\\w+)\\s+(\\w+)", ["First", "Last"])
        """
        from etlpipe._config import get_engine

        return get_engine().regex_parse(df, column, pattern, output_cols)

    # ------------------------------------------------------------------ #
    # RegEx Replace
    # ------------------------------------------------------------------ #
    @staticmethod
    def regex_replace(
        df: pd.DataFrame,
        column: str,
        pattern: str,
        replacement: str,
    ) -> pd.DataFrame:
        """Replace text matched by a regex pattern.

        Args:
            df: The input DataFrame.
            column: Column to modify.
            pattern: Regex pattern to match.
            replacement: Replacement string (may contain group refs like ``\\1``).

        Returns:
            A new DataFrame with the replaced values.

        Example:
            >>> df = Parse.regex_replace(df, "Phone", r"\\D", "")
        """
        from etlpipe._config import get_engine

        return get_engine().regex_replace(df, column, pattern, replacement)

    # ------------------------------------------------------------------ #
    # RegEx Tokenize
    # ------------------------------------------------------------------ #
    @staticmethod
    def regex_tokenize(
        df: pd.DataFrame,
        column: str,
        pattern: str,
        split_to: str = "rows",
    ) -> pd.DataFrame:
        """Split a column by regex into rows or columns.

        Args:
            df: The input DataFrame.
            column: Column to split.
            pattern: Regex pattern to split on.
            split_to: ``"rows"`` (one value per row) or ``"columns"``
                (one value per new column).

        Returns:
            A new DataFrame with the tokenized values.

        Example:
            >>> df = Parse.regex_tokenize(df, "Tags", r",\\s*", split_to="rows")
        """
        from etlpipe._config import get_engine

        return get_engine().regex_tokenize(df, column, pattern, split_to)

    # ------------------------------------------------------------------ #
    # Text to Columns
    # ------------------------------------------------------------------ #
    @staticmethod
    def text_to_columns(
        df: pd.DataFrame,
        column: str,
        delimiter: str,
        split_to: str = "columns",
        num_columns: int | None = None,
    ) -> pd.DataFrame:
        """Split a delimited column into rows or columns.

        Args:
            df: The input DataFrame.
            column: Column to split.
            delimiter: String delimiter (literal, not regex).
            split_to: ``"columns"`` or ``"rows"``.
            num_columns: Max number of output columns (only for
                ``split_to="columns"``).

        Returns:
            A new DataFrame with the split data.

        Example:
            >>> df = Parse.text_to_columns(df, "Skills", ",", split_to="columns")
        """
        from etlpipe._config import get_engine

        return get_engine().text_to_columns(df, column, delimiter, split_to, num_columns)

    # ------------------------------------------------------------------ #
    # XML Parse
    # ------------------------------------------------------------------ #
    @staticmethod
    def xml_parse(
        df: pd.DataFrame,
        column: str,
        xpath: str,
        output_column: str = "ParsedXML",
        return_child_values: bool = False,
        return_outer_xml: bool = False,
    ) -> pd.DataFrame:
        """Extract values from XML strings.

        Args:
            df: The input DataFrame.
            column: Column containing XML strings.
            xpath: XPath expression to extract.
            output_column: Name for the extracted-value column(s).
            return_child_values: If True, flattens child tags and attributes
                into separate columns instead of extracting the text of the matched node.
            return_outer_xml: If True, also outputs a column containing the raw
                XML tags and content of the matched node.

        Returns:
            A new DataFrame with the extracted XML data appended.

        Example:
            >>> df = Parse.xml_parse(df, "XMLData", ".//Person", "Person", return_child_values=True)
        """
        from etlpipe._config import get_engine

        return get_engine().xml_parse(df, column, xpath, output_column, return_child_values, return_outer_xml)
