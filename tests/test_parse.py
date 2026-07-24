"""Tests for etlpipe.parse â€” Parse class."""

from __future__ import annotations

import pandas as pd
import pytest

from etlpipe import Parse


class TestDateTime:
    """Tests for Parse.date_time."""

    def test_format_conversion(self, sample_dates_df: pd.DataFrame) -> None:
        result = Parse.date_time(sample_dates_df, "DateStr", input_fmt="%m/%d/%Y", output_fmt="%Y-%m-%d")
        assert result["DateStr"].iloc[0] == "2023-01-15"

    def test_infer_format(self) -> None:
        df = pd.DataFrame({"D": ["2023-01-01", "2023-06-15"]})
        result = Parse.date_time(df, "D")
        assert pd.api.types.is_datetime64_any_dtype(result["D"])


class TestRegexMatch:
    """Tests for Parse.regex_match."""

    def test_email_pattern(self, sample_text_df: pd.DataFrame) -> None:
        result = Parse.regex_match(sample_text_df, "Email", r"^[\w.]+@[\w.]+$")
        assert result["Match"].iloc[0]  # alice@example.com
        assert not result["Match"].iloc[2]  # invalid-email


class TestRegexParse:
    """Tests for Parse.regex_parse."""

    def test_extract_groups(self, sample_text_df: pd.DataFrame) -> None:
        result = Parse.regex_parse(sample_text_df, "FullName", r"(\w+)\s+(\w+)", output_cols=["First", "Last"])
        assert result["First"].iloc[0] == "Alice"
        assert result["Last"].iloc[0] == "Smith"

    def test_auto_names(self, sample_text_df: pd.DataFrame) -> None:
        result = Parse.regex_parse(sample_text_df, "FullName", r"(\w+)\s+(\w+)")
        assert "Group_1" in result.columns
        assert "Group_2" in result.columns

    def test_wrong_column_count(self, sample_text_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="output column names"):
            Parse.regex_parse(sample_text_df, "FullName", r"(\w+)\s+(\w+)", output_cols=["Only"])


class TestRegexReplace:
    """Tests for Parse.regex_replace."""

    def test_remove_digits(self) -> None:
        df = pd.DataFrame({"Phone": ["(123) 456-7890", "(987) 654-3210"]})
        result = Parse.regex_replace(df, "Phone", r"\D", "")
        assert result["Phone"].iloc[0] == "1234567890"


class TestRegexTokenize:
    """Tests for Parse.regex_tokenize."""

    def test_split_to_rows(self, sample_text_df: pd.DataFrame) -> None:
        result = Parse.regex_tokenize(sample_text_df, "Tags", r",", split_to="rows")
        # "python,data,ml" â†’ 3 rows, "sql,etl" â†’ 2 rows, "java,spring,boot,api" â†’ 4 rows = 9 total
        assert len(result) == 9

    def test_split_to_columns(self, sample_text_df: pd.DataFrame) -> None:
        result = Parse.regex_tokenize(sample_text_df, "Tags", r",", split_to="columns")
        assert "Tags_1" in result.columns

    def test_invalid_split_to(self, sample_text_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="Unknown split_to"):
            Parse.regex_tokenize(sample_text_df, "Tags", r",", split_to="bad")


class TestTextToColumns:
    """Tests for Parse.text_to_columns."""

    def test_split_to_columns(self) -> None:
        df = pd.DataFrame({"Skills": ["Python|SQL|R", "Java|C++"]})
        result = Parse.text_to_columns(df, "Skills", "|", split_to="columns")
        assert "Skills_1" in result.columns
        assert result["Skills_1"].iloc[0] == "Python"

    def test_split_to_rows(self) -> None:
        df = pd.DataFrame({"Skills": ["A|B", "C|D|E"]})
        result = Parse.text_to_columns(df, "Skills", "|", split_to="rows")
        assert len(result) == 5


class TestXMLParse:
    """Tests for Parse.xml_parse."""

    def test_extract_element(self) -> None:
        df = pd.DataFrame({"XML": ["<root><name>Alice</name></root>", "<root><name>Bob</name></root>"]})
        result = Parse.xml_parse(df, "XML", ".//name", "Name")
        assert result["Name"].iloc[0] == "Alice"
        assert result["Name"].iloc[1] == "Bob"

    def test_missing_element(self) -> None:
        df = pd.DataFrame({"XML": ["<root><age>30</age></root>"]})
        result = Parse.xml_parse(df, "XML", ".//name", "Name")
        assert result["Name"].iloc[0] is None

    def test_return_child_values(self) -> None:
        df = pd.DataFrame({"XML": ['<root><person id="1"><name>Alice</name><age>30</age></person></root>']})
        result = Parse.xml_parse(df, "XML", ".//person", "Person", return_child_values=True)
        assert "Person_id" in result.columns
        assert "Person_name" in result.columns
        assert "Person_age" in result.columns
        assert result["Person_id"].iloc[0] == "1"
        assert result["Person_name"].iloc[0] == "Alice"
        assert result["Person_age"].iloc[0] == "30"

    def test_return_outer_xml(self) -> None:
        df = pd.DataFrame({"XML": ["<root><name>Alice</name></root>"]})
        result = Parse.xml_parse(df, "XML", ".//name", "Name", return_outer_xml=True)
        assert result["Name"].iloc[0] == "Alice"
        assert "Name_OuterXML" in result.columns
        assert "<name>Alice</name>" in result["Name_OuterXML"].iloc[0]

    def test_return_child_and_outer(self) -> None:
        df = pd.DataFrame({"XML": ['<root><item v="x"><sub/></item></root>']})
        result = Parse.xml_parse(df, "XML", ".//item", "Item", return_child_values=True, return_outer_xml=True)
        assert result["Item_v"].iloc[0] == "x"
        assert result["Item_sub"].iloc[0] is None
        assert "Item_OuterXML" in result.columns
