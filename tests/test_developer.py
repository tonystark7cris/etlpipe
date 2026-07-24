"""Tests for etlpipe.developer â€” Developer class."""

from __future__ import annotations

import base64

import pandas as pd
import pytest

from etlpipe import Developer


class TestBase64Encode:
    """Tests for Developer.base64_encode."""

    def test_encode(self) -> None:
        df = pd.DataFrame({"Secret": ["Hello", "World"]})
        result = Developer.base64_encode(df, "Secret")
        assert "Secret_Base64" in result.columns
        decoded = base64.b64decode(result["Secret_Base64"].iloc[0]).decode()
        assert decoded == "Hello"

    def test_custom_output_col(self) -> None:
        df = pd.DataFrame({"S": ["abc"]})
        result = Developer.base64_encode(df, "S", output_column="Encoded")
        assert "Encoded" in result.columns


class TestBase64Decode:
    """Tests for Developer.base64_decode."""

    def test_decode(self) -> None:
        encoded = base64.b64encode(b"Hello").decode()
        df = pd.DataFrame({"Encoded": [encoded]})
        result = Developer.base64_decode(df, "Encoded")
        assert result["Encoded_Decoded"].iloc[0] == "Hello"


class TestBase64RoundTrip:
    """Tests for encode â†’ decode round-trip."""

    def test_roundtrip(self) -> None:
        df = pd.DataFrame({"Data": ["test string 123!", "another value"]})
        encoded = Developer.base64_encode(df, "Data")
        decoded = Developer.base64_decode(encoded, "Data_Base64", output_column="Restored")
        assert decoded["Restored"].iloc[0] == "test string 123!"
        assert decoded["Restored"].iloc[1] == "another value"


class TestColumnInfo:
    """Tests for Developer.column_info."""

    def test_basic(self, sample_df: pd.DataFrame) -> None:
        result = Developer.column_info(sample_df)
        assert "Name" in result.columns
        assert "Type" in result.columns
        assert "NullCount" in result.columns
        assert len(result) == 5  # 5 columns in sample_df

    def test_with_nulls(self, sample_df_with_nulls: pd.DataFrame) -> None:
        result = Developer.column_info(sample_df_with_nulls)
        name_row = (
            result.loc[result["Name_col"] == "Name"]
            if "Name_col" in result.columns
            else result.loc[result["Name"] == "Name"]
        )
        assert name_row["NullCount"].iloc[0] == 2


class TestDynamicRename:
    """Tests for Developer.dynamic_rename."""

    def test_mapping_mode(self) -> None:
        df = pd.DataFrame({"col_a": [1], "col_b": [2]})
        mapping = pd.DataFrame({"OldName": ["col_a"], "NewName": ["Column A"]})
        result = Developer.dynamic_rename(df, mapping)
        assert "Column A" in result.columns
        assert "col_b" in result.columns  # unchanged

    def test_prefix_mode(self) -> None:
        df = pd.DataFrame({"A": [1], "B": [2]})
        prefix_df = pd.DataFrame({"P": ["pre_"]})
        result = Developer.dynamic_rename(df, prefix_df, mode="prefix")
        assert "pre_A" in result.columns
        assert "pre_B" in result.columns

    def test_suffix_mode(self) -> None:
        df = pd.DataFrame({"A": [1], "B": [2]})
        suffix_df = pd.DataFrame({"S": ["_suf"]})
        result = Developer.dynamic_rename(df, suffix_df, mode="suffix")
        assert "A_suf" in result.columns

    def test_invalid_mode(self) -> None:
        df = pd.DataFrame({"A": [1]})
        m = pd.DataFrame({"X": [1]})
        with pytest.raises(ValueError, match="Unknown mode"):
            Developer.dynamic_rename(df, m, mode="bad")


class TestJSONParse:
    """Tests for Developer.json_parse."""

    def test_json_parse(self) -> None:
        df = pd.DataFrame({"ID": [1, 2], "Data": ['{"name": "Alice", "age": 30}', '{"name": "Bob"}']})
        result = Developer.json_parse(df, "Data")
        assert "Data_name" in result.columns
        assert "Data_age" in result.columns
        assert result["Data_name"].iloc[0] == "Alice"
        assert result["Data_age"].iloc[0] == 30.0
        assert pd.isna(result["Data_age"].iloc[1])

    def test_json_parse_invalid(self) -> None:
        df = pd.DataFrame({"Data": ['{"name": "Alice"}', "invalid json"]})
        result = Developer.json_parse(df, "Data", prefix="J")
        assert result["J_name"].iloc[0] == "Alice"
        assert pd.isna(result["J_name"].iloc[1])


class TestDynamicSelect:
    """Tests for Developer.dynamic_select."""

    def test_dynamic_select_dtype(self) -> None:
        df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"], "C": [3.0, 4.0]})
        result = Developer.dynamic_select(df, dtype_include="number")
        assert "A" in result.columns
        assert "C" in result.columns
        assert "B" not in result.columns

    def test_dynamic_select_pattern(self) -> None:
        df = pd.DataFrame({"Sales_Q1": [100], "Sales_Q2": [200], "Cost": [50]})
        result = Developer.dynamic_select(df, pattern="^Sales_")
        assert "Sales_Q1" in result.columns
        assert "Sales_Q2" in result.columns
        assert "Cost" not in result.columns


class TestTestEqual:
    """Tests for Developer.test_equal."""

    def test_test_equal_pass(self) -> None:
        df1 = pd.DataFrame({"A": [1, 2]})
        df2 = pd.DataFrame({"A": [1, 2]})
        Developer.test_equal(df1, df2)

    def test_test_equal_fail(self) -> None:
        df1 = pd.DataFrame({"A": [1, 2]})
        df2 = pd.DataFrame({"A": [1, 3]})
        with pytest.raises(AssertionError):
            Developer.test_equal(df1, df2)


class TestTest:
    """Tests for Developer.test."""

    def test_test_pass(self) -> None:
        df = pd.DataFrame({"A": [10, 20]})
        result = Developer.test(df, lambda d: d["A"].sum() == 30)
        assert len(result) == 2

    def test_test_fail(self) -> None:
        df = pd.DataFrame({"A": [10, 20]})
        with pytest.raises(ValueError, match="Test condition failed"):
            Developer.test(df, lambda d: d["A"].sum() > 100)
