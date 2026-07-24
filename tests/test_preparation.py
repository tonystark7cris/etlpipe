"""Tests for etlpipe.preparation — Preparation class."""

from __future__ import annotations

import pandas as pd
import pytest

from etlpipe import Preparation


class TestFilter:
    """Tests for Preparation.filter."""

    def test_string_condition(self, sample_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(sample_df, "Age > 30")
        assert len(t) == 2  # Charlie (35), Eve (32)
        assert len(f) == 3

    def test_callable_condition(self, sample_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(sample_df, lambda d: d["City"] == "Boston")
        assert len(t) == 2
        assert len(f) == 3

    def test_all_true(self, sample_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(sample_df, "Age > 0")
        assert len(t) == 5
        assert len(f) == 0

    def test_basic_filter_equals(self, sample_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(sample_df, column="City", operator="==", value="Boston")
        assert len(t) == 2
        assert len(f) == 3

    def test_basic_filter_contains(self, sample_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(sample_df, column="Name", operator="contains", value="li")
        assert len(t) == 2  # Alice, Charlie
        assert set(t["Name"]) == {"Alice", "Charlie"}
        assert len(f) == 3

    def test_basic_filter_is_null(self, sample_df_with_nulls: pd.DataFrame) -> None:
        t, f = Preparation.filter(sample_df_with_nulls, column="Name", operator="is null")
        assert len(t) == 2
        assert len(f) == 3

    def test_basic_filter_is_not_null(self, sample_df_with_nulls: pd.DataFrame) -> None:
        t, f = Preparation.filter(sample_df_with_nulls, column="Name", operator="is not null")
        assert len(t) == 3
        assert len(f) == 2

    def test_basic_filter_does_not_equal(self, sample_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(sample_df, column="City", operator="!=", value="Boston")
        assert len(t) == 3
        assert len(f) == 2

    def test_basic_filter_comparisons(self, sample_df: pd.DataFrame) -> None:
        # >
        t, _ = Preparation.filter(sample_df, column="Age", operator=">", value=30)
        assert len(t) == 2
        # >=
        t, _ = Preparation.filter(sample_df, column="Age", operator=">=", value=30)
        assert len(t) == 3
        # <
        t, _ = Preparation.filter(sample_df, column="Age", operator="<", value=30)
        assert len(t) == 2
        # <=
        t, _ = Preparation.filter(sample_df, column="Age", operator="<=", value=30)
        assert len(t) == 3

    def test_basic_filter_empty(self, sample_df_with_nulls: pd.DataFrame) -> None:
        df = pd.DataFrame({"Val": ["a", "", None, "b"]})
        # is empty
        t, f = Preparation.filter(df, column="Val", operator="is empty")
        assert len(t) == 2  # "" and None
        assert len(f) == 2
        # is not empty
        t, f = Preparation.filter(df, column="Val", operator="is not empty")
        assert len(t) == 2  # "a" and "b"

    def test_basic_filter_does_not_contain(self, sample_df: pd.DataFrame) -> None:
        t, f = Preparation.filter(sample_df, column="Name", operator="does not contain", value="li")
        assert len(t) == 3
        assert len(f) == 2

    def test_basic_filter_booleans(self) -> None:
        df = pd.DataFrame({"Flag": [True, False, True]})
        t, f = Preparation.filter(df, column="Flag", operator="is true")
        assert len(t) == 2
        t, f = Preparation.filter(df, column="Flag", operator="is false")
        assert len(t) == 1

    def test_basic_filter_invalid_args(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="either 'condition' or both"):
            Preparation.filter(sample_df, column="City")

        with pytest.raises(ValueError, match="Unsupported filter operator"):
            Preparation.filter(sample_df, column="Age", operator="MAGIC", value=30)


class TestFormula:
    """Tests for Preparation.formula."""

    def test_expression_string(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.formula(sample_df, "DoubleSalary", "Salary * 2")
        assert "DoubleSalary" in result.columns
        assert result["DoubleSalary"].iloc[0] == 140000

    def test_callable_expression(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.formula(sample_df, "UpperName", lambda d: d["Name"].str.upper())
        assert result["UpperName"].iloc[0] == "ALICE"

    def test_does_not_mutate(self, sample_df: pd.DataFrame) -> None:
        Preparation.formula(sample_df, "New", "Age + 1")
        assert "New" not in sample_df.columns

    def test_fallback_eval(self, sample_df: pd.DataFrame) -> None:
        # pd.eval can't handle function calls like print(), which previously forced an insecure eval() fallback
        # We now assert that this raises a safe ValueError
        import pytest

        with pytest.raises(ValueError, match="Could not safely evaluate formula"):
            Preparation.formula(sample_df, "Print", "print('hello')")

    def test_spaces_in_columns(self) -> None:
        # Tests the auto-backticking transpiler for spaces in column names
        df = pd.DataFrame({"Customer Name": ["Alice", "Bob"]})
        result = Preparation.formula(df, "IsAlice", "Customer Name == 'Alice'")
        assert result["IsAlice"].iloc[0]
        assert not result["IsAlice"].iloc[1]


class TestSelect:
    """Tests for Preparation.select."""

    def test_select_columns(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.select(sample_df, columns=["Name", "Age"])
        assert list(result.columns) == ["Name", "Age"]

    def test_rename(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.select(sample_df, renames={"Name": "FullName"})
        assert "FullName" in result.columns
        assert "Name" not in result.columns

    def test_dtype_cast(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.select(sample_df, dtypes={"Age": "float64"})
        assert result["Age"].dtype == "float64"


class TestDataCleansing:
    """Tests for Preparation.data_cleansing."""

    def test_strip_whitespace(self) -> None:
        df = pd.DataFrame({"Name": ["  Alice  ", "  Bob  "]})
        result = Preparation.data_cleansing(df, columns=["Name"], strip_whitespace=True)
        assert result["Name"].iloc[0] == "Alice"

    def test_replace_nulls(self, sample_df_with_nulls: pd.DataFrame) -> None:
        result = Preparation.data_cleansing(sample_df_with_nulls, columns=["Name"], replace_nulls_with="Unknown")
        assert "Unknown" in result["Name"].values

    def test_remove_punctuation(self) -> None:
        df = pd.DataFrame({"Text": ["Hello, World!", "Test..."]})
        result = Preparation.data_cleansing(df, columns=["Text"], remove_punctuation=True)
        assert result["Text"].iloc[0] == "Hello World"

    def test_all_string_columns_default(self) -> None:
        df = pd.DataFrame({"A": [" a "], "B": [1], "C": [" c "]})
        result = Preparation.data_cleansing(df, strip_whitespace=True)
        assert result["A"].iloc[0] == "a"
        assert result["C"].iloc[0] == "c"

    def test_remove_null_rows(self) -> None:
        df = pd.DataFrame({"A": [1, None, 3], "B": [1, 2, None]})
        result = Preparation.data_cleansing(df, columns=["A", "B"], remove_null_rows=True)
        assert len(result) == 1
        assert result["A"].iloc[0] == 1.0

    def test_remove_letters_numbers(self) -> None:
        df = pd.DataFrame({"Text": ["A1B2", "C3D4"]})
        result = Preparation.data_cleansing(df, columns=["Text"], remove_letters=True)
        assert result["Text"].iloc[0] == "12"
        result2 = Preparation.data_cleansing(df, columns=["Text"], remove_numbers=True)
        assert result2["Text"].iloc[0] == "AB"

    def test_modify_case(self) -> None:
        df = pd.DataFrame({"Text": ["hello WORLD"]})
        res_lower = Preparation.data_cleansing(df, columns=["Text"], modify_case="lower")
        assert res_lower["Text"].iloc[0] == "hello world"
        res_upper = Preparation.data_cleansing(df, columns=["Text"], modify_case="upper")
        assert res_upper["Text"].iloc[0] == "HELLO WORLD"
        res_title = Preparation.data_cleansing(df, columns=["Text"], modify_case="title")
        assert res_title["Text"].iloc[0] == "Hello World"


class TestSort:
    """Tests for Preparation.sort."""

    def test_ascending(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.sort(sample_df, "Age")
        assert result["Age"].iloc[0] == 25

    def test_descending(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.sort(sample_df, "Age", ascending=False)
        assert result["Age"].iloc[0] == 35

    def test_multi_column(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.sort(sample_df, ["City", "Age"])
        assert len(result) == 5


class TestUnique:
    """Tests for Preparation.unique."""

    def test_unique_split(self, sample_df: pd.DataFrame) -> None:
        uniq, dups = Preparation.unique(sample_df, "City")
        assert len(uniq) + len(dups) == len(sample_df)
        # Boston and New York both appear twice → 2 duplicates
        assert len(dups) == 2

    def test_all_unique(self) -> None:
        df = pd.DataFrame({"X": [1, 2, 3]})
        uniq, dups = Preparation.unique(df, "X")
        assert len(uniq) == 3
        assert len(dups) == 0

    def test_ignore_case(self) -> None:
        df = pd.DataFrame({"City": ["Boston", "boston", "NEW YORK", "new york"]})
        uniq, dups = Preparation.unique(df, "City", ignore_case=True)
        assert len(uniq) == 2  # Boston, NEW YORK
        assert len(dups) == 2  # boston, new york
        assert uniq["City"].iloc[0] == "Boston"
        assert uniq["City"].iloc[1] == "NEW YORK"


class TestSample:
    """Tests for Preparation.sample."""

    def test_first_n(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.sample(sample_df, n=2)
        assert len(result) == 2

    def test_last_n(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.sample(sample_df, n=2, position="last")
        assert len(result) == 2

    def test_random(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.sample(sample_df, n=3, random=True, random_state=42)
        assert len(result) == 3

    def test_pct(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.sample(sample_df, pct=0.4)
        assert len(result) == 2

    def test_error_both(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="not both"):
            Preparation.sample(sample_df, n=2, pct=0.5)

    def test_error_neither(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="either"):
            Preparation.sample(sample_df)


class TestRecordID:
    """Tests for Preparation.record_id."""

    def test_default(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.record_id(sample_df)
        assert result.columns[0] == "RecordID"
        assert result["RecordID"].iloc[0] == 1
        assert result["RecordID"].iloc[-1] == 5

    def test_custom_name_and_start(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.record_id(sample_df, "RowNum", start=100)
        assert result["RowNum"].iloc[0] == 100


class TestGenerateRows:
    """Tests for Preparation.generate_rows."""

    def test_simple(self) -> None:
        result = Preparation.generate_rows(5)
        assert len(result) == 5
        assert "RowNum" in result.columns

    def test_with_expression(self) -> None:
        result = Preparation.generate_rows(3, lambda i: {"x": i, "y": i**2})
        assert list(result.columns) == ["x", "y"]
        assert result["y"].iloc[2] == 4

    def test_with_columns(self) -> None:
        result = Preparation.generate_rows(2, lambda i: {"y": i, "x": i}, columns=["x", "y"])
        assert list(result.columns) == ["x", "y"]


class TestAutoField:
    """Tests for Preparation.auto_field."""

    def test_optimizes_types(self) -> None:
        df = pd.DataFrame(
            {
                "A": [1, 2, 3, 4, 5, 6],
                "B": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                "C": ["a", "b", "a", "b", "a", "b"],  # 2 unique / 6 rows = 33% < 50%
            }
        )
        result = Preparation.auto_field(df)
        # Category conversion for low-cardinality strings
        assert str(result["C"].dtype) == "category"


class TestMultiFieldFormula:
    """Tests for Preparation.multi_field_formula."""

    def test_double(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.multi_field_formula(sample_df, ["Age", "Salary"], lambda s: s * 2)
        assert result["Age"].iloc[0] == 60
        assert result["Salary"].iloc[0] == 140000


class TestMultiRowFormula:
    """Tests for Preparation.multi_row_formula."""

    def test_running_difference(self) -> None:
        df = pd.DataFrame({"Value": [10, 20, 35, 50]})
        result = Preparation.multi_row_formula(df, "Value", lambda cur, prev: cur - prev, rows_back=1)
        assert pd.isna(result["Value"].iloc[0])  # No previous row
        assert result["Value"].iloc[1] == 10.0

    def test_with_group_by(self) -> None:
        df = pd.DataFrame({"Group": ["A", "A", "B", "B"], "Value": [10, 20, 10, 30]})
        result = Preparation.multi_row_formula(df, "Value", lambda cur, prev: cur - prev, rows_back=1, group_by="Group")
        assert pd.isna(result["Value"].iloc[0])
        assert result["Value"].iloc[1] == 10.0
        assert pd.isna(result["Value"].iloc[2])  # First of group B
        assert result["Value"].iloc[3] == 20.0


class TestTile:
    """Tests for Preparation.tile."""

    def test_equal_records(self, sample_df: pd.DataFrame) -> None:
        result = Preparation.tile(sample_df, "Age", 2)
        assert "Tile" in result.columns

    def test_equal_range(self) -> None:
        df = pd.DataFrame({"Value": [10, 20, 30, 40, 50]})
        result = Preparation.tile(df, "Value", 2, method="equal_range")
        assert "Tile" in result.columns
        assert list(result["Tile"].unique()) == [1, 2]

    def test_invalid_method(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="Unknown method"):
            Preparation.tile(sample_df, "Age", 2, method="bad")


class TestImputation:
    """Tests for Preparation.imputation."""

    def test_mean(self, sample_df_with_nulls: pd.DataFrame) -> None:
        result = Preparation.imputation(sample_df_with_nulls, "Score", method="mean")
        assert result["Score"].isna().sum() == 0
        assert "Score_WasImputed" in result.columns

    def test_value(self, sample_df_with_nulls: pd.DataFrame) -> None:
        result = Preparation.imputation(sample_df_with_nulls, "Score", method="value", replacement_value=0)
        assert (result.loc[result["Score_WasImputed"], "Score"] == 0).all()

    def test_value_no_replacement_raises(self, sample_df_with_nulls: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="replacement_value"):
            Preparation.imputation(sample_df_with_nulls, "Score", method="value")

    def test_median(self, sample_df_with_nulls: pd.DataFrame) -> None:
        result = Preparation.imputation(sample_df_with_nulls, "Score", method="median")
        assert result["Score"].isna().sum() == 0

    def test_mode(self) -> None:
        df = pd.DataFrame({"Val": [1, 1, 2, None]})
        result = Preparation.imputation(df, "Val", method="mode")
        assert result["Val"].iloc[3] == 1.0

    def test_mode_empty(self) -> None:
        df = pd.DataFrame({"Val": [None, None]})
        result = Preparation.imputation(df, "Val", method="mode")
        assert pd.isna(result["Val"].iloc[0])

    def test_invalid_method(self) -> None:
        df = pd.DataFrame({"Val": [1, None]})
        with pytest.raises(ValueError, match="Unknown method"):
            Preparation.imputation(df, "Val", method="invalid")


class TestCreateSamples:
    """Tests for Preparation.create_samples."""

    def test_create_samples(self) -> None:
        df = pd.DataFrame({"ID": range(100)})
        est, val, hold = Preparation.create_samples(df, 0.5, 0.3, 0.2, random_state=42)
        assert len(est) == 50
        assert len(val) == 30
        assert len(hold) == 20

    def test_invalid_pct(self) -> None:
        df = pd.DataFrame({"ID": range(100)})
        with pytest.raises(ValueError, match="sum to 1.0"):
            Preparation.create_samples(df, 0.5, 0.5, 0.1)


class TestDateFilter:
    """Tests for Preparation.date_filter."""

    def test_date_filter(self) -> None:
        df = pd.DataFrame({"Date": ["2023-01-01", "2023-05-15", "2023-12-31"]})
        t, f = Preparation.date_filter(df, "Date", start_date="2023-03-01", end_date="2023-06-01")
        assert len(t) == 1
        assert t["Date"].iloc[0] == "2023-05-15"
        assert len(f) == 2


class TestOversampleField:
    """Tests for Preparation.oversample_field."""

    def test_oversample_field(self) -> None:
        df = pd.DataFrame({"Class": ["A", "B", "B", "B", "B"]})
        result = Preparation.oversample_field(df, "Class", "A", target_pct=0.5, random_state=42)
        # B has 4 records. We want 50% A, so we need 4 A's. Total length = 8.
        assert len(result) == 8
        assert (result["Class"] == "A").sum() == 4
        assert (result["Class"] == "B").sum() == 4

    def test_invalid_pct(self) -> None:
        df = pd.DataFrame({"Class": ["A", "B"]})
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            Preparation.oversample_field(df, "Class", "A", target_pct=1.5)


class TestRank:
    """Tests for Preparation.rank."""

    def test_rank_basic(self) -> None:
        df = pd.DataFrame({"Score": [10, 30, 20]})
        result = Preparation.rank(df, "Score", ascending=False)
        assert list(result["Rank"]) == [3, 1, 2]

    def test_rank_group_by(self) -> None:
        df = pd.DataFrame({"Group": ["A", "A", "B", "B"], "Score": [10, 20, 10, 5]})
        result = Preparation.rank(df, "Score", group_by="Group", ascending=False)
        assert result["Rank"].iloc[0] == 2  # Group A, 10
        assert result["Rank"].iloc[1] == 1  # Group A, 20
        assert result["Rank"].iloc[2] == 1  # Group B, 10
        assert result["Rank"].iloc[3] == 2  # Group B, 5
