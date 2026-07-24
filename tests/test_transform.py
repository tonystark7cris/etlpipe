"""Tests for etlpipe.transform â€” Transform class."""

from __future__ import annotations

import pandas as pd
import pytest

from etlpipe import Transform


class TestSummarize:
    """Tests for Transform.summarize."""

    def test_group_sum(self, sales_df: pd.DataFrame) -> None:
        result = Transform.summarize(sales_df, group_by="Region", aggregations={"Revenue": "sum"})
        assert "Sum_Revenue" in result.columns
        east_total = result.loc[result["Region"] == "East", "Sum_Revenue"].iloc[0]
        assert east_total == 600  # 100 + 200 + 300

    def test_multiple_aggs(self, sales_df: pd.DataFrame) -> None:
        result = Transform.summarize(
            sales_df,
            group_by="Region",
            aggregations={"Revenue": ["sum", "mean"]},
        )
        assert "Sum_Revenue" in result.columns
        assert "Mean_Revenue" in result.columns

    def test_no_group(self, sales_df: pd.DataFrame) -> None:
        result = Transform.summarize(sales_df, aggregations={"Revenue": "sum"})
        assert result["Sum_Revenue"].iloc[0] == 1000

    def test_no_aggregations_raises(self, sales_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="aggregation"):
            Transform.summarize(sales_df)


class TestTranspose:
    """Tests for Transform.transpose."""

    def test_wide_to_long(self) -> None:
        df = pd.DataFrame({"ID": [1, 2], "Q1": [10, 20], "Q2": [30, 40]})
        result = Transform.transpose(df, key_columns="ID", data_columns=["Q1", "Q2"])
        assert "Name" in result.columns
        assert "Value" in result.columns
        assert len(result) == 4  # 2 IDs Ã— 2 quarters

    def test_default_data_columns(self) -> None:
        df = pd.DataFrame({"ID": [1, 2], "Q1": [10, 20], "Q2": [30, 40]})
        result = Transform.transpose(df, key_columns="ID")
        assert len(result) == 4
        assert set(result["Name"]) == {"Q1", "Q2"}


class TestCrossTab:
    """Tests for Transform.cross_tab."""

    def test_long_to_wide(self, sales_df: pd.DataFrame) -> None:
        result = Transform.cross_tab(sales_df, group_by="Region", pivot_col="Quarter", value_col="Revenue")
        assert "Q1" in result.columns
        assert "Q2" in result.columns


class TestRunningTotal:
    """Tests for Transform.running_total."""

    def test_simple(self) -> None:
        df = pd.DataFrame({"Value": [10, 20, 30]})
        result = Transform.running_total(df, "Value")
        assert result["RunningTotal_Value"].iloc[2] == 60

    def test_grouped(self, sales_df: pd.DataFrame) -> None:
        result = Transform.running_total(sales_df, "Revenue", group_by="Region")
        assert "RunningTotal_Revenue" in result.columns


class TestCountRecords:
    """Tests for Transform.count_records."""

    def test_count(self, sample_df: pd.DataFrame) -> None:
        result = Transform.count_records(sample_df)
        assert result["Count"].iloc[0] == 5

    def test_custom_col_name(self, sample_df: pd.DataFrame) -> None:
        result = Transform.count_records(sample_df, output_col="Total")
        assert result["Total"].iloc[0] == 5


class TestArrange:
    """Tests for Transform.arrange."""

    def test_arrange(self) -> None:
        df = pd.DataFrame(
            {
                "ID": [1, 2],
                "Q1_Sales": [10, 20],
                "Q1_Costs": [5, 10],
                "Q2_Sales": [15, 25],
                "Q2_Costs": [8, 12],
            }
        )
        result = Transform.arrange(
            df,
            key_columns="ID",
            output_mapping={
                "Sales": ["Q1_Sales", "Q2_Sales"],
                "Costs": ["Q1_Costs", "Q2_Costs"],
            },
        )
        assert len(result) == 4
        assert "Sales" in result.columns
        assert "Costs" in result.columns
        assert result["Sales"].tolist() == [10, 15, 20, 25]

    def test_arrange_no_mapping(self) -> None:
        df = pd.DataFrame({"ID": [1, 2]})
        result = Transform.arrange(df)
        assert len(result) == 2

    def test_arrange_invalid_mapping(self) -> None:
        df = pd.DataFrame({"ID": [1]})
        with pytest.raises(ValueError, match="same length"):
            Transform.arrange(df, output_mapping={"A": ["X"], "B": ["Y", "Z"]})


