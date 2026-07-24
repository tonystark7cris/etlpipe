"""Comprehensive enterprise assessment test suite for etlpipe.

Tests cover all 7 focus areas identified in the Deloitte package assessment:
1. Functional Validation â€” core tool correctness and schema preservation
2. Edge Cases & Robustness â€” empty data, nulls, extremes, duplicates
3. Performance â€” regression markers for large datasets
4. Integration â€” import and export compatibility
5. Security â€” injection, RCE vectors, safe defaults
6. Packaging â€” imports, version, CLI
7. Documentation â€” README example accuracy

Run with:  pytest tests/test_assessment.py -v --tb=long
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import etlpipe
from etlpipe import (
    Developer,
    InOut,
    Join,
    Parse,
    Pipeline,
    Preparation,
    Transform,
)

# ====================================================================== #
#  Shared fixtures
# ====================================================================== #


@pytest.fixture
def basic_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": [1, 2, 3, 4, 5],
            "Name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "Age": [30, 25, 35, 28, 32],
            "City": ["New York", "Boston", "Chicago", "Boston", "New York"],
            "Salary": [70000, 55000, 85000, 62000, 78000],
        }
    )


@pytest.fixture
def nulls_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": [1, 2, 3, 4, 5],
            "Name": ["Alice", None, "Charlie", "Diana", None],
            "Age": [30, 25, None, 28, 32],
            "Score": [95.5, None, 88.0, None, 72.5],
        }
    )


@pytest.fixture
def empty_df() -> pd.DataFrame:
    return pd.DataFrame({"A": pd.Series(dtype="int64"), "B": pd.Series(dtype="str")})


@pytest.fixture
def single_row_df() -> pd.DataFrame:
    return pd.DataFrame({"X": [42], "Y": ["hello"]})


@pytest.fixture
def dates_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "DateStr": ["01/15/2023", "02/20/2023", "03/25/2023"],
        }
    )


@pytest.fixture
def sales_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Region": ["East", "East", "West", "West", "East"],
            "Quarter": ["Q1", "Q2", "Q1", "Q2", "Q1"],
            "Revenue": [100, 200, 150, 250, 300],
            "Quantity": [10, 20, 15, 25, 30],
        }
    )


@pytest.fixture
def left_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CustomerID": [1, 2, 3, 4],
            "Name": ["Alice", "Bob", "Charlie", "Diana"],
        }
    )


@pytest.fixture
def right_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CustomerID": [2, 3, 5],
            "OrderTotal": [150.00, 200.00, 95.00],
        }
    )


@pytest.fixture
def spaced_cols_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "First Name": ["Alice", "Bob"],
            "Last Name": ["Smith", "Jones"],
            "Total Sales": [100.0, 200.0],
        }
    )


@pytest.fixture
def duplicates_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Email": ["a@b.com", "a@b.com", "c@d.com", "c@d.com", "e@f.com"],
            "Name": ["Alice", "Alice Dup", "Charlie", "Charlie Dup", "Eve"],
        }
    )


@pytest.fixture
def xml_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": [1, 2],
            "XMLData": [
                '<root><Person name="Alice"><Age>30</Age></Person></root>',
                '<root><Person name="Bob"><Age>25</Age></Person></root>',
            ],
        }
    )


@pytest.fixture
def json_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": [1, 2],
            "Payload": ['{"city": "NYC", "zip": "10001"}', '{"city": "LA", "zip": "90001"}'],
        }
    )


@pytest.fixture
def extreme_values_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "BigInt": [2**62, -(2**62), 0],
            "BigFloat": [1e308, -1e308, 1e-308],
            "Normal": [1, 2, 3],
        }
    )


# ====================================================================== #
#  1. FUNCTIONAL VALIDATION
# ====================================================================== #


class TestFunctionalValidation:
    """Core tool correctness and schema preservation."""

    # --- Filter ---
    def test_filter_string_condition(self, basic_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(basic_df, "Age > 30")
        assert len(t) == 2
        assert len(f) == 3
        assert set(t.columns) == set(basic_df.columns)

    def test_filter_callable_condition(self, basic_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(basic_df, lambda d: d["City"] == "Boston")
        assert len(t) == 2
        assert set(t["Name"]) == {"Bob", "Diana"}

    def test_filter_basic_operators(self, basic_df: pd.DataFrame) -> None:
        t, _ = Preparation.filter(basic_df, column="Salary", operator=">=", value=70000)
        assert len(t) == 3  # Alice(70k), Charlie(85k), Eve(78k)

    def test_filter_contains_operator(self, basic_df: pd.DataFrame) -> None:
        t, _ = Preparation.filter(basic_df, column="Name", operator="contains", value="li")
        assert set(t["Name"]) == {"Alice", "Charlie"}

    def test_filter_is_null_operator(self, nulls_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(nulls_df, column="Name", operator="is null")
        assert len(t) == 2
        assert len(f) == 3

    def test_filter_returns_tuple(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.filter(basic_df, "Age > 30")
        assert isinstance(result, tuple)
        assert len(result) == 2

    # --- Formula ---
    def test_formula_creates_column(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.formula(basic_df, "DoubleSalary", "Salary * 2")
        assert "DoubleSalary" in result.columns
        assert result["DoubleSalary"].iloc[0] == 140000

    def test_formula_lambda(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.formula(basic_df, "Upper", lambda d: d["Name"].str.upper())
        assert result["Upper"].iloc[0] == "ALICE"

    def test_formula_with_spaces_in_column_names(self, spaced_cols_df: pd.DataFrame) -> None:
        """Column names with spaces should be auto-backticked."""
        result = Preparation.formula(spaced_cols_df, "Result", "`Total Sales` * 2")
        assert result["Result"].iloc[0] == 200.0

    def test_formula_does_not_mutate_input(self, basic_df: pd.DataFrame) -> None:
        original_cols = list(basic_df.columns)
        _ = Preparation.formula(basic_df, "NewCol", "Age + 1")
        assert list(basic_df.columns) == original_cols
        assert "NewCol" not in basic_df.columns

    # --- Select ---
    def test_select_subset(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.select(basic_df, ["Name", "Age"])
        assert list(result.columns) == ["Name", "Age"]

    def test_select_rename(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.select(basic_df, ["Name"], renames={"Name": "FullName"})
        assert "FullName" in result.columns
        assert "Name" not in result.columns

    def test_select_dtype_cast(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.select(basic_df, ["Age"], dtypes={"Age": "float64"})
        assert result["Age"].dtype == np.float64

    # --- Join ---
    def test_join_returns_three_anchors(self, left_df: pd.DataFrame, right_df: pd.DataFrame) -> None:
        L, J, R = Join.join(left_df, right_df, on="CustomerID")
        assert isinstance(L, pd.DataFrame)
        assert isinstance(J, pd.DataFrame)
        assert isinstance(R, pd.DataFrame)

    def test_join_inner_correctness(self, left_df: pd.DataFrame, right_df: pd.DataFrame) -> None:
        L, J, R = Join.join(left_df, right_df, on="CustomerID")
        assert len(J) == 2  # IDs 2 and 3 match
        assert set(J["CustomerID"]) == {2, 3}
        assert len(L) == 2  # IDs 1 and 4 unmatched
        assert len(R) == 1  # ID 5 unmatched

    def test_join_immutability(self) -> None:
        """CRITICAL: Join must NOT mutate input DataFrames.

        Uses intentionally mismatched dtypes (int vs float) on the join key
        to trigger the dtype coercion code path that previously mutated
        the right DataFrame in-place.
        """
        left = pd.DataFrame({"Key": [1, 2, 3], "A": ["a", "b", "c"]})
        right = pd.DataFrame({"Key": [1.0, 2.0, 4.0], "B": ["x", "y", "z"]})
        right_original = right.copy()
        left_original = left.copy()
        Join.join(left, right, on="Key")
        pd.testing.assert_frame_equal(left, left_original)
        pd.testing.assert_frame_equal(right, right_original, check_dtype=True)

    def test_join_type_mismatch_coercion(self) -> None:
        """Join should handle int vs float key columns gracefully."""
        left = pd.DataFrame({"Key": [1, 2, 3], "Val": ["a", "b", "c"]})
        right = pd.DataFrame({"Key": [1.0, 2.0, 4.0], "Data": ["x", "y", "z"]})
        L, J, R = Join.join(left, right, on="Key")
        assert len(J) == 2

    # --- Data Cleansing ---
    def test_data_cleansing_strip_whitespace(self) -> None:
        df = pd.DataFrame({"Name": ["  Alice  ", "Bob  ", "  Charlie"]})
        result = Preparation.data_cleansing(df, ["Name"], strip_whitespace=True)
        assert list(result["Name"]) == ["Alice", "Bob", "Charlie"]

    def test_data_cleansing_modify_case(self) -> None:
        df = pd.DataFrame({"City": ["new york", "BOSTON", "chicago"]})
        result = Preparation.data_cleansing(df, ["City"], modify_case="title")
        assert list(result["City"]) == ["New York", "Boston", "Chicago"]

    def test_data_cleansing_nan_handling(self, nulls_df: pd.DataFrame) -> None:
        """Data cleansing must NOT convert NaN to the string 'nan'."""
        result = Preparation.data_cleansing(nulls_df, ["Name"], strip_whitespace=True)
        # After the fix, null values should remain as NaN, not become "nan"
        nan_string_count = (result["Name"] == "nan").sum()
        none_string_count = (result["Name"] == "None").sum()
        null_count = result["Name"].isna().sum()
        assert nan_string_count == 0, "NaN was converted to literal string 'nan'"
        assert none_string_count == 0, "None was converted to literal string 'None'"
        assert null_count == 2, f"Expected 2 nulls preserved, got {null_count}"

    # --- Sort ---
    def test_sort_ascending(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.sort(basic_df, "Age", ascending=True)
        assert list(result["Age"]) == [25, 28, 30, 32, 35]

    def test_sort_multi_column(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.sort(basic_df, ["City", "Age"], ascending=[True, False])
        assert result.iloc[0]["City"] == "Boston"
        assert result.iloc[0]["Age"] == 28

    # --- Unique ---
    def test_unique_split(self, duplicates_df: pd.DataFrame) -> None:
        uniq, dups = Preparation.unique(duplicates_df, "Email")
        assert len(uniq) == 3
        assert len(dups) == 2

    # --- Sample ---
    def test_sample_first_n(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.sample(basic_df, n=3, position="first")
        assert len(result) == 3

    def test_sample_last_n(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.sample(basic_df, n=2, position="last")
        assert len(result) == 2

    def test_sample_random(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.sample(basic_df, n=3, random=True, random_state=42)
        assert len(result) == 3

    # --- Record ID ---
    def test_record_id(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.record_id(basic_df)
        assert "RecordID" in result.columns
        assert list(result["RecordID"]) == [1, 2, 3, 4, 5]

    def test_record_id_custom_start(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.record_id(basic_df, column_name="RowNum", start=100)
        assert list(result["RowNum"]) == [100, 101, 102, 103, 104]

    # --- Generate Rows ---
    def test_generate_rows_simple(self) -> None:
        result = Preparation.generate_rows(5)
        assert len(result) == 5
        assert "RowNum" in result.columns

    def test_generate_rows_with_expression(self) -> None:
        result = Preparation.generate_rows(3, lambda i: {"x": i, "y": i**2})
        assert len(result) == 3
        assert list(result["y"]) == [0, 1, 4]

    # --- Summarize ---
    def test_summarize_group_by(self, sales_df: pd.DataFrame) -> None:
        result = Transform.summarize(sales_df, group_by="Region", aggregations={"Revenue": ["sum", "mean"]})
        assert "Region" in result.columns
        assert len(result) == 2  # East and West

    def test_summarize_no_group(self, sales_df: pd.DataFrame) -> None:
        result = Transform.summarize(sales_df, aggregations={"Revenue": "sum"})
        assert len(result) == 1

    # --- Transpose ---
    def test_transpose(self, sales_df: pd.DataFrame) -> None:
        result = Transform.transpose(sales_df, key_columns="Region", data_columns=["Revenue", "Quantity"])
        assert "Name" in result.columns
        assert "Value" in result.columns

    # --- Cross Tab ---
    def test_cross_tab(self, sales_df: pd.DataFrame) -> None:
        result = Transform.cross_tab(sales_df, group_by="Region", pivot_col="Quarter", value_col="Revenue", agg="sum")
        assert "Q1" in result.columns
        assert "Q2" in result.columns

    # --- Running Total ---
    def test_running_total(self) -> None:
        df = pd.DataFrame({"Sales": [10, 20, 30, 40, 50]})
        result = Transform.running_total(df, "Sales")
        assert list(result["RunningTotal_Sales"]) == [10, 30, 60, 100, 150]

    # --- Count Records ---
    def test_count_records(self, basic_df: pd.DataFrame) -> None:
        result = Transform.count_records(basic_df)
        assert result["Count"].iloc[0] == 5

    # --- Union ---
    def test_union_by_name(self) -> None:
        df1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        df2 = pd.DataFrame({"A": [5, 6], "B": [7, 8]})
        result = Join.union(df1, df2)
        assert len(result) == 4

    # --- Append Fields ---
    def test_append_fields_cross_join(self) -> None:
        left = pd.DataFrame({"Size": ["S", "M", "L"]})
        right = pd.DataFrame({"Color": ["Red", "Blue"]})
        result = Join.append_fields(left, right)
        assert len(result) == 6  # 3 x 2

    # --- Text Input ---
    def test_text_input_dict(self) -> None:
        result = InOut.text_input({"A": [1, 2], "B": [3, 4]})
        assert len(result) == 2
        assert list(result.columns) == ["A", "B"]

    def test_text_input_list_of_dicts(self) -> None:
        result = InOut.text_input([{"x": 1, "y": 2}, {"x": 3, "y": 4}])
        assert len(result) == 2

    # --- All tools return DataFrames ---
    def test_all_preparation_tools_return_dataframes(self, basic_df: pd.DataFrame) -> None:
        """Every tool should return a DataFrame (or tuple of DataFrames)."""
        results = {
            "formula": Preparation.formula(basic_df, "X", "Age + 1"),
            "select": Preparation.select(basic_df, ["Name"]),
            "sort": Preparation.sort(basic_df, "Age"),
            "sample": Preparation.sample(basic_df, n=2),
            "record_id": Preparation.record_id(basic_df),
            "auto_field": Preparation.auto_field(basic_df),
        }
        for name, result in results.items():
            assert isinstance(result, pd.DataFrame), f"{name} did not return DataFrame"

    def test_tuple_returning_tools(self, basic_df: pd.DataFrame) -> None:
        filter_result = Preparation.filter(basic_df, "Age > 30")
        assert isinstance(filter_result, tuple) and len(filter_result) == 2

        unique_result = Preparation.unique(basic_df, "City")
        assert isinstance(unique_result, tuple) and len(unique_result) == 2


# ====================================================================== #
#  2. EDGE CASES & ROBUSTNESS
# ====================================================================== #


class TestEdgeCases:
    """Empty datasets, nulls, malformed inputs, extreme values, duplicates."""

    # --- Empty DataFrames ---
    def test_filter_empty_df(self, empty_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(pd.DataFrame({"A": pd.Series(dtype="int64")}), "A > 0")
        assert len(t) == 0
        assert len(f) == 0

    def test_sort_empty_df(self) -> None:
        df = pd.DataFrame({"A": pd.Series(dtype="int64")})
        result = Preparation.sort(df, "A")
        assert len(result) == 0

    def test_count_records_empty_df(self) -> None:
        df = pd.DataFrame({"A": pd.Series(dtype="int64")})
        result = Transform.count_records(df)
        assert result["Count"].iloc[0] == 0

    def test_record_id_empty_df(self) -> None:
        df = pd.DataFrame({"A": pd.Series(dtype="int64")})
        result = Preparation.record_id(df)
        assert len(result) == 0
        assert "RecordID" in result.columns

    # --- Single row ---
    def test_filter_single_row_true(self, single_row_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(single_row_df, "X > 0")
        assert len(t) == 1
        assert len(f) == 0

    def test_filter_single_row_false(self, single_row_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(single_row_df, "X < 0")
        assert len(t) == 0
        assert len(f) == 1

    def test_unique_single_row(self, single_row_df: pd.DataFrame) -> None:
        uniq, dups = Preparation.unique(single_row_df, "X")
        assert len(uniq) == 1
        assert len(dups) == 0

    def test_sample_n_exceeds_rows(self, single_row_df: pd.DataFrame) -> None:
        result = Preparation.sample(single_row_df, n=100)
        assert len(result) == 1

    # --- Null handling ---
    def test_imputation_mean(self, nulls_df: pd.DataFrame) -> None:
        result = Preparation.imputation(nulls_df, "Score", method="mean")
        assert result["Score"].isna().sum() == 0
        assert "Score_WasImputed" in result.columns
        assert result["Score_WasImputed"].sum() == 2

    def test_imputation_median(self, nulls_df: pd.DataFrame) -> None:
        result = Preparation.imputation(nulls_df, "Score", method="median")
        assert result["Score"].isna().sum() == 0

    def test_imputation_mode(self, nulls_df: pd.DataFrame) -> None:
        result = Preparation.imputation(nulls_df, "Score", method="mode")
        assert result["Score"].isna().sum() == 0

    def test_imputation_custom_value(self, nulls_df: pd.DataFrame) -> None:
        result = Preparation.imputation(nulls_df, "Score", method="value", replacement_value=-1)
        assert (result["Score"] == -1).sum() == 2

    def test_data_cleansing_replace_nulls(self, nulls_df: pd.DataFrame) -> None:
        result = Preparation.data_cleansing(nulls_df, ["Name"], replace_nulls_with="UNKNOWN")
        assert "UNKNOWN" in result["Name"].values

    # --- Extreme values ---
    def test_sort_extreme_values(self, extreme_values_df: pd.DataFrame) -> None:
        result = Preparation.sort(extreme_values_df, "BigInt")
        assert result["BigInt"].iloc[0] == -(2**62)

    def test_formula_extreme_values(self, extreme_values_df: pd.DataFrame) -> None:
        result = Preparation.formula(extreme_values_df, "Doubled", "Normal * 2")
        assert list(result["Doubled"]) == [2, 4, 6]

    def test_running_total_extreme_values(self, extreme_values_df: pd.DataFrame) -> None:
        result = Transform.running_total(extreme_values_df, "Normal")
        assert list(result["RunningTotal_Normal"]) == [1, 3, 6]

    # --- Duplicate handling ---
    def test_unique_all_duplicates(self) -> None:
        df = pd.DataFrame({"A": [1, 1, 1, 1]})
        uniq, dups = Preparation.unique(df, "A")
        assert len(uniq) == 1
        assert len(dups) == 3

    def test_unique_no_duplicates(self, basic_df: pd.DataFrame) -> None:
        uniq, dups = Preparation.unique(basic_df, "ID")
        assert len(uniq) == 5
        assert len(dups) == 0

    def test_unique_ignore_case(self) -> None:
        df = pd.DataFrame({"Name": ["Alice", "alice", "ALICE", "Bob"]})
        uniq, dups = Preparation.unique(df, "Name", ignore_case=True)
        assert len(uniq) == 2
        assert len(dups) == 2

    # --- Type errors ---
    def test_filter_invalid_input_type(self) -> None:
        with pytest.raises(TypeError):
            Preparation.filter("not a dataframe", "x > 0")

    def test_select_missing_column(self, basic_df: pd.DataFrame) -> None:
        with pytest.raises(KeyError):
            Preparation.select(basic_df, ["NonExistent"])

    def test_sample_no_n_or_pct(self, basic_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError):
            Preparation.sample(basic_df)

    def test_sample_both_n_and_pct(self, basic_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError):
            Preparation.sample(basic_df, n=3, pct=0.5)

    # --- Create Samples ---
    def test_create_samples_valid_split(self, basic_df: pd.DataFrame) -> None:
        est, val, hold = Preparation.create_samples(basic_df, 0.6, 0.2, 0.2, random_state=42)
        total = len(est) + len(val) + len(hold)
        assert total == len(basic_df)

    def test_create_samples_invalid_sum(self, basic_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="sum to 1.0"):
            Preparation.create_samples(basic_df, 0.7, 0.2, 0.2)

    # --- Date Filter ---
    def test_date_filter(self) -> None:
        df = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2023-01-15", "2023-06-15", "2023-12-15"]),
                "Val": [1, 2, 3],
            }
        )
        t, f = Preparation.date_filter(df, "Date", "2023-02-01", "2023-07-01")
        assert len(t) == 1
        assert len(f) == 2

    # --- Tile ---
    def test_tile_equal_records(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.tile(basic_df, "Salary", 2)
        assert "Tile" in result.columns

    def test_tile_equal_range(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.tile(basic_df, "Salary", 3, method="equal_range")
        assert "Tile" in result.columns

    # --- Oversample ---
    def test_oversample_field(self) -> None:
        df = pd.DataFrame(
            {
                "Label": ["A"] * 90 + ["B"] * 10,
                "Val": range(100),
            }
        )
        result = Preparation.oversample_field(df, "Label", "B", target_pct=0.5, random_state=42)
        b_count = (result["Label"] == "B").sum()
        total = len(result)
        actual_pct = b_count / total
        assert 0.35 < actual_pct < 0.65  # Allow tolerance

    # --- Rank ---
    def test_rank_basic(self, basic_df: pd.DataFrame) -> None:
        result = Preparation.rank(basic_df, "Salary")
        assert "Rank" in result.columns
        # Highest salary (85000) should be rank 1 (default ascending=False)
        top = result.loc[result["Salary"] == 85000, "Rank"].iloc[0]
        assert top == 1


# ====================================================================== #
#  3. PERFORMANCE (Markers only â€” not run by default)
# ====================================================================== #


class TestPerformance:
    """Performance regression tests. Run with: pytest -m slow"""

    @pytest.mark.slow
    def test_large_filter(self) -> None:
        n = 1_000_000
        df = pd.DataFrame({"A": np.random.randint(0, 100, n), "B": np.random.rand(n)})
        t, f = Preparation.filter(df, "A > 50")
        assert len(t) + len(f) == n

    @pytest.mark.slow
    def test_large_sort(self) -> None:
        n = 1_000_000
        df = pd.DataFrame({"A": np.random.rand(n)})
        result = Preparation.sort(df, "A")
        assert len(result) == n

    @pytest.mark.slow
    def test_large_join(self) -> None:
        n = 500_000
        left = pd.DataFrame({"Key": range(n), "Val": np.random.rand(n)})
        right = pd.DataFrame({"Key": range(0, n, 2), "Data": np.random.rand(n // 2)})
        L, J, R = Join.join(left, right, on="Key")
        assert len(J) == n // 2

    @pytest.mark.slow
    def test_large_summarize(self) -> None:
        n = 1_000_000
        df = pd.DataFrame(
            {
                "Group": np.random.choice(["A", "B", "C", "D"], n),
                "Value": np.random.rand(n),
            }
        )
        result = Transform.summarize(df, group_by="Group", aggregations={"Value": ["sum", "mean", "count"]})
        assert len(result) == 4


# ====================================================================== #
#  4. SECURITY
# ====================================================================== #


class TestSecurity:
    """Injection, RCE vectors, and safe defaults."""

    def test_formula_no_arbitrary_eval(self, basic_df: pd.DataFrame) -> None:
        """Formula should not execute arbitrary Python code via eval()."""
        with pytest.raises((ValueError, Exception)):
            Preparation.formula(basic_df, "Hack", "__import__('os').system('echo pwned')")

    def test_yaml_uses_safe_load(self) -> None:
        """Pipeline YAML loading must use safe_load, not load."""
        import inspect

        source = inspect.getsource(Pipeline.__init__)
        assert "safe_load" in source
        assert "yaml.load(" not in source or "yaml.safe_load" in source

    def test_pickle_format_supported(self) -> None:
        """Document that pickle is supported (potential RCE vector)."""
        from etlpipe.in_out import _READERS

        # This test documents the risk â€” pickle is currently supported
        assert ".pkl" in _READERS or ".pickle" in _READERS

    def test_download_does_not_hang_on_bad_url(self) -> None:
        """Download should not hang indefinitely on unreachable URLs."""
        # We can't easily test real timeouts without network, but we verify
        # the function raises on invalid URLs rather than hanging
        with pytest.raises(Exception, match=r".+"):
            Developer.download("http://192.0.2.1:1/nonexistent")  # RFC 5737 test address

    def test_pipeline_tool_resolution_scoped(self) -> None:
        """Pipeline should only resolve tools from etlpipe module."""
        import yaml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, dir=tempfile.gettempdir()) as f:
            yaml.dump(
                {"name": "test", "steps": [{"id": "bad", "tool": "os.system", "args": {"command": "echo pwned"}}]}, f
            )
            temp_path = f.name

        try:
            pipeline = Pipeline(temp_path)
            with pytest.raises((ValueError, AttributeError)):
                pipeline.execute()
        finally:
            os.unlink(temp_path)

    def test_pickle_emits_deprecation_warning(self, basic_df: pd.DataFrame, tmp_path: Path) -> None:
        """Pickle I/O should emit a DeprecationWarning (CWE-502 mitigation)."""
        pkl_path = tmp_path / "test.pkl"
        with pytest.warns(DeprecationWarning, match="Pickle format support is deprecated"):
            InOut.output_data(basic_df, str(pkl_path))
        with pytest.warns(DeprecationWarning, match="Pickle format support is deprecated"):
            InOut.input_data(str(pkl_path))

    def test_backend_engine_not_implemented(self) -> None:
        """BackendEngine base methods must raise NotImplementedError, not return None."""
        from etlpipe.engines.base import BackendEngine

        class DummyEngine(BackendEngine):
            @property
            def name(self) -> str:
                return "dummy"

        engine = DummyEngine()
        with pytest.raises(NotImplementedError, match="filter.*dummy"):
            engine.filter(None)
        with pytest.raises(NotImplementedError, match="summarize.*dummy"):
            engine.summarize(None)


# ====================================================================== #
#  5. DUAL-ENGINE PARITY (Pandas-only verification of parity issues)
# ====================================================================== #


class TestDualEngineParity:
    """Document and test engine-specific behavioral differences."""

    def test_formula_equality_expression_pandas(self, basic_df: pd.DataFrame) -> None:
        """Pandas: `==` in formula expressions should work correctly."""
        result = Preparation.formula(basic_df, "IsBob", "Name == 'Bob'")
        assert result["IsBob"].sum() == 1

    def test_record_id_is_sequential_pandas(self, basic_df: pd.DataFrame) -> None:
        """Pandas engine should produce strictly sequential IDs."""
        result = Preparation.record_id(basic_df)
        ids = list(result["RecordID"])
        assert ids == list(range(1, 6))

    def test_column_info_has_real_counts_pandas(self, basic_df: pd.DataFrame) -> None:
        """Pandas column_info should return real NonNull/Null/Unique counts."""
        info = Developer.column_info(basic_df)
        assert "NonNullCount" in info.columns
        name_row = info[info["Name"] == "Name"]
        assert name_row["NonNullCount"].iloc[0] == 5
        assert name_row["NullCount"].iloc[0] == 0

    def test_multi_field_formula_preserves_type(self, basic_df: pd.DataFrame) -> None:
        """multi_field_formula should preserve the output type in Pandas."""
        result = Preparation.multi_field_formula(basic_df, ["Age", "Salary"], lambda s: s * 2)
        assert result["Age"].dtype in (np.int64, np.int32)
        assert result["Salary"].dtype in (np.int64, np.int32)


# ====================================================================== #
#  6. PACKAGING
# ====================================================================== #


class TestPackaging:
    """Import checks, version, CLI, and module structure."""

    def test_import_etlpipe(self) -> None:
        import etlpipe

        assert etlpipe is not None

    def test_version_exists(self) -> None:
        assert hasattr(etlpipe, "__version__")
        assert isinstance(etlpipe.__version__, str)
        assert len(etlpipe.__version__) > 0

    def test_all_classes_importable(self) -> None:
        from etlpipe import Developer, InOut, Join, Parse, Pipeline, Preparation, Transform

        assert all([InOut, Preparation, Join, Transform, Parse, Developer, Pipeline])

    def test_backend_functions(self) -> None:
        from etlpipe import get_backend, set_backend

        assert callable(set_backend)
        assert callable(get_backend)

    def test_default_backend_is_pandas(self) -> None:
        assert etlpipe.get_backend() == "pandas"

    def test_set_backend_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown backend"):
            etlpipe.set_backend("invalid_engine")

    def test_context_manager_restores_backend(self) -> None:
        original = etlpipe.get_backend()
        # The context manager should restore even on same backend
        with etlpipe.backend("pandas"):
            assert etlpipe.get_backend() == "pandas"
        assert etlpipe.get_backend() == original


# ====================================================================== #
#  7. DOCUMENTATION â€” README example verification
# ====================================================================== #


class TestDocumentation:
    """Verify that documented examples actually work."""

    def test_readme_text_input(self) -> None:
        df = InOut.text_input({"Name": ["Alice", "Bob"], "Age": [30, 25]})
        assert len(df) == 2
        assert list(df.columns) == ["Name", "Age"]

    def test_readme_filter(self) -> None:
        df = InOut.text_input({"Revenue": [500, 1500, 2000], "Name": ["A", "B", "C"]})
        high, low = Preparation.filter(df, "Revenue > 1000")
        assert len(high) == 2
        assert len(low) == 1

    def test_readme_formula(self) -> None:
        df = InOut.text_input({"Revenue": [100, 200], "Cost": [40, 60]})
        result = Preparation.formula(df, "Profit", "Revenue - Cost")
        assert list(result["Profit"]) == [60, 140]

    def test_readme_join(self) -> None:
        """README shows Join.join(df1, df2, on='ID', how='inner') but actual API has no 'how' param."""
        df1 = InOut.text_input({"ID": [1, 2, 3], "A": ["a", "b", "c"]})
        df2 = InOut.text_input({"ID": [2, 3, 4], "B": ["x", "y", "z"]})
        # Correct usage (no `how` parameter):
        L, J, R = Join.join(df1, df2, on="ID")
        assert len(J) == 2

    def test_readme_summarize(self) -> None:
        df = InOut.text_input(
            {
                "Region": ["East", "East", "West"],
                "Sales": [100, 200, 150],
            }
        )
        result = Transform.summarize(df, group_by="Region", aggregations={"Sales": ["sum", "mean"]})
        assert len(result) == 2

    def test_yaml_pipeline_execution(self) -> None:
        """The sample YAML pipeline should execute without errors."""
        yaml_path = Path(__file__).parent.parent / "demo" / "sample_pipeline.yaml"
        if yaml_path.exists():
            pipeline = Pipeline(yaml_path)
            pipeline.execute()
            # Verify final state
            assert "load" in pipeline.state
            assert "filter" in pipeline.state
        else:
            pytest.skip("sample_pipeline.yaml not found")

    def test_readme_browse_returns_df(self, basic_df: pd.DataFrame) -> None:
        """browse() should return the original DataFrame for mid-pipeline use."""
        result = InOut.browse(basic_df, n=2)
        pd.testing.assert_frame_equal(result, basic_df)

    def test_readme_directory(self, tmp_path: Path) -> None:
        """directory() should list files in a folder."""
        (tmp_path / "test.csv").write_text("a,b\n1,2")
        (tmp_path / "test.json").write_text("{}")
        result = InOut.directory(str(tmp_path))
        assert len(result) == 2
        assert "FileName" in result.columns

    def test_readme_date_time_now(self) -> None:
        result = InOut.date_time_now()
        assert len(result) == 1
        assert "DateTime" in result.columns


# ====================================================================== #
#  PARSE TOOLS
# ====================================================================== #


class TestParseTools:
    """Parse palette tool validation."""

    def test_date_time_conversion(self, dates_df: pd.DataFrame) -> None:
        result = Parse.date_time(dates_df, "DateStr", input_fmt="%m/%d/%Y")
        assert pd.api.types.is_datetime64_any_dtype(result["DateStr"])

    def test_date_time_with_output_format(self, dates_df: pd.DataFrame) -> None:
        result = Parse.date_time(dates_df, "DateStr", input_fmt="%m/%d/%Y", output_fmt="%Y-%m-%d")
        assert result["DateStr"].iloc[0] == "2023-01-15"

    def test_regex_match(self) -> None:
        df = pd.DataFrame({"Email": ["a@b.com", "invalid", "c@d.org"]})
        result = Parse.regex_match(df, "Email", r"@")
        assert list(result["Match"]) == [True, False, True]

    def test_regex_parse_named_groups(self) -> None:
        df = pd.DataFrame({"Full": ["Alice Smith", "Bob Jones"]})
        result = Parse.regex_parse(df, "Full", r"(\w+)\s+(\w+)", ["First", "Last"])
        assert list(result["First"]) == ["Alice", "Bob"]
        assert list(result["Last"]) == ["Smith", "Jones"]

    def test_regex_replace(self) -> None:
        df = pd.DataFrame({"Phone": ["(123) 456-7890", "(987) 654-3210"]})
        result = Parse.regex_replace(df, "Phone", r"\D", "")
        assert result["Phone"].iloc[0] == "1234567890"

    def test_regex_tokenize_to_rows(self) -> None:
        df = pd.DataFrame({"Tags": ["a,b,c", "d,e"]})
        result = Parse.regex_tokenize(df, "Tags", r",", split_to="rows")
        assert len(result) == 5

    def test_regex_tokenize_to_columns(self) -> None:
        df = pd.DataFrame({"Tags": ["a,b,c", "d,e,f"]})
        result = Parse.regex_tokenize(df, "Tags", r",", split_to="columns")
        assert "Tags_1" in result.columns

    def test_text_to_columns(self) -> None:
        df = pd.DataFrame({"Address": ["123 Main St, NYC, NY", "456 Oak Ave, LA, CA"]})
        result = Parse.text_to_columns(df, "Address", ",", num_columns=3)
        assert "Address_1" in result.columns
        assert "Address_3" in result.columns

    def test_text_to_columns_rows(self) -> None:
        df = pd.DataFrame({"Items": ["a|b|c", "d|e"]})
        result = Parse.text_to_columns(df, "Items", "|", split_to="rows")
        assert len(result) == 5

    def test_xml_parse_simple(self, xml_df: pd.DataFrame) -> None:
        result = Parse.xml_parse(xml_df, "XMLData", ".//Person", "Person")
        assert "Person" in result.columns

    def test_xml_parse_child_values(self, xml_df: pd.DataFrame) -> None:
        result = Parse.xml_parse(xml_df, "XMLData", ".//Person", "Person", return_child_values=True)
        assert "Person_name" in result.columns or "Person_Age" in result.columns


# ====================================================================== #
#  DEVELOPER TOOLS
# ====================================================================== #


class TestDeveloperTools:
    """Developer palette tool validation."""

    def test_base64_encode_decode_roundtrip(self) -> None:
        df = pd.DataFrame({"Secret": ["Hello World", "etlpipe"]})
        encoded = Developer.base64_encode(df, "Secret")
        assert "Secret_Base64" in encoded.columns
        decoded = Developer.base64_decode(encoded, "Secret_Base64")
        assert "Secret_Base64_Decoded" in decoded.columns
        assert list(decoded["Secret_Base64_Decoded"]) == ["Hello World", "etlpipe"]

    def test_column_info(self, basic_df: pd.DataFrame) -> None:
        info = Developer.column_info(basic_df)
        assert len(info) == len(basic_df.columns)
        assert set(info.columns) == {"Name", "Type", "Size", "NonNullCount", "NullCount", "UniqueCount"}

    def test_dynamic_rename_mapping(self, basic_df: pd.DataFrame) -> None:
        mapping = pd.DataFrame(
            {
                "OldName": ["Name", "Age"],
                "NewName": ["FullName", "Years"],
            }
        )
        result = Developer.dynamic_rename(basic_df, mapping)
        assert "FullName" in result.columns
        assert "Years" in result.columns
        assert "Name" not in result.columns

    def test_dynamic_rename_prefix(self, basic_df: pd.DataFrame) -> None:
        prefix_df = pd.DataFrame({"Prefix": ["src_"]})
        result = Developer.dynamic_rename(basic_df, prefix_df, mode="prefix")
        assert all(c.startswith("src_") for c in result.columns)

    def test_json_parse(self, json_df: pd.DataFrame) -> None:
        result = Developer.json_parse(json_df, "Payload")
        assert "Payload_city" in result.columns or "Payload_zip" in result.columns

    def test_dynamic_select_by_type(self, basic_df: pd.DataFrame) -> None:
        result = Developer.dynamic_select(basic_df, dtype_include="number")
        assert all(pd.api.types.is_numeric_dtype(result[c]) for c in result.columns)

    def test_dynamic_select_by_pattern(self, basic_df: pd.DataFrame) -> None:
        result = Developer.dynamic_select(basic_df, pattern="^(Name|Age)$")
        assert set(result.columns) == {"Name", "Age"}

    def test_tool_pass(self, basic_df: pd.DataFrame) -> None:
        result = Developer.test(basic_df, lambda df: len(df) > 0, "DataFrame is empty!")
        pd.testing.assert_frame_equal(result, basic_df)

    def test_tool_fail(self, basic_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="should fail"):
            Developer.test(basic_df, lambda df: len(df) == 0, "This should fail")

    def test_test_equal_pass(self, basic_df: pd.DataFrame) -> None:
        Developer.test_equal(basic_df, basic_df.copy())

    def test_test_equal_fail(self, basic_df: pd.DataFrame) -> None:
        other = basic_df.copy()
        other["Age"] = other["Age"] + 1
        with pytest.raises(AssertionError):
            Developer.test_equal(basic_df, other)


# ====================================================================== #
#  TRANSFORM TOOLS â€” Advanced
# ====================================================================== #


class TestTransformAdvanced:
    """Advanced transform tool validation."""

    def test_arrange(self) -> None:
        df = pd.DataFrame(
            {
                "ID": [1, 2],
                "Home": ["111", "444"],
                "Work": ["222", "555"],
                "Cell": ["333", "666"],
            }
        )
        result = Transform.arrange(
            df,
            key_columns="ID",
            output_mapping={
                "Type": ["Home", "Work", "Cell"],
                "Phone": ["Home", "Work", "Cell"],
            },
        )
        # Should have 6 rows (2 IDs Ã— 3 phone types)
        assert len(result) == 6

    def test_make_columns(self) -> None:
        df = pd.DataFrame({"Name": ["A", "B", "C", "D", "E", "F"]})
        result = Transform.make_columns(df, 3)
        assert len(result.columns) == 3  # Name_1, Name_2, Name_3
        assert len(result) == 2  # 6 items / 3 columns

    def test_weighted_average(self) -> None:
        df = pd.DataFrame(
            {
                "Score": [80, 90, 100],
                "Weight": [1, 2, 1],
            }
        )
        result = Transform.weighted_average(df, "Score", "Weight")
        wa = result["WeightedAverage"].iloc[0]
        expected = (80 * 1 + 90 * 2 + 100 * 1) / (1 + 2 + 1)
        assert abs(wa - expected) < 0.01

    def test_weighted_average_grouped(self) -> None:
        df = pd.DataFrame(
            {
                "Region": ["E", "E", "W", "W"],
                "Price": [10, 20, 30, 40],
                "Volume": [100, 200, 300, 400],
            }
        )
        result = Transform.weighted_average(df, "Price", "Volume", group_by="Region")
        assert len(result) == 2

    def test_running_total_grouped(self) -> None:
        df = pd.DataFrame(
            {
                "Region": ["A", "A", "B", "B"],
                "Sales": [10, 20, 100, 200],
            }
        )
        result = Transform.running_total(df, "Sales", group_by="Region")
        col = "RunningTotal_Sales"
        assert list(result[col]) == [10, 30, 100, 300]


# ====================================================================== #
#  JOIN TOOLS â€” Advanced
# ====================================================================== #


class TestJoinAdvanced:
    """Advanced join tool validation."""

    def test_join_multiple(self) -> None:
        df1 = pd.DataFrame({"Key": [1, 2, 3], "A": [10, 20, 30]})
        df2 = pd.DataFrame({"Key": [1, 2, 3], "B": [40, 50, 60]})
        df3 = pd.DataFrame({"Key": [1, 2, 3], "C": [70, 80, 90]})
        result = Join.join_multiple(df1, df2, df3, on="Key")
        assert len(result) == 3
        assert {"A", "B", "C"}.issubset(set(result.columns))

    def test_union_by_position(self) -> None:
        df1 = pd.DataFrame({"X": [1, 2], "Y": [3, 4]})
        df2 = pd.DataFrame({"A": [5, 6], "B": [7, 8]})
        result = Join.union(df1, df2, by="position")
        assert list(result.columns) == ["X", "Y"]
        assert len(result) == 4

    def test_find_replace_entire(self) -> None:
        df = pd.DataFrame({"State": ["CA", "NY", "TX"]})
        lookup = pd.DataFrame({"State": ["CA", "NY"], "FullName": ["California", "New York"]})
        result = Join.find_replace(df, lookup, "State", "FullName")
        assert result["State"].iloc[0] == "California"
        assert result["State"].iloc[2] == "TX"  # Unchanged

    def test_find_replace_partial(self) -> None:
        df = pd.DataFrame({"Text": ["Hello World", "Goodbye World"]})
        lookup = pd.DataFrame({"Find": ["World"], "Replace": ["Earth"]})
        result = Join.find_replace(df, lookup, "Find", "Replace", target_col="Text", mode="partial")
        assert result["Text"].iloc[0] == "Hello Earth"

    def test_find_replace_append_mode(self) -> None:
        df = pd.DataFrame({"Code": ["CA", "NY", "TX"]})
        lookup = pd.DataFrame({"Code": ["CA", "NY"], "Name": ["California", "New York"]})
        result = Join.find_replace(df, lookup, "Code", "Name", append=True)
        assert "Name" in result.columns
        assert result["Code"].iloc[0] == "CA"  # Original preserved

    def test_fuzzy_match(self) -> None:
        left = pd.DataFrame({"Company": ["Apple Inc", "Google LLC"]})
        right = pd.DataFrame({"Name": ["Apple Incorporated", "Microsoft Corp"]})
        result = Join.fuzzy_match(left, right, "Company", "Name", threshold=0.5)
        assert len(result) >= 1
        assert "MatchScore" in result.columns

    def test_make_group(self) -> None:
        df = pd.DataFrame(
            {
                "A": ["X", "Y", "Z"],
                "B": ["Y", "Z", "W"],
            }
        )
        result = Join.make_group(df, "A", "B")
        assert "Group" in result.columns
        assert "Key" in result.columns
        # X-Y, Y-Z, Z-W should all be in the same group
        assert result["Group"].nunique() == 1

    def test_append_fields_empty_right(self) -> None:
        left = pd.DataFrame({"A": [1, 2]})
        right = pd.DataFrame({"B": pd.Series(dtype="int64")})
        result = Join.append_fields(left, right)
        assert len(result) == 0


# ====================================================================== #
#  I/O TOOLS
# ====================================================================== #


class TestIOTools:
    """InOut palette tool validation."""

    def test_csv_roundtrip(self, basic_df: pd.DataFrame, tmp_path: Path) -> None:
        path = tmp_path / "test.csv"
        InOut.output_data(basic_df, str(path))
        loaded = InOut.input_data(str(path))
        assert len(loaded) == len(basic_df)
        assert set(loaded.columns) == set(basic_df.columns)

    def test_parquet_roundtrip(self, basic_df: pd.DataFrame, tmp_path: Path) -> None:
        path = tmp_path / "test.parquet"
        InOut.output_data(basic_df, str(path))
        loaded = InOut.input_data(str(path))
        assert len(loaded) == len(basic_df)

    def test_json_roundtrip(self, basic_df: pd.DataFrame, tmp_path: Path) -> None:
        path = tmp_path / "test.json"
        InOut.output_data(basic_df, str(path))
        loaded = InOut.input_data(str(path))
        assert len(loaded) == len(basic_df)

    def test_input_data_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            InOut.input_data("nonexistent_file.csv")

    def test_input_data_unsupported_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "data.xyz"
        path.write_text("test")
        with pytest.raises(ValueError, match="Unsupported"):
            InOut.input_data(str(path))

    def test_output_creates_parent_dirs(self, basic_df: pd.DataFrame, tmp_path: Path) -> None:
        path = tmp_path / "sub" / "dir" / "output.csv"
        InOut.output_data(basic_df, str(path))
        assert path.exists()

    def test_text_input_list_of_lists(self) -> None:
        data = [[1, "a"], [2, "b"], [3, "c"]]
        result = InOut.text_input(data, columns=["Num", "Letter"])
        assert len(result) == 3
        assert list(result.columns) == ["Num", "Letter"]

    def test_text_input_list_of_lists_no_columns_raises(self) -> None:
        with pytest.raises(ValueError, match="columns"):
            InOut.text_input([[1, 2], [3, 4]])
