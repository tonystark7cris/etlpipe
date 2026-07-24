from __future__ import annotations

import abc
from collections.abc import Callable, Sequence
from typing import Any


class BackendEngine(abc.ABC):
    """Abstract base class for etlpipe backend engines."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the backend engine."""
        pass

    def _log_operation(self, method: str, input_df: Any = None, output_df: Any = None) -> Any:  # noqa: B027
        pass

    def _not_implemented(self, method_name: str) -> None:
        """Raise NotImplementedError with a clear message for unimplemented methods."""
        raise NotImplementedError(
            f"'{method_name}' is not implemented by the '{self.name}' backend engine. "
            f"Please implement {self.__class__.__name__}.{method_name}() or use a different backend."
        )

    # Preparation
    def filter(
        self,
        df: Any,
        condition: Any = None,
        *,
        column: str | None = None,
        operator: str | None = None,
        value: Any = None,
    ) -> tuple[Any, Any]:
        self._not_implemented("filter")

    def formula(self, df: Any, column: str, expression: Any) -> Any:
        self._not_implemented("formula")

    def select(
        self,
        df: Any,
        columns: Sequence[str] | None = None,
        renames: dict[str, str] | None = None,
        dtypes: dict[str, str | type] | None = None,
    ) -> Any:
        self._not_implemented("select")

    def data_cleansing(
        self,
        df: Any,
        columns: Sequence[str] | None = None,
        remove_null_rows: bool = False,
        replace_nulls_with: Any = None,
        strip_whitespace: bool = True,
        remove_letters: bool = False,
        remove_numbers: bool = False,
        remove_punctuation: bool = False,
        modify_case: str | None = None,
    ) -> Any:
        self._not_implemented("data_cleansing")

    def sort(self, df: Any, columns: str | Sequence[str], ascending: bool | Sequence[bool] = True) -> Any:
        self._not_implemented("sort")

    def unique(self, df: Any, columns: str | Sequence[str], ignore_case: bool = False) -> tuple[Any, Any]:
        self._not_implemented("unique")

    def sample(
        self,
        df: Any,
        n: int | None = None,
        pct: float | None = None,
        random: bool = False,
        position: str = "first",
        random_state: int | None = None,
    ) -> Any:
        self._not_implemented("sample")

    def record_id(self, df: Any, column_name: str = "RecordID", start: int = 1) -> Any:
        self._not_implemented("record_id")

    def generate_rows(
        self,
        count: int,
        expression: Callable[[int], dict[str, Any]] | None = None,
        columns: Sequence[str] | None = None,
    ) -> Any:
        self._not_implemented("generate_rows")

    def auto_field(self, df: Any) -> Any:
        self._not_implemented("auto_field")

    def multi_field_formula(self, df: Any, columns: Sequence[str], expression: Callable) -> Any:
        self._not_implemented("multi_field_formula")

    def multi_row_formula(
        self,
        df: Any,
        column: str,
        expression: Callable,
        rows_back: int = 1,
        group_by: str | Sequence[str] | None = None,
    ) -> Any:
        self._not_implemented("multi_row_formula")

    def tile(
        self, df: Any, column: str, n_tiles: int, method: str = "equal_records", output_column: str = "Tile"
    ) -> Any:
        self._not_implemented("tile")

    def imputation(
        self,
        df: Any,
        columns: str | Sequence[str],
        method: str = "mean",
        replacement_value: Any | None = None,
        add_indicator: bool = True,
    ) -> Any:
        self._not_implemented("imputation")

    def create_samples(
        self, df: Any, estimation_pct: float, validation_pct: float, holdout_pct: float, random_state: int | None = None
    ) -> tuple[Any, Any, Any]:
        self._not_implemented("create_samples")

    def date_filter(self, df: Any, column: str, start_date: Any = None, end_date: Any = None) -> tuple[Any, Any]:
        self._not_implemented("date_filter")

    def oversample_field(
        self, df: Any, column: str, value: Any, target_pct: float = 0.5, random_state: int | None = None
    ) -> Any:
        self._not_implemented("oversample_field")

    def rank(
        self,
        df: Any,
        column: str,
        group_by: str | Sequence[str] | None = None,
        ascending: bool = False,
        method: str = "min",
        output_column: str = "Rank",
    ) -> Any:
        self._not_implemented("rank")

    # Join
    def join(
        self,
        left: Any,
        right: Any,
        on: str | Sequence[str] | None = None,
        left_on: str | Sequence[str] | None = None,
        right_on: str | Sequence[str] | None = None,
        suffixes: tuple[str, str] = ("_left", "_right"),
    ) -> tuple[Any, Any, Any]:
        self._not_implemented("join")

    def join_multiple(self, *dfs: Any, on: str | Sequence[str] | None = None, join_type: str = "outer") -> Any:
        self._not_implemented("join_multiple")

    def union(self, *dfs: Any, by: str = "name") -> Any:
        self._not_implemented("union")

    def find_replace(
        self,
        df: Any,
        find_df: Any,
        find_col: str,
        replace_col: str,
        target_col: str | None = None,
        mode: str = "entire",
        append: bool = False,
    ) -> Any:
        self._not_implemented("find_replace")

    def append_fields(self, left: Any, right: Any) -> Any:
        self._not_implemented("append_fields")

    def fuzzy_match(
        self,
        left: Any,
        right: Any,
        left_on: str,
        right_on: str,
        threshold: float = 0.6,
        score_column: str = "MatchScore",
    ) -> Any:
        self._not_implemented("fuzzy_match")

    def make_group(self, df: Any, key1: str, key2: str) -> Any:
        self._not_implemented("make_group")

    # Transform
    def summarize(
        self,
        df: Any,
        group_by: str | Sequence[str] | None = None,
        aggregations: dict[str, str | list[str]] | None = None,
    ) -> Any:
        self._not_implemented("summarize")

    def transpose(
        self,
        df: Any,
        key_columns: str | Sequence[str],
        data_columns: str | Sequence[str] | None = None,
        var_name: str = "Name",
        value_name: str = "Value",
    ) -> Any:
        self._not_implemented("transpose")

    def cross_tab(
        self, df: Any, group_by: str | Sequence[str], pivot_col: str, value_col: str, agg: str = "sum"
    ) -> Any:
        self._not_implemented("cross_tab")

    def running_total(
        self, df: Any, column: str, group_by: str | Sequence[str] | None = None, output_column: str | None = None
    ) -> Any:
        self._not_implemented("running_total")

    def count_records(self, df: Any, output_col: str = "Count") -> Any:
        self._not_implemented("count_records")

    def arrange(
        self,
        df: Any,
        key_columns: str | Sequence[str] | None = None,
        output_mapping: dict[str, Sequence[str]] | None = None,
    ) -> Any:
        self._not_implemented("arrange")

    def make_columns(self, df: Any, num_columns: int) -> Any:
        self._not_implemented("make_columns")

    def weighted_average(
        self,
        df: Any,
        value_column: str,
        weight_column: str,
        group_by: str | Sequence[str] | None = None,
        output_column: str = "WeightedAverage",
    ) -> Any:
        self._not_implemented("weighted_average")

    # InOut
    def input_data(self, path: Any, **kwargs: Any) -> Any:
        self._not_implemented("input_data")

    def output_data(self, df: Any, path: Any, **kwargs: Any) -> None:
        self._not_implemented("output_data")

    def text_input(self, data: Any, columns: Sequence[str] | None = None) -> Any:
        self._not_implemented("text_input")

    def browse(self, df: Any, n: int = 10) -> Any:
        self._not_implemented("browse")

    def directory(self, path: Any, pattern: str = "*") -> Any:
        self._not_implemented("directory")

    def date_time_now(self) -> Any:
        self._not_implemented("date_time_now")

    # Parse
    def date_time(self, df: Any, column: str, input_fmt: str | None = None, output_fmt: str | None = None) -> Any:
        self._not_implemented("date_time")

    def regex_match(self, df: Any, column: str, pattern: str, output_column: str = "Match") -> Any:
        self._not_implemented("regex_match")

    def regex_parse(self, df: Any, column: str, pattern: str, output_cols: Sequence[str] | None = None) -> Any:
        self._not_implemented("regex_parse")

    def regex_replace(self, df: Any, column: str, pattern: str, replacement: str) -> Any:
        self._not_implemented("regex_replace")

    def regex_tokenize(self, df: Any, column: str, pattern: str, split_to: str = "rows") -> Any:
        self._not_implemented("regex_tokenize")

    def text_to_columns(
        self, df: Any, column: str, delimiter: str, split_to: str = "columns", num_columns: int | None = None
    ) -> Any:
        self._not_implemented("text_to_columns")

    def xml_parse(
        self,
        df: Any,
        column: str,
        xpath: str,
        output_column: str = "ParsedXML",
        return_child_values: bool = False,
        return_outer_xml: bool = False,
    ) -> Any:
        self._not_implemented("xml_parse")

    # Developer
    def base64_encode(self, df: Any, column: str, output_column: str | None = None) -> Any:
        self._not_implemented("base64_encode")

    def base64_decode(self, df: Any, column: str, output_column: str | None = None) -> Any:
        self._not_implemented("base64_decode")

    def download(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        output_column: str = "DownloadData",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Any:
        self._not_implemented("download")

    def column_info(self, df: Any) -> Any:
        self._not_implemented("column_info")

    def dynamic_rename(
        self, df: Any, rename_df: Any, key_col: str = "OldName", new_name_col: str = "NewName", mode: str = "mapping"
    ) -> Any:
        self._not_implemented("dynamic_rename")

    def json_parse(self, df: Any, column: str, prefix: str | None = None) -> Any:
        self._not_implemented("json_parse")

    def dynamic_select(
        self, df: Any, dtype_include: Any = None, dtype_exclude: Any = None, pattern: str | None = None
    ) -> Any:
        self._not_implemented("dynamic_select")

    def test(self, df: Any, condition_func: Callable, error_msg: str = "Test condition failed") -> Any:
        self._not_implemented("test")

    def test_equal(self, df_left: Any, df_right: Any, **kwargs: Any) -> None:
        self._not_implemented("test_equal")