class TestMakeColumns:
    """Tests for Transform.make_columns."""

    def test_make_columns(self) -> None:
        df = pd.DataFrame({"Val": [1, 2, 3, 4, 5, 6]})
        result = Transform.make_columns(df, num_columns=3)
        assert len(result) == 2
        assert list(result.columns) == ["Val_1", "Val_2", "Val_3"]
        assert result["Val_1"].tolist() == [1, 4]
        assert result["Val_2"].tolist() == [2, 5]
        assert result["Val_3"].tolist() == [3, 6]

    def test_make_columns_invalid(self) -> None:
        df = pd.DataFrame({"Val": [1]})
        with pytest.raises(ValueError, match="at least 1"):
            Transform.make_columns(df, num_columns=0)

    def test_make_columns_1(self) -> None:
        df = pd.DataFrame({"Val": [1, 2]})
        result = Transform.make_columns(df, num_columns=1)
        assert list(result.columns) == ["Val"]


class TestWeightedAverage:
    """Tests for Transform.weighted_average."""

    def test_weighted_average(self) -> None:
        df = pd.DataFrame({"Val": [10, 20], "Weight": [1, 3]})
        result = Transform.weighted_average(df, "Val", "Weight")
        assert result["WeightedAverage"].iloc[0] == 17.5

    def test_weighted_average_group(self) -> None:
        df = pd.DataFrame({"Grp": ["A", "A", "B"], "Val": [10, 20, 50], "Weight": [1, 3, 2]})
        result = Transform.weighted_average(df, "Val", "Weight", group_by="Grp")
        assert len(result) == 2
        assert result.loc[result["Grp"] == "A", "WeightedAverage"].iloc[0] == 17.5
        assert result.loc[result["Grp"] == "B", "WeightedAverage"].iloc[0] == 50.0


class TestCustomAggregations:
    """Tests for custom aggregations in Summarize."""

    def test_count_distinct(self) -> None:
        df = pd.DataFrame({"ID": [1, 1, 2, 2, 2]})
        result = Transform.summarize(df, aggregations={"ID": "count distinct"})
        assert result["Count_distinct_ID"].iloc[0] == 2

    def test_count_null_and_blank(self) -> None:
        df = pd.DataFrame({"Val": ["A", None, "", "B", "  "]})
        result = Transform.summarize(df, aggregations={"Val": ["count null", "count blank", "count non blank"]})
        assert result["Count_null_Val"].iloc[0] == 1
        assert result["Count_blank_Val"].iloc[0] == 2  # "" and "  "
        assert result["Count_non_blank_Val"].iloc[0] == 2  # "A" and "B"

    def test_concatenate(self) -> None:
        df = pd.DataFrame({"Val": ["Apple", "Banana", "Apple", None]})
        result = Transform.summarize(df, aggregations={"Val": ["concatenate", "concatenate distinct"]})
        assert result["Concatenate_Val"].iloc[0] == "Apple,Banana,Apple"
        assert result["Concatenate_distinct_Val"].iloc[0] == "Apple,Banana"

    def test_longest_shortest(self) -> None:
        df = pd.DataFrame({"Val": ["A", "BB", "CCC", None]})
        result = Transform.summarize(df, aggregations={"Val": ["longest", "shortest"]})
        assert result["Longest_Val"].iloc[0] == "CCC"
        assert result["Shortest_Val"].iloc[0] == "A"

    def test_mode(self) -> None:
        df = pd.DataFrame({"Val": ["X", "Y", "X", "Z"]})
        result = Transform.summarize(df, aggregations={"Val": "mode"})
        assert result["Mode_Val"].iloc[0] == "X"

    def test_custom_aggs_empty(self) -> None:
        df = pd.DataFrame({"Val": pd.Series(dtype=str)})
        result = Transform.summarize(df, aggregations={"Val": ["longest", "shortest", "mode", "concatenate"]})
        assert pd.isna(result["Longest_Val"].iloc[0])
        assert pd.isna(result["Shortest_Val"].iloc[0])
        assert pd.isna(result["Mode_Val"].iloc[0])
        assert result["Concatenate_Val"].iloc[0] == ""
