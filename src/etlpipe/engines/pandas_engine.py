"""Pandas backend engine implementation for etlpipe.

Wraps the original pandas execution logic for all 55 tool functions.
"""

from __future__ import annotations

import base64
import difflib
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from datetime import datetime
from functools import reduce
from pathlib import Path
from typing import Any

import defusedxml.ElementTree as ET  # XXE-safe XML parsing
import pandas as pd

from etlpipe._validators import validate_columns, validate_dataframe
from etlpipe.engines.base import BackendEngine

logger = logging.getLogger("etlpipe.engines.pandas")


class PandasEngine(BackendEngine):
    """Concrete backend engine executing operations using standard Pandas."""

    @property
    def name(self) -> str:
        return "pandas"

    def _log_operation(
        self, method: str, input_df: pd.DataFrame | None = None, output_df: pd.DataFrame | None = None
    ) -> None:
        log_data = {"backend": "pandas", "tool": method, "timestamp": datetime.now().isoformat()}
        if input_df is not None and isinstance(input_df, pd.DataFrame):
            log_data["input_rows"] = len(input_df)
        if output_df is not None and isinstance(output_df, pd.DataFrame):
            log_data["output_rows"] = len(output_df)

        logger.debug(json.dumps(log_data))

    # ================================================================== #
    #  Preparation Palette
    # ================================================================== #

    def filter(
        self,
        df: pd.DataFrame,
        condition: str | Callable[[pd.DataFrame], pd.Series] | None = None,
        *,
        column: str | None = None,
        operator: str | None = None,
        value: Any = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        validate_dataframe(df)

        if condition is not None:
            mask = condition(df) if callable(condition) else df.eval(condition)
        elif column is not None and operator is not None:
            validate_columns(df, column)
            op = operator.lower().strip()
            series = df[column]

            if op in ("=", "==", "equals"):
                mask = series == value
            elif op in ("!=", "does not equal"):
                mask = series != value
            elif op == ">":
                mask = series > value
            elif op == ">=":
                mask = series >= value
            elif op == "<":
                mask = series < value
            elif op == "<=":
                mask = series <= value
            elif op == "is null":
                mask = series.isna()
            elif op == "is not null":
                mask = series.notna()
            elif op == "is empty":
                mask = series.isna() | (series == "")
            elif op == "is not empty":
                mask = series.notna() & (series != "")
            elif op == "contains":
                mask = series.astype(str).str.contains(str(value), regex=False, na=False)
            elif op == "does not contain":
                mask = ~series.astype(str).str.contains(str(value), regex=False, na=False)
            elif op == "is true":
                mask = series.eq(True)
            elif op == "is false":
                mask = series.eq(False)
            else:
                raise ValueError(f"Unsupported filter operator: {operator}")
        else:
            raise ValueError("Must provide either 'condition' or both 'column' and 'operator'.")

        true_df = df.loc[mask].reset_index(drop=True)
        false_df = df.loc[~mask].reset_index(drop=True)
        self._log_operation("Preparation.filter", df, true_df)
        return true_df, false_df

    def formula(
        self,
        df: pd.DataFrame,
        column: str,
        expression: str | Callable[[pd.DataFrame], pd.Series],
    ) -> pd.DataFrame:
        validate_dataframe(df)
        out = df.copy()

        if callable(expression):
            out[column] = expression(out)
        else:
            if isinstance(expression, str):
                for c in df.columns:
                    if " " in c and c in expression and f"`{c}`" not in expression:
                        expression = expression.replace(c, f"`{c}`")
            try:
                out[column] = out.eval(expression)
            except Exception as e:
                raise ValueError(
                    f"Could not safely evaluate formula: '{expression}'. "
                    f"Pandas eval failed with: {e}. "
                    "For complex string logic, pass a lambda callable instead."
                ) from e

        self._log_operation("Preparation.formula", df, out)
        return out

    def select(
        self,
        df: pd.DataFrame,
        columns: Sequence[str] | None = None,
        renames: dict[str, str] | None = None,
        dtypes: dict[str, str | type] | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        out = df.copy()

        if columns is not None:
            validate_columns(out, columns)
            out = out[list(columns)]

        if renames:
            out = out.rename(columns=renames)

        if dtypes:
            out = out.astype(dtypes)

        self._log_operation("Preparation.select", df, out)
        return out

    def data_cleansing(
        self,
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
        validate_dataframe(df)
        out = df.copy()

        if columns is None:
            columns = list(out.select_dtypes(include=["object", "string"]).columns)
        else:
            columns = validate_columns(out, columns)

        if remove_null_rows:
            out = out.dropna(subset=columns).reset_index(drop=True)

        if replace_nulls_with is not None:
            out[columns] = out[columns].fillna(replace_nulls_with)

        for col in columns:
            if out[col].dtype == object or pd.api.types.is_string_dtype(out[col]):
                # Preserve NaN values: save the null mask before str operations
                # to prevent .astype(str) from converting NaN â†’ "nan"
                null_mask = out[col].isna()
                if strip_whitespace:
                    out[col] = out[col].astype(str).str.strip()
                if remove_letters:
                    out[col] = out[col].astype(str).str.replace(r"[A-Za-z]", "", regex=True)
                if remove_numbers:
                    out[col] = out[col].astype(str).str.replace(r"\d", "", regex=True)
                if remove_punctuation:
                    out[col] = out[col].astype(str).str.replace(r"[^\w\s]", "", regex=True)
                if modify_case == "lower":
                    out[col] = out[col].astype(str).str.lower()
                elif modify_case == "upper":
                    out[col] = out[col].astype(str).str.upper()
                elif modify_case == "title":
                    out[col] = out[col].astype(str).str.title()
                # Restore original NaN values that were corrupted by .astype(str)
                out.loc[null_mask, col] = None

        self._log_operation("Preparation.data_cleansing", df, out)
        return out

    def sort(
        self,
        df: pd.DataFrame,
        columns: str | Sequence[str],
        ascending: bool | Sequence[bool] = True,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        cols = validate_columns(df, columns)
        out = df.sort_values(by=cols, ascending=ascending).reset_index(drop=True)
        self._log_operation("Preparation.sort", df, out)
        return out

    def unique(
        self,
        df: pd.DataFrame,
        columns: str | Sequence[str],
        ignore_case: bool = False,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        validate_dataframe(df)
        cols = validate_columns(df, columns)

        compare_df = df[cols].copy()
        if ignore_case:
            for col in cols:
                if pd.api.types.is_string_dtype(compare_df[col]) or compare_df[col].dtype == object:
                    compare_df[col] = compare_df[col].astype(str).str.lower()

        is_dup = compare_df.duplicated(keep="first")
        unique_df = df.loc[~is_dup].reset_index(drop=True)
        duplicate_df = df.loc[is_dup].reset_index(drop=True)
        self._log_operation("Preparation.unique", df, unique_df)
        return unique_df, duplicate_df

    def sample(
        self,
        df: pd.DataFrame,
        n: int | None = None,
        pct: float | None = None,
        random: bool = False,
        position: str = "first",
        random_state: int | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)

        if n is not None and pct is not None:
            raise ValueError("Specify either 'n' or 'pct', not both.")
        if n is None and pct is None:
            raise ValueError("Specify either 'n' or 'pct'.")

        if pct is not None:
            n = max(1, int(len(df) * pct))

        if random:
            out = df.sample(n=min(n, len(df)), random_state=random_state).reset_index(drop=True)
        elif position == "last":
            out = df.tail(n).reset_index(drop=True)
        else:
            out = df.head(n).reset_index(drop=True)

        self._log_operation("Preparation.sample", df, out)
        return out

    def record_id(
        self,
        df: pd.DataFrame,
        column_name: str = "RecordID",
        start: int = 1,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        out = df.copy()
        out.insert(0, column_name, range(start, start + len(df)))
        self._log_operation("Preparation.record_id", df, out)
        return out

    def generate_rows(
        self,
        count: int,
        expression: Callable[[int], dict[str, Any]] | None = None,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        if expression is None:
            out = pd.DataFrame({"RowNum": range(count)})
        else:
            rows = [expression(i) for i in range(count)]
            out = pd.DataFrame(rows)

        if columns is not None:
            out = out[list(columns)]

        self._log_operation("Preparation.generate_rows", None, out)
        return out

    def auto_field(self, df: pd.DataFrame) -> pd.DataFrame:
        validate_dataframe(df)
        out = df.copy()

        for col in out.columns:
            col_data = out[col]

            if pd.api.types.is_integer_dtype(col_data):
                out[col] = pd.to_numeric(col_data, downcast="integer")
            elif pd.api.types.is_float_dtype(col_data):
                out[col] = pd.to_numeric(col_data, downcast="float")
            elif not pd.api.types.is_numeric_dtype(col_data):
                n_unique = col_data.nunique()
                if n_unique > 0 and n_unique / len(col_data) < 0.5:
                    out[col] = col_data.astype("category")

        self._log_operation("Preparation.auto_field", df, out)
        return out

    def multi_field_formula(
        self,
        df: pd.DataFrame,
        columns: Sequence[str],
        expression: Callable[[pd.Series], pd.Series],
    ) -> pd.DataFrame:
        validate_dataframe(df)
        cols = validate_columns(df, columns)
        out = df.copy()

        for col in cols:
            out[col] = expression(out[col])

        self._log_operation("Preparation.multi_field_formula", df, out)
        return out

    def multi_row_formula(
        self,
        df: pd.DataFrame,
        column: str,
        expression: Callable[[pd.Series, pd.Series], pd.Series],
        rows_back: int = 1,
        group_by: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()

        if group_by is not None:
            group_cols = validate_columns(df, group_by)
            shifted = out.groupby(group_cols)[column].shift(rows_back)
        else:
            shifted = out[column].shift(rows_back)

        out[column] = expression(out[column], shifted)
        self._log_operation("Preparation.multi_row_formula", df, out)
        return out

    def tile(
        self,
        df: pd.DataFrame,
        column: str,
        n_tiles: int,
        method: str = "equal_records",
        output_column: str = "Tile",
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()

        if method == "equal_records":
            out[output_column] = pd.qcut(out[column], q=n_tiles, labels=range(1, n_tiles + 1), duplicates="drop")
        elif method == "equal_range":
            out[output_column] = pd.cut(out[column], bins=n_tiles, labels=range(1, n_tiles + 1))
        else:
            raise ValueError(f"Unknown method '{method}'. Use 'equal_records' or 'equal_range'.")

        self._log_operation("Preparation.tile", df, out)
        return out

    def imputation(
        self,
        df: pd.DataFrame,
        columns: str | Sequence[str],
        method: str = "mean",
        replacement_value: Any | None = None,
        add_indicator: bool = True,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        cols = validate_columns(df, columns)
        out = df.copy()

        for col in cols:
            null_mask = out[col].isna()

            if add_indicator:
                out[f"{col}_WasImputed"] = null_mask

            if method == "mean":
                fill = out[col].mean()
            elif method == "median":
                fill = out[col].median()
            elif method == "mode":
                mode_vals = out[col].mode()
                fill = mode_vals.iloc[0] if len(mode_vals) > 0 else None
            elif method == "value":
                if replacement_value is None:
                    raise ValueError("'replacement_value' is required when method='value'.")
                fill = replacement_value
            else:
                raise ValueError(f"Unknown method '{method}'. Use 'mean', 'median', 'mode', or 'value'.")

            if fill is not None and not pd.isna(fill):
                out[col] = out[col].fillna(fill)

        self._log_operation("Preparation.imputation", df, out)
        return out

    def create_samples(
        self,
        df: pd.DataFrame,
        estimation_pct: float,
        validation_pct: float,
        holdout_pct: float,
        random_state: int | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        validate_dataframe(df)
        if round(estimation_pct + validation_pct + holdout_pct, 5) != 1.0:
            raise ValueError("Percentages must sum to 1.0")

        shuffled = df.sample(frac=1.0, random_state=random_state).reset_index(drop=True)
        n = len(shuffled)
        n_est = int(n * estimation_pct)
        n_val = int(n * validation_pct)

        est_df = shuffled.iloc[:n_est].reset_index(drop=True)
        val_df = shuffled.iloc[n_est : n_est + n_val].reset_index(drop=True)
        hold_df = shuffled.iloc[n_est + n_val :].reset_index(drop=True)

        self._log_operation("Preparation.create_samples", df, None)
        return est_df, val_df, hold_df

    def date_filter(
        self,
        df: pd.DataFrame,
        column: str,
        start_date: str | pd.Timestamp | None = None,
        end_date: str | pd.Timestamp | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        validate_dataframe(df)
        validate_columns(df, column)

        col_data = pd.to_datetime(df[column])
        mask = pd.Series(True, index=df.index)

        if start_date is not None:
            mask &= col_data >= pd.to_datetime(start_date)
        if end_date is not None:
            mask &= col_data <= pd.to_datetime(end_date)

        true_df = df.loc[mask].reset_index(drop=True)
        false_df = df.loc[~mask].reset_index(drop=True)

        self._log_operation("Preparation.date_filter", df, true_df)
        return true_df, false_df

    def oversample_field(
        self,
        df: pd.DataFrame,
        column: str,
        value: Any,
        target_pct: float = 0.5,
        random_state: int | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)

        is_target = df[column] == value
        target_df = df[is_target]
        other_df = df[~is_target]

        if len(target_df) == 0 or len(other_df) == 0:
            self._log_operation("Preparation.oversample_field", df, df)
            return df.copy()

        if target_pct >= 1.0 or target_pct <= 0.0:
            raise ValueError("target_pct must be strictly between 0.0 and 1.0")

        n_target = int(len(other_df) * (target_pct / (1.0 - target_pct)))

        target_sampled = target_df.sample(n=n_target, replace=True, random_state=random_state)
        out = pd.concat([target_sampled, other_df], ignore_index=True)
        out = out.sample(frac=1.0, random_state=random_state).reset_index(drop=True)
        self._log_operation("Preparation.oversample_field", df, out)
        return out

    def rank(
        self,
        df: pd.DataFrame,
        column: str,
        group_by: str | Sequence[str] | None = None,
        ascending: bool = False,
        method: str = "min",
        output_column: str = "Rank",
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()

        if group_by is not None:
            group_cols = validate_columns(df, group_by)
            grouper = out.groupby(group_cols)
            ranks = grouper[column].rank(method=method, ascending=ascending)
        else:
            ranks = out[column].rank(method=method, ascending=ascending)

        out[output_column] = ranks.astype(int) if method in ("min", "dense", "first", "max") else ranks
        self._log_operation("Preparation.rank", df, out)
        return out

    # ================================================================== #
    #  Join Palette
    # ================================================================== #

    def join(
        self,
        left: pd.DataFrame,
        right: pd.DataFrame,
        on: str | Sequence[str] | None = None,
        left_on: str | Sequence[str] | None = None,
        right_on: str | Sequence[str] | None = None,
        suffixes: tuple[str, str] = ("_left", "_right"),
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        validate_dataframe(left, "left")
        validate_dataframe(right, "right")

        # Copy inputs to avoid mutating caller's DataFrames during dtype coercion
        left = left.copy()
        right = right.copy()

        # Cast Right join keys to match Left join keys to prevent type mismatch failures
        if on:
            on_list = [on] if isinstance(on, str) else on
            for key in on_list:
                left_type = left[key].dtype
                right_type = right[key].dtype
                if left_type != right_type:
                    right[key] = right[key].astype(left_type)
        else:
            left_list = [left_on] if isinstance(left_on, str) else left_on
            right_list = [right_on] if isinstance(right_on, str) else right_on
            for l_key, r_key in zip(left_list, right_list, strict=False):
                left_type = left[l_key].dtype
                right_type = right[r_key].dtype
                if left_type != right_type:
                    right[r_key] = right[r_key].astype(left_type)

        left_temp = left.copy()
        right_temp = right.copy()
        left_temp["_fs_left_idx_"] = range(len(left_temp))
        right_temp["_fs_right_idx_"] = range(len(right_temp))

        merged = pd.merge(
            left_temp,
            right_temp,
            how="outer",
            on=on,
            left_on=left_on,
            right_on=right_on,
            suffixes=suffixes,
            indicator=True,
        )

        joined = (
            merged.loc[merged["_merge"] == "both"]
            .drop(columns=["_fs_left_idx_", "_fs_right_idx_", "_merge"])
            .reset_index(drop=True)
        )
        left_only_idx = merged.loc[merged["_merge"] == "left_only", "_fs_left_idx_"].dropna().astype(int)
        right_only_idx = merged.loc[merged["_merge"] == "right_only", "_fs_right_idx_"].dropna().astype(int)

        left_unjoined = left.iloc[left_only_idx].reset_index(drop=True)
        right_unjoined = right.iloc[right_only_idx].reset_index(drop=True)

        self._log_operation("Join.join", left, joined)
        return left_unjoined, joined, right_unjoined

    def join_multiple(
        self,
        *dfs: pd.DataFrame,
        on: str | Sequence[str] | None = None,
        join_type: str = "outer",
    ) -> pd.DataFrame:
        if len(dfs) < 2:
            raise ValueError("join_multiple requires at least 2 DataFrames.")
        for i, d in enumerate(dfs):
            validate_dataframe(d, f"dfs[{i}]")

        def _merge_pair(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
            return pd.merge(left, right, on=on, how=join_type, suffixes=("", f"_dup_{id(right)}"))

        out = reduce(_merge_pair, dfs).reset_index(drop=True)
        self._log_operation("Join.join_multiple", None, out)
        return out

    def union(
        self,
        *dfs: pd.DataFrame,
        by: str = "name",
    ) -> pd.DataFrame:
        if len(dfs) < 2:
            raise ValueError("union requires at least 2 DataFrames.")
        for i, d in enumerate(dfs):
            validate_dataframe(d, f"dfs[{i}]")

        if by == "position":
            reference_cols = list(dfs[0].columns)
            renamed = []
            for d in dfs:
                d_copy = d.copy()
                d_copy.columns = reference_cols[: len(d_copy.columns)]
                renamed.append(d_copy)
            out = pd.concat(renamed, ignore_index=True)
        else:
            out = pd.concat(dfs, ignore_index=True)

        self._log_operation("Join.union", None, out)
        return out

    def find_replace(
        self,
        df: pd.DataFrame,
        find_df: pd.DataFrame,
        find_col: str,
        replace_col: str,
        target_col: str | None = None,
        mode: str = "entire",
        append: bool = False,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_dataframe(find_df, "find_df")

        if target_col is None:
            target_col = find_col
        validate_columns(df, target_col, "target_col")

        out = df.copy()
        lookup = dict(zip(find_df[find_col], find_df[replace_col], strict=False))

        if append:
            new_col = replace_col
            if new_col in out.columns:
                new_col = f"{new_col}_found"

            if mode == "entire":
                out[new_col] = out[target_col].map(lambda v: lookup.get(v))
            elif mode == "partial":
                out[new_col] = None
                for find_val, replace_val in lookup.items():
                    mask = out[target_col].astype(str).str.contains(str(find_val), regex=False) & out[new_col].isna()
                    out.loc[mask, new_col] = replace_val
        else:
            if mode == "entire":
                out[target_col] = out[target_col].map(lambda v: lookup.get(v, v))
            elif mode == "partial":
                for find_val, replace_val in lookup.items():
                    out[target_col] = (
                        out[target_col].astype(str).str.replace(str(find_val), str(replace_val), regex=False)
                    )
            else:
                raise ValueError(f"Unknown mode '{mode}'. Use 'entire' or 'partial'.")

        self._log_operation("Join.find_replace", df, out)
        return out

    def append_fields(self, left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
        validate_dataframe(left, "left")
        validate_dataframe(right, "right")

        left_temp = left.copy()
        right_temp = right.copy()
        left_temp["_fs_cross_"] = 1
        right_temp["_fs_cross_"] = 1

        result = pd.merge(left_temp, right_temp, on="_fs_cross_", suffixes=("_left", "_right"))
        out = result.drop(columns=["_fs_cross_"]).reset_index(drop=True)
        self._log_operation("Join.append_fields", left, out)
        return out

    def fuzzy_match(
        self,
        left: pd.DataFrame,
        right: pd.DataFrame,
        left_on: str,
        right_on: str,
        threshold: float = 0.6,
        score_column: str = "MatchScore",
    ) -> pd.DataFrame:
        validate_dataframe(left, "left")
        validate_dataframe(right, "right")
        validate_columns(left, left_on, "left_on")
        validate_columns(right, right_on, "right_on")

        rows: list[dict] = []
        for l_idx, l_val in left[left_on].items():
            l_str = str(l_val)
            for r_idx, r_val in right[right_on].items():
                r_str = str(r_val)
                score = difflib.SequenceMatcher(None, l_str, r_str).ratio()
                if score >= threshold:
                    row = {}
                    for col in left.columns:
                        row[f"{col}_left"] = left.at[l_idx, col]
                    for col in right.columns:
                        row[f"{col}_right"] = right.at[r_idx, col]
                    row[score_column] = round(score, 4)
                    rows.append(row)

        out = pd.DataFrame(rows)
        self._log_operation("Join.fuzzy_match", left, out)
        return out

    def make_group(self, df: pd.DataFrame, key1: str, key2: str) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, [key1, key2])

        from collections import defaultdict

        graph = defaultdict(set)

        for _, row in df.iterrows():
            k1 = row[key1]
            k2 = row[key2]
            if pd.notna(k1) and pd.notna(k2):
                graph[k1].add(k2)
                graph[k2].add(k1)
            elif pd.notna(k1):
                graph[k1].add(k1)
            elif pd.notna(k2):
                graph[k2].add(k2)

        visited = set()
        components = []

        for node in graph:
            if node not in visited:
                comp = []
                stack = [node]
                while stack:
                    curr = stack.pop()
                    if curr not in visited:
                        visited.add(curr)
                        comp.append(curr)
                        for neighbor in graph[curr]:
                            if neighbor not in visited:
                                stack.append(neighbor)
                components.append(comp)

        records = []
        for comp in components:
            group_id = min(comp, key=lambda x: str(x))
            for key in comp:
                records.append({"Group": group_id, "Key": key})

        out = pd.DataFrame(records, columns=["Group", "Key"])
        if not out.empty:
            out = out.sort_values(by=["Group", "Key"]).reset_index(drop=True)

        self._log_operation("Join.make_group", df, out)
        return out

    # ================================================================== #
    #  Transform Palette
    # ================================================================== #

    @staticmethod
    def _resolve_aggregation(agg_name: str | Callable) -> str | Callable:
        if not isinstance(agg_name, str):
            return agg_name

        agg = agg_name.lower().strip()

        if agg in ("count distinct", "count_distinct"):

            def _count_distinct(x):
                return x.nunique()

            _count_distinct.__name__ = "count_distinct"
            return _count_distinct
        if agg in ("count null", "count_null"):

            def _count_null(x):
                return x.isna().sum()

            _count_null.__name__ = "count_null"
            return _count_null
        if agg in ("count blank", "count_blank"):

            def _count_blank(x):
                return (x.dropna().astype(str).str.strip() == "").sum()

            _count_blank.__name__ = "count_blank"
            return _count_blank
        if agg in ("count non blank", "count_non_blank"):

            def _count_non_blank(x):
                return (x.dropna().astype(str).str.strip() != "").sum()

            _count_non_blank.__name__ = "count_non_blank"
            return _count_non_blank
        if agg in ("concatenate", "concat", "concatenate distinct", "concat_distinct"):
            is_distinct = "distinct" in agg

            def _concat(x):
                vals = x.dropna().astype(str)
                if is_distinct:
                    vals = pd.Series(list(dict.fromkeys(vals)))
                return ",".join(vals)

            _concat.__name__ = agg.replace(" ", "_")
            return _concat
        if agg == "longest":

            def _longest(x):
                s = x.dropna().astype(str)
                return s.loc[s.str.len().idxmax()] if not s.empty else pd.NA

            _longest.__name__ = "longest"
            return _longest
        if agg == "shortest":

            def _shortest(x):
                s = x.dropna().astype(str)
                return s.loc[s.str.len().idxmin()] if not s.empty else pd.NA

            _shortest.__name__ = "shortest"
            return _shortest
        if agg == "mode":

            def _mode(x):
                m = x.dropna().mode()
                return m.iloc[0] if not m.empty else pd.NA

            _mode.__name__ = "mode"
            return _mode

        return agg_name

    def summarize(
        self,
        df: pd.DataFrame,
        group_by: str | Sequence[str] | None = None,
        aggregations: dict[str, str | list[str]] | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)

        if aggregations is None:
            raise ValueError("Must provide at least one aggregation.")

        resolved_aggs = {}
        for col, aggs in aggregations.items():
            if isinstance(aggs, list):
                resolved_aggs[col] = [self._resolve_aggregation(a) for a in aggs]
            else:
                resolved_aggs[col] = self._resolve_aggregation(aggs)

        if group_by is not None:
            group_cols = validate_columns(df, group_by)
            grouped = df.groupby(group_cols, as_index=False)
        else:
            temp = df.copy()
            if temp.empty:
                temp.loc[0, "_fs_group_"] = 1
            else:
                temp["_fs_group_"] = 1
            grouped = temp.groupby("_fs_group_", as_index=False)

        norm_aggs = {}
        for col, funcs in resolved_aggs.items():
            if not isinstance(funcs, list):
                norm_aggs[col] = [funcs]
            else:
                norm_aggs[col] = list(funcs)

        result = grouped.agg(norm_aggs)

        if isinstance(result.columns, pd.MultiIndex):
            new_cols = []
            for col_top, col_agg in result.columns:
                if col_agg == "":
                    new_cols.append(col_top)
                else:
                    new_cols.append(f"{col_agg.capitalize()}_{col_top}")
            result.columns = new_cols

        if group_by is None and "_fs_group_" in result.columns:
            result = result.drop(columns=["_fs_group_"])

        out = result.reset_index(drop=True)
        self._log_operation("Transform.summarize", df, out)
        return out

    def transpose(
        self,
        df: pd.DataFrame,
        key_columns: str | Sequence[str],
        data_columns: str | Sequence[str] | None = None,
        var_name: str = "Name",
        value_name: str = "Value",
    ) -> pd.DataFrame:
        validate_dataframe(df)
        id_vars = validate_columns(df, key_columns)

        if data_columns is not None:
            value_vars = validate_columns(df, data_columns)
        else:
            value_vars = [c for c in df.columns if c not in id_vars]

        out = pd.melt(
            df,
            id_vars=id_vars,
            value_vars=value_vars,
            var_name=var_name,
            value_name=value_name,
        ).reset_index(drop=True)
        self._log_operation("Transform.transpose", df, out)
        return out

    def cross_tab(
        self,
        df: pd.DataFrame,
        group_by: str | Sequence[str],
        pivot_col: str,
        value_col: str,
        agg: str = "sum",
    ) -> pd.DataFrame:
        validate_dataframe(df)
        idx = validate_columns(df, group_by)
        validate_columns(df, pivot_col)
        validate_columns(df, value_col)

        aggfunc = self._resolve_aggregation(agg)

        result = pd.pivot_table(
            df,
            index=idx,
            columns=pivot_col,
            values=value_col,
            aggfunc=aggfunc,
            fill_value=0,
        )

        result = result.reset_index()
        result.columns.name = None
        self._log_operation("Transform.cross_tab", df, result)
        return result

    def running_total(
        self,
        df: pd.DataFrame,
        column: str,
        group_by: str | Sequence[str] | None = None,
        output_column: str | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()
        out_col = output_column or f"RunningTotal_{column}"

        if group_by is not None:
            group_cols = validate_columns(df, group_by)
            out[out_col] = out.groupby(group_cols)[column].cumsum()
        else:
            out[out_col] = out[column].cumsum()

        self._log_operation("Transform.running_total", df, out)
        return out

    def count_records(
        self,
        df: pd.DataFrame,
        output_col: str = "Count",
    ) -> pd.DataFrame:
        validate_dataframe(df)
        out = pd.DataFrame({output_col: [len(df)]})
        self._log_operation("Transform.count_records", df, out)
        return out

    def arrange(
        self,
        df: pd.DataFrame,
        key_columns: str | Sequence[str] | None = None,
        output_mapping: dict[str, Sequence[str]] | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)

        if output_mapping is None or not output_mapping:
            return df.copy()

        keys = validate_columns(df, key_columns) if key_columns else []

        lengths = {len(v) for v in output_mapping.values()}
        if len(lengths) > 1:
            raise ValueError("All lists in output_mapping must have the same length.")

        n_rows = list(lengths)[0]

        chunks = []
        for i in range(n_rows):
            chunk = df[keys].copy() if keys else pd.DataFrame(index=df.index)
            for out_col, in_cols in output_mapping.items():
                in_col = in_cols[i]
                chunk[out_col] = df[in_col]
            chunks.append(chunk)

        out = pd.concat(chunks, ignore_index=True)
        if keys:
            out = out.sort_values(by=keys, kind="stable").reset_index(drop=True)

        self._log_operation("Transform.arrange", df, out)
        return out

    def make_columns(
        self,
        df: pd.DataFrame,
        num_columns: int,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        if num_columns < 1:
            raise ValueError("num_columns must be at least 1")
        if num_columns == 1 or len(df) == 0:
            return df.copy()

        out_chunks = []
        for i in range(num_columns):
            chunk = df.iloc[i::num_columns].reset_index(drop=True)
            chunk = chunk.add_suffix(f"_{i + 1}")
            out_chunks.append(chunk)

        out = pd.concat(out_chunks, axis=1)
        self._log_operation("Transform.make_columns", df, out)
        return out

    def weighted_average(
        self,
        df: pd.DataFrame,
        value_column: str,
        weight_column: str,
        group_by: str | Sequence[str] | None = None,
        output_column: str = "WeightedAverage",
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, value_column)
        validate_columns(df, weight_column)

        out = df.copy()
        out["_fs_wa_prod"] = out[value_column] * out[weight_column]

        if group_by is not None:
            group_cols = validate_columns(df, group_by)
            grouped = out.groupby(group_cols, as_index=False)
            sums = grouped[["_fs_wa_prod", weight_column]].sum()
            sums[output_column] = sums["_fs_wa_prod"] / sums[weight_column]
            result = sums.drop(columns=["_fs_wa_prod", weight_column])
        else:
            total_prod = out["_fs_wa_prod"].sum()
            total_weight = out[weight_column].sum()
            wa = total_prod / total_weight if total_weight != 0 else pd.NA
            result = pd.DataFrame({output_column: [wa]})

        self._log_operation("Transform.weighted_average", df, result)
        return result

    # ================================================================== #
    #  In/Out Palette
    # ================================================================== #

    def input_data(self, path: str | Path, **kwargs: Any) -> pd.DataFrame:
        from etlpipe.in_out import _READERS

        str_path = str(path)

        # Cloud storage support via fsspec (s3://, gs://, abfs://, etc.)
        if "://" in str_path:
            try:
                import fsspec  # noqa: F401
            except ImportError:
                raise ImportError(
                    f"Cloud path '{str_path}' requires the fsspec package. "
                    "Install cloud support with: pip install etlpipe[cloud]"
                ) from None
            # Extract extension from cloud path
            ext = "." + str_path.rsplit(".", 1)[-1].lower() if "." in str_path.split("/")[-1] else ""
            reader_name = _READERS.get(ext)
            if reader_name is None:
                raise ValueError(f"Unsupported file extension '{ext}'. Supported: {sorted(_READERS.keys())}")
            reader = getattr(pd, reader_name)
            result = reader(str_path, **kwargs)
            if isinstance(result, list):
                result = result[0]
            self._log_operation("InOut.input_data", None, result)
            return result

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        reader_name = _READERS.get(ext)
        if reader_name is None:
            raise ValueError(f"Unsupported file extension '{ext}'. Supported: {sorted(_READERS.keys())}")

        reader = getattr(pd, reader_name)

        if ext == ".tsv" and "sep" not in kwargs:
            kwargs["sep"] = "\t"

        if ext in (".csv", ".tsv") and "engine" not in kwargs:
            try:
                import pyarrow  # noqa: F401

                kwargs["engine"] = "pyarrow"
            except ImportError:
                if path.stat().st_size > 100 * 1024 * 1024:  # 100 MB
                    logger.warning(
                        f"Loading large file ({path.name}) with default pandas C engine. "
                        "Install pyarrow (`pip install pyarrow`) or switch to the Spark backend "
                        "to prevent MemoryErrors."
                    )

        result = reader(path, **kwargs)
        if isinstance(result, list):
            result = result[0]

        self._log_operation("InOut.input_data", None, result)
        return result

    def output_data(self, df: pd.DataFrame, path: str | Path, **kwargs: Any) -> None:
        from etlpipe.in_out import _WRITERS

        validate_dataframe(df)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        ext = path.suffix.lower()
        writer_name = _WRITERS.get(ext)
        if writer_name is None:
            raise ValueError(f"Unsupported file extension '{ext}'. Supported: {sorted(_WRITERS.keys())}")

        writer = getattr(df, writer_name)

        if ext in {".csv", ".tsv"} and "index" not in kwargs:
            kwargs["index"] = False
        if ext == ".tsv" and "sep" not in kwargs:
            kwargs["sep"] = "\t"

        writer(path, **kwargs)
        self._log_operation("InOut.output_data", df, None)

    def text_input(
        self,
        data: dict[str, list] | list[dict] | list[list | tuple],
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        if isinstance(data, dict) or isinstance(data, list) and data and isinstance(data[0], dict):
            out = pd.DataFrame(data)
        elif isinstance(data, list):
            if columns is None:
                raise ValueError("When 'data' is a list of lists/tuples, 'columns' must be provided.")
            out = pd.DataFrame(data, columns=columns)
        else:
            raise TypeError(f"Unsupported data type: {type(data).__name__}")

        self._log_operation("InOut.text_input", None, out)
        return out

    def browse(self, df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
        validate_dataframe(df)

        print("=" * 60)
        print(f"Shape: {df.shape[0]} rows Ã— {df.shape[1]} columns")
        print("-" * 60)

        info_df = pd.DataFrame(
            {
                "Column": df.columns,
                "Type": [str(dt) for dt in df.dtypes],
                "Non-Null": [df[c].notna().sum() for c in df.columns],
                "Null": [df[c].isna().sum() for c in df.columns],
                "Unique": [df[c].nunique() for c in df.columns],
            }
        )
        print(info_df.to_string(index=False))

        print("-" * 60)
        print("Descriptive Statistics:")
        print(df.describe(include="all").to_string())
        print("-" * 60)
        print(f"First {n} rows:")
        print(df.head(n).to_string(index=False))
        print("=" * 60)

        self._log_operation("InOut.browse", df, df)
        return df

    def directory(self, path: str | Path, pattern: str = "*") -> pd.DataFrame:
        path = Path(path)
        if not path.is_dir():
            raise FileNotFoundError(f"Directory not found: {path}")

        rows: list[dict[str, Any]] = []
        for entry in sorted(path.glob(pattern)):
            if entry.is_file():
                stat = entry.stat()
                rows.append(
                    {
                        "FullPath": str(entry.resolve()),
                        "Directory": str(entry.parent.resolve()),
                        "FileName": entry.name,
                        "ShortFileName": entry.stem,
                        "CreationTime": datetime.fromtimestamp(stat.st_ctime),
                        "LastWriteTime": datetime.fromtimestamp(stat.st_mtime),
                        "LastAccessTime": datetime.fromtimestamp(stat.st_atime),
                        "Size": stat.st_size,
                    }
                )

        out = pd.DataFrame(
            rows,
            columns=[
                "FullPath",
                "Directory",
                "FileName",
                "ShortFileName",
                "CreationTime",
                "LastWriteTime",
                "LastAccessTime",
                "Size",
            ],
        )
        self._log_operation("InOut.directory", None, out)
        return out

    def date_time_now(self) -> pd.DataFrame:
        out = pd.DataFrame({"DateTime": [datetime.now()]})
        self._log_operation("InOut.date_time_now", None, out)
        return out

    # ================================================================== #
    #  Parse Palette
    # ================================================================== #

    def date_time(
        self,
        df: pd.DataFrame,
        column: str,
        input_fmt: str | None = None,
        output_fmt: str | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()

        if input_fmt:
            out[column] = pd.to_datetime(out[column], format=input_fmt)
        else:
            out[column] = pd.to_datetime(out[column])

        if output_fmt:
            out[column] = out[column].dt.strftime(output_fmt)

        self._log_operation("Parse.date_time", df, out)
        return out

    def regex_match(
        self,
        df: pd.DataFrame,
        column: str,
        pattern: str,
        output_column: str = "Match",
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()
        out[output_column] = out[column].astype(str).str.contains(pattern, regex=True, na=False)
        self._log_operation("Parse.regex_match", df, out)
        return out

    def regex_parse(
        self,
        df: pd.DataFrame,
        column: str,
        pattern: str,
        output_cols: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()

        extracted = out[column].astype(str).str.extract(pattern)

        if output_cols is not None:
            if len(output_cols) != extracted.shape[1]:
                raise ValueError(f"Expected {extracted.shape[1]} output column names, got {len(output_cols)}.")
            extracted.columns = output_cols
        else:
            extracted.columns = [f"Group_{i + 1}" for i in range(extracted.shape[1])]

        out = pd.concat([out, extracted], axis=1)
        self._log_operation("Parse.regex_parse", df, out)
        return out

    def regex_replace(
        self,
        df: pd.DataFrame,
        column: str,
        pattern: str,
        replacement: str,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()
        out[column] = out[column].astype(str).str.replace(pattern, replacement, regex=True)
        self._log_operation("Parse.regex_replace", df, out)
        return out

    def regex_tokenize(
        self,
        df: pd.DataFrame,
        column: str,
        pattern: str,
        split_to: str = "rows",
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()

        if split_to == "rows":
            out[column] = out[column].astype(str).str.split(pattern)
            out = out.explode(column).reset_index(drop=True)
        elif split_to == "columns":
            split_df = out[column].astype(str).str.split(pattern, expand=True)
            split_df.columns = [f"{column}_{i + 1}" for i in range(split_df.shape[1])]
            out = pd.concat([out.drop(columns=[column]), split_df], axis=1)
        else:
            raise ValueError(f"Unknown split_to '{split_to}'. Use 'rows' or 'columns'.")

        self._log_operation("Parse.regex_tokenize", df, out)
        return out

    def text_to_columns(
        self,
        df: pd.DataFrame,
        column: str,
        delimiter: str,
        split_to: str = "columns",
        num_columns: int | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()

        if split_to == "rows":
            out[column] = out[column].astype(str).str.split(re.escape(delimiter))
            out = out.explode(column).reset_index(drop=True)
        elif split_to == "columns":
            split_df = (
                out[column]
                .astype(str)
                .str.split(re.escape(delimiter), expand=True, n=num_columns - 1 if num_columns else None)
            )
            split_df.columns = [f"{column}_{i + 1}" for i in range(split_df.shape[1])]
            out = pd.concat([out.drop(columns=[column]), split_df], axis=1)
        else:
            raise ValueError(f"Unknown split_to '{split_to}'. Use 'rows' or 'columns'.")

        self._log_operation("Parse.text_to_columns", df, out)
        return out

    def xml_parse(
        self,
        df: pd.DataFrame,
        column: str,
        xpath: str,
        output_column: str = "ParsedXML",
        return_child_values: bool = False,
        return_outer_xml: bool = False,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()

        def _extract(xml_str: str) -> dict:
            try:
                if not isinstance(xml_str, str):
                    return {}
                root = ET.fromstring(xml_str)
                elem = root.find(xpath)
                if elem is None and root.tag == xpath.lstrip("./"):
                    elem = root

                if elem is None:
                    return {}

                res = {}
                if return_child_values:
                    for k, v in elem.attrib.items():
                        res[f"{output_column}_{k}"] = v
                    for child in elem:
                        res[f"{output_column}_{child.tag}"] = child.text
                else:
                    res[output_column] = elem.text

                if return_outer_xml:
                    res[f"{output_column}_OuterXML"] = ET.tostring(elem, encoding="unicode")

                return res
            except (ET.ParseError, TypeError):
                return {}

        extracted_series = out[column].apply(_extract)
        extracted_df = pd.DataFrame(extracted_series.tolist(), index=out.index)

        if extracted_df.empty:
            if not return_child_values:
                out[output_column] = None
            if return_outer_xml:
                out[f"{output_column}_OuterXML"] = None
        else:
            out = pd.concat([out, extracted_df], axis=1)

        self._log_operation("Parse.xml_parse", df, out)
        return out

    # ================================================================== #
    #  Developer Palette
    # ================================================================== #

    def base64_encode(
        self,
        df: pd.DataFrame,
        column: str,
        output_column: str | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()
        out_col = output_column or f"{column}_Base64"
        out[out_col] = out[column].astype(str).apply(lambda v: base64.b64encode(v.encode("utf-8")).decode("utf-8"))
        self._log_operation("Developer.base64_encode", df, out)
        return out

    def base64_decode(
        self,
        df: pd.DataFrame,
        column: str,
        output_column: str | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)
        out = df.copy()
        out_col = output_column or f"{column}_Decoded"
        out[out_col] = out[column].astype(str).apply(lambda v: base64.b64decode(v.encode("utf-8")).decode("utf-8"))
        self._log_operation("Developer.base64_decode", df, out)
        return out

    def download(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        output_column: str = "DownloadData",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> pd.DataFrame:
        import time

        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"

        for attempt in range(1, max_retries + 1):
            try:
                with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 # nosec B310
                    status_code = response.getcode()
                    if status_code and status_code >= 500:
                        raise urllib.error.URLError(f"Server error: HTTP {status_code}")
                    body = response.read().decode("utf-8")
                break  # Success â€” exit retry loop
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt < max_retries:
                    wait = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(
                        "Download attempt %d/%d failed for '%s': %s. Retrying in %.1fs...",
                        attempt,
                        max_retries,
                        url,
                        e,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "Download failed after %d attempts for '%s': %s",
                        max_retries,
                        url,
                        e,
                    )
                    raise

        try:
            data = json.loads(body)
            if isinstance(data, list):
                out = pd.DataFrame(data)
            elif isinstance(data, dict):
                out = pd.DataFrame([data])
            else:
                out = pd.DataFrame({output_column: [body]})
        except (json.JSONDecodeError, ValueError):
            out = pd.DataFrame({output_column: [body]})

        self._log_operation("Developer.download", None, out)
        return out

    def column_info(self, df: pd.DataFrame) -> pd.DataFrame:
        validate_dataframe(df)

        rows = []
        for col in df.columns:
            rows.append(
                {
                    "Name": col,
                    "Type": str(df[col].dtype),
                    "Size": df[col].memory_usage(deep=True),
                    "NonNullCount": int(df[col].notna().sum()),
                    "NullCount": int(df[col].isna().sum()),
                    "UniqueCount": int(df[col].nunique()),
                }
            )

        out = pd.DataFrame(rows)
        self._log_operation("Developer.column_info", df, out)
        return out

    def dynamic_rename(
        self,
        df: pd.DataFrame,
        rename_df: pd.DataFrame,
        key_col: str = "OldName",
        new_name_col: str = "NewName",
        mode: str = "mapping",
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_dataframe(rename_df, "rename_df")

        if mode == "mapping":
            validate_columns(rename_df, key_col, "key_col")
            validate_columns(rename_df, new_name_col, "new_name_col")
            rename_map = dict(zip(rename_df[key_col], rename_df[new_name_col], strict=False))
            out = df.rename(columns=rename_map)
        elif mode == "prefix":
            prefix = str(rename_df.iloc[0, 0])
            out = df.rename(columns={c: f"{prefix}{c}" for c in df.columns})
        elif mode == "suffix":
            suffix = str(rename_df.iloc[0, 0])
            out = df.rename(columns={c: f"{c}{suffix}" for c in df.columns})
        else:
            raise ValueError(f"Unknown mode '{mode}'. Use 'mapping', 'prefix', or 'suffix'.")

        self._log_operation("Developer.dynamic_rename", df, out)
        return out

    def json_parse(
        self,
        df: pd.DataFrame,
        column: str,
        prefix: str | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)
        validate_columns(df, column)

        out = df.copy()

        def parse_json(val: Any) -> dict:
            if pd.isna(val):
                return {}
            if isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict):
                        return parsed
                    return {"value": parsed}
                except (json.JSONDecodeError, TypeError):
                    return {}
            return {}

        parsed_series = out[column].apply(parse_json)
        parsed_df = pd.json_normalize(parsed_series)

        prefix_str = prefix if prefix is not None else column
        if prefix_str:
            parsed_df = parsed_df.add_prefix(f"{prefix_str}_")

        out = out.drop(columns=[column])
        parsed_df.index = out.index
        out = pd.concat([out, parsed_df], axis=1)

        self._log_operation("Developer.json_parse", df, out)
        return out

    def dynamic_select(
        self,
        df: pd.DataFrame,
        dtype_include: Any | None = None,
        dtype_exclude: Any | None = None,
        pattern: str | None = None,
    ) -> pd.DataFrame:
        validate_dataframe(df)

        out = df
        if dtype_include is not None or dtype_exclude is not None:
            out = out.select_dtypes(include=dtype_include, exclude=dtype_exclude)

        if pattern is not None:
            out = out.filter(regex=pattern)

        self._log_operation("Developer.dynamic_select", df, out)
        return out

    def test(
        self,
        df: pd.DataFrame,
        condition_func: Callable,
        error_msg: str = "Test condition failed",
    ) -> pd.DataFrame:
        validate_dataframe(df)

        if not condition_func(df):
            raise ValueError(error_msg)

        self._log_operation("Developer.test", df, df)
        return df

    def test_equal(
        self,
        df_left: pd.DataFrame,
        df_right: pd.DataFrame,
        **kwargs: Any,
    ) -> None:
        validate_dataframe(df_left)
        validate_dataframe(df_right, "df_right")

        pd.testing.assert_frame_equal(df_left, df_right, **kwargs)
        self._log_operation("Developer.test_equal", df_left, None)
