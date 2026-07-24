"""Tests for etlpipe.join â€” Join class."""

from __future__ import annotations

import pandas as pd
import pytest

from etlpipe import Join


class TestJoin:
    """Tests for Join.join."""

    def test_basic_join(self, left_df: pd.DataFrame, right_df: pd.DataFrame) -> None:
        L, J, R = Join.join(left_df, right_df, on="CustomerID")
        # CustomerID 2 and 3 match
        assert len(J) == 2
        # CustomerID 1 and 4 are left-only
        assert len(L) == 2
        # CustomerID 5 is right-only
        assert len(R) == 1

    def test_all_match(self) -> None:
        df1 = pd.DataFrame({"K": [1, 2], "V1": ["a", "b"]})
        df2 = pd.DataFrame({"K": [1, 2], "V2": ["x", "y"]})
        L, J, R = Join.join(df1, df2, on="K")
        assert len(J) == 2
        assert len(L) == 0
        assert len(R) == 0

    def test_datatype_drift_coercion(self) -> None:
        # Test joining an integer column to a string column
        df1 = pd.DataFrame({"ID": [1, 2], "V1": ["a", "b"]})  # int64
        df2 = pd.DataFrame({"ID": ["1", "3"], "V2": ["x", "y"]})  # object/string
        L, J, R = Join.join(df1, df2, on="ID")

        # ID 1 should match despite the datatype drift
        assert len(J) == 1
        assert J["ID"].iloc[0] == 1
        assert len(L) == 1
        assert len(R) == 1

    def test_no_match(self) -> None:
        df1 = pd.DataFrame({"K": [1], "V1": ["a"]})
        df2 = pd.DataFrame({"K": [2], "V2": ["x"]})
        L, J, R = Join.join(df1, df2, on="K")
        assert len(J) == 0
        assert len(L) == 1
        assert len(R) == 1

    def test_left_on_right_on(self) -> None:
        df1 = pd.DataFrame({"ID_A": [1, 2], "V": ["a", "b"]})
        df2 = pd.DataFrame({"ID_B": [2, 3], "W": ["x", "y"]})
        L, J, R = Join.join(df1, df2, left_on="ID_A", right_on="ID_B")
        assert len(J) == 1


class TestJoinMultiple:
    """Tests for Join.join_multiple."""

    def test_three_dfs(self) -> None:
        df1 = pd.DataFrame({"ID": [1, 2], "A": [10, 20]})
        df2 = pd.DataFrame({"ID": [1, 2], "B": [30, 40]})
        df3 = pd.DataFrame({"ID": [1, 2], "C": [50, 60]})
        result = Join.join_multiple(df1, df2, df3, on="ID")
        assert "A" in result.columns
        assert "C" in result.columns
        assert len(result) == 2

    def test_too_few(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            Join.join_multiple(pd.DataFrame({"A": [1]}))


class TestUnion:
    """Tests for Join.union."""

    def test_by_name(self) -> None:
        df1 = pd.DataFrame({"A": [1], "B": [2]})
        df2 = pd.DataFrame({"A": [3], "B": [4]})
        result = Join.union(df1, df2)
        assert len(result) == 2

    def test_by_position(self) -> None:
        df1 = pd.DataFrame({"X": [1], "Y": [2]})
        df2 = pd.DataFrame({"A": [3], "B": [4]})
        result = Join.union(df1, df2, by="position")
        assert list(result.columns) == ["X", "Y"]
        assert len(result) == 2

    def test_too_few(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            Join.union(pd.DataFrame({"A": [1]}))


class TestFindReplace:
    """Tests for Join.find_replace."""

    def test_entire_replace(self) -> None:
        df = pd.DataFrame({"State": ["CA", "NY", "TX"]})
        mapping = pd.DataFrame({"State": ["CA", "NY"], "Full": ["California", "New York"]})
        result = Join.find_replace(df, mapping, "State", "Full")
        assert result["State"].iloc[0] == "California"
        assert result["State"].iloc[2] == "TX"  # Not in mapping, unchanged

    def test_partial_replace(self) -> None:
        df = pd.DataFrame({"Text": ["Hello World", "Hello Python"]})
        mapping = pd.DataFrame({"Find": ["Hello"], "Replace": ["Hi"]})
        result = Join.find_replace(df, mapping, "Find", "Replace", target_col="Text", mode="partial")
        assert result["Text"].iloc[0] == "Hi World"

    def test_entire_append(self) -> None:
        df = pd.DataFrame({"State": ["CA", "NY", "TX"]})
        mapping = pd.DataFrame({"State": ["CA", "NY"], "Full": ["California", "New York"]})
        result = Join.find_replace(df, mapping, "State", "Full", append=True)
        assert "Full" in result.columns
        assert result["Full"].iloc[0] == "California"
        assert pd.isna(result["Full"].iloc[2])
        assert result["State"].iloc[0] == "CA"  # Original unmodified

    def test_partial_append(self) -> None:
        df = pd.DataFrame({"Text": ["Apple Pie", "Banana Bread", "Cherry Tart"]})
        mapping = pd.DataFrame({"Find": ["Apple", "Cherry"], "Category": ["Fruit", "Fruit"]})
        result = Join.find_replace(df, mapping, "Find", "Category", target_col="Text", mode="partial", append=True)
        assert "Category" in result.columns
        assert result["Category"].iloc[0] == "Fruit"
        assert pd.isna(result["Category"].iloc[1])
        assert result["Category"].iloc[2] == "Fruit"


class TestMakeGroup:
    """Tests for Join.make_group."""

    def test_basic_group(self) -> None:
        # A=B, B=C, D=E. Groups should be {A,B,C} and {D,E}
        df = pd.DataFrame({"Key1": ["A", "B", "D"], "Key2": ["B", "C", "E"]})
        result = Join.make_group(df, "Key1", "Key2")
        # Smallest element in {A,B,C} is A. Smallest in {D,E} is D.
        assert len(result) == 5
        assert set(result["Group"].unique()) == {"A", "D"}
        assert len(result[result["Group"] == "A"]) == 3
        assert len(result[result["Group"] == "D"]) == 2

    def test_single_nodes(self) -> None:
        # X maps to NaN, should be in group X
        df = pd.DataFrame({"K1": ["X", "Y"], "K2": [float("nan"), "Z"]})
        result = Join.make_group(df, "K1", "K2")
        assert len(result) == 3
        assert set(result["Group"].unique()) == {"X", "Y"}


class TestAppendFields:
    """Tests for Join.append_fields."""

    def test_cross_join(self) -> None:
        df1 = pd.DataFrame({"Size": ["S", "M"]})
        df2 = pd.DataFrame({"Color": ["Red", "Blue"]})
        result = Join.append_fields(df1, df2)
        assert len(result) == 4  # 2 Ã— 2


class TestFuzzyMatch:
    """Tests for Join.fuzzy_match."""

    def test_basic_match(self) -> None:
        df1 = pd.DataFrame({"Company": ["Alphabet Inc", "Microsoft Corp"]})
        df2 = pd.DataFrame({"Name": ["Alphabet", "Apple Inc"]})
        result = Join.fuzzy_match(df1, df2, "Company", "Name", threshold=0.5)
        assert len(result) >= 1
        assert "MatchScore" in result.columns

    def test_high_threshold_no_match(self) -> None:
        df1 = pd.DataFrame({"A": ["xyz"]})
        df2 = pd.DataFrame({"B": ["abc"]})
        result = Join.fuzzy_match(df1, df2, "A", "B", threshold=0.99)
        assert len(result) == 0
