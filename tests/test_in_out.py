"""Tests for etlpipe.in_out — InOut class."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from etlpipe import InOut


class TestInputData:
    """Tests for InOut.input_data."""

    def test_read_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        pd.DataFrame({"A": [1, 2], "B": [3, 4]}).to_csv(csv_path, index=False)
        result = InOut.input_data(csv_path)
        assert list(result.columns) == ["A", "B"]
        assert len(result) == 2

    def test_read_json(self, tmp_path: Path) -> None:
        json_path = tmp_path / "data.json"
        pd.DataFrame({"X": [10, 20]}).to_json(json_path)
        result = InOut.input_data(json_path)
        assert "X" in result.columns

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            InOut.input_data("nonexistent_file.csv")

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        bad_path = tmp_path / "data.xyz"
        bad_path.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            InOut.input_data(bad_path)


class TestOutputData:
    """Tests for InOut.output_data."""

    def test_write_csv(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        out_path = tmp_path / "output.csv"
        InOut.output_data(df, out_path)
        assert out_path.exists()
        result = pd.read_csv(out_path)
        assert len(result) == 2

    def test_write_json(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"X": [10]})
        out_path = tmp_path / "output.json"
        InOut.output_data(df, out_path)
        assert out_path.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"A": [1]})
        out_path = tmp_path / "nested" / "dir" / "output.csv"
        InOut.output_data(df, out_path)
        assert out_path.exists()

    def test_type_error(self) -> None:
        with pytest.raises(TypeError):
            InOut.output_data("not a df", "output.csv")

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"A": [1]})
        with pytest.raises(ValueError, match="Unsupported"):
            InOut.output_data(df, tmp_path / "out.abc")


class TestTextInput:
    """Tests for InOut.text_input."""

    def test_dict_input(self) -> None:
        df = InOut.text_input({"Name": ["Alice", "Bob"], "Age": [30, 25]})
        assert list(df.columns) == ["Name", "Age"]
        assert len(df) == 2

    def test_records_input(self) -> None:
        df = InOut.text_input([{"A": 1, "B": 2}, {"A": 3, "B": 4}])
        assert len(df) == 2

    def test_list_of_lists(self) -> None:
        df = InOut.text_input([[1, 2], [3, 4]], columns=["X", "Y"])
        assert list(df.columns) == ["X", "Y"]

    def test_list_of_lists_no_columns_raises(self) -> None:
        with pytest.raises(ValueError, match="columns"):
            InOut.text_input([[1, 2]])


class TestBrowse:
    """Tests for InOut.browse."""

    def test_returns_same_df(self, sample_df: pd.DataFrame, capsys) -> None:
        result = InOut.browse(sample_df, n=3)
        assert result is sample_df  # Same object, not a copy
        captured = capsys.readouterr()
        assert "5 rows" in captured.out

    def test_type_error(self) -> None:
        with pytest.raises(TypeError):
            InOut.browse("not a df")


class TestDirectory:
    """Tests for InOut.directory."""

    def test_lists_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.txt").write_text("data")
        result = InOut.directory(tmp_path)
        assert len(result) == 2
        assert "FullPath" in result.columns
        assert "Size" in result.columns

    def test_glob_pattern(self, tmp_path: Path) -> None:
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.txt").write_text("data")
        result = InOut.directory(tmp_path, "*.csv")
        assert len(result) == 1

    def test_dir_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            InOut.directory("/nonexistent/path/abc123")


class TestDateTimeNow:
    """Tests for InOut.date_time_now."""

    def test_returns_single_row(self) -> None:
        result = InOut.date_time_now()
        assert len(result) == 1
        assert "DateTime" in result.columns
