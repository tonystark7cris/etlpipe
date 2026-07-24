"""Tests for etlpipe._contracts — schema validation and data contracts."""

from __future__ import annotations

import pandas as pd
import pytest

from etlpipe._contracts import (
    SchemaViolationError,
    _dtype_matches,
    expect_schema,
    infer_schema,
)

# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "Name": ["Alice", "Bob", "Charlie"],
            "Score": [95.5, 88.0, 72.5],
        }
    )


@pytest.fixture
def sample_schema() -> dict:
    return {
        "columns": {
            "ID": {"dtype": "int64", "nullable": False},
            "Name": {"dtype": "object", "nullable": True},
            "Score": {"dtype": "float64", "nullable": True},
        }
    }


# ------------------------------------------------------------------ #
# infer_schema tests
# ------------------------------------------------------------------ #


class TestInferSchema:
    def test_basic_inference(self, sample_df):
        schema = infer_schema(sample_df)
        assert "columns" in schema
        assert set(schema["columns"].keys()) == {"ID", "Name", "Score"}

    def test_dtype_captured(self, sample_df):
        schema = infer_schema(sample_df)
        assert schema["columns"]["ID"]["dtype"] == "int64"
        assert schema["columns"]["Name"]["dtype"] == "object"
        assert schema["columns"]["Score"]["dtype"] == "float64"

    def test_nullable_detected(self):
        df = pd.DataFrame({"A": [1, None, 3], "B": [4, 5, 6]})
        schema = infer_schema(df)
        assert schema["columns"]["A"]["nullable"] is True
        assert schema["columns"]["B"]["nullable"] is False

    def test_empty_df(self):
        df = pd.DataFrame({"A": pd.Series([], dtype="int64")})
        schema = infer_schema(df)
        assert schema["columns"]["A"]["dtype"] == "int64"
        assert schema["columns"]["A"]["nullable"] is False


# ------------------------------------------------------------------ #
# expect_schema tests — happy path
# ------------------------------------------------------------------ #


class TestExpectSchemaPass:
    def test_valid_schema(self, sample_df, sample_schema):
        result = expect_schema(sample_df, sample_schema)
        assert result is sample_df  # Returns the same DataFrame

    def test_round_trip(self, sample_df):
        """infer_schema -> expect_schema should always pass."""
        schema = infer_schema(sample_df)
        result = expect_schema(sample_df, schema)
        assert result is sample_df

    def test_canonical_group_int(self, sample_df):
        schema = {"columns": {"ID": {"dtype": "int"}}}
        expect_schema(sample_df, schema)  # Should not raise

    def test_canonical_group_str(self, sample_df):
        schema = {"columns": {"Name": {"dtype": "str"}}}
        expect_schema(sample_df, schema)  # Should not raise

    def test_canonical_group_float(self, sample_df):
        schema = {"columns": {"Score": {"dtype": "float"}}}
        expect_schema(sample_df, schema)  # Should not raise

    def test_any_dtype_wildcard(self, sample_df):
        schema = {"columns": {"ID": {"dtype": "any"}, "Name": {"dtype": "any"}}}
        expect_schema(sample_df, schema)  # Should not raise

    def test_nullable_true_allows_nulls(self):
        df = pd.DataFrame({"A": [1, None, 3]})
        schema = {"columns": {"A": {"dtype": "any", "nullable": True}}}
        expect_schema(df, schema)  # Should not raise

    def test_extra_columns_allowed(self, sample_df):
        schema = {"columns": {"ID": {"dtype": "int64"}}}
        expect_schema(sample_df, schema)  # Extra cols Name, Score are fine

    def test_empty_schema_skips(self, sample_df):
        result = expect_schema(sample_df, {"columns": {}})
        assert result is sample_df


# ------------------------------------------------------------------ #
# expect_schema tests — violations
# ------------------------------------------------------------------ #


class TestExpectSchemaViolations:
    def test_missing_column(self, sample_df):
        schema = {"columns": {"NonExistent": {"dtype": "int64"}}}
        with pytest.raises(SchemaViolationError) as exc_info:
            expect_schema(sample_df, schema)
        assert "Missing column: 'NonExistent'" in str(exc_info.value)

    def test_wrong_dtype(self, sample_df):
        schema = {"columns": {"ID": {"dtype": "float64"}}}
        with pytest.raises(SchemaViolationError) as exc_info:
            expect_schema(sample_df, schema)
        assert "expected dtype 'float64'" in str(exc_info.value)

    def test_non_nullable_violation(self):
        df = pd.DataFrame({"A": [1, None, 3]})
        schema = {"columns": {"A": {"dtype": "any", "nullable": False}}}
        with pytest.raises(SchemaViolationError) as exc_info:
            expect_schema(df, schema)
        assert "non-nullable" in str(exc_info.value)
        assert "1 null(s)" in str(exc_info.value)

    def test_multiple_violations(self):
        df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
        schema = {
            "columns": {
                "A": {"dtype": "str"},
                "B": {"dtype": "int64"},
                "C": {"dtype": "any"},
            }
        }
        with pytest.raises(SchemaViolationError) as exc_info:
            expect_schema(df, schema)
        assert len(exc_info.value.violations) == 3  # 2 wrong dtypes + 1 missing

    def test_non_strict_mode_warns(self, sample_df, caplog):
        schema = {"columns": {"NonExistent": {"dtype": "int64"}}}
        import logging

        with caplog.at_level(logging.WARNING, logger="etlpipe.contracts"):
            result = expect_schema(sample_df, schema, strict=False)
        assert result is sample_df
        assert "Schema violation" in caplog.text

    def test_type_error_non_dataframe(self):
        with pytest.raises(TypeError, match="Expected a pandas DataFrame"):
            expect_schema([1, 2, 3], {"columns": {}})


# ------------------------------------------------------------------ #
# _dtype_matches tests
# ------------------------------------------------------------------ #


class TestDtypeMatches:
    def test_exact_match(self):
        assert _dtype_matches("int64", "int64") is True

    def test_canonical_int(self):
        assert _dtype_matches("int64", "int") is True
        assert _dtype_matches("int32", "int") is True
        assert _dtype_matches("Int64", "int") is True

    def test_canonical_float(self):
        assert _dtype_matches("float64", "float") is True
        assert _dtype_matches("float32", "float") is True

    def test_canonical_str(self):
        assert _dtype_matches("object", "str") is True
        assert _dtype_matches("string", "str") is True

    def test_any_wildcard(self):
        assert _dtype_matches("int64", "any") is True
        assert _dtype_matches("object", "any") is True

    def test_mismatch(self):
        assert _dtype_matches("int64", "float64") is False
        assert _dtype_matches("object", "int") is False


# ------------------------------------------------------------------ #
# Backward-compatibility shim tests
# ------------------------------------------------------------------ #


class TestBackwardCompatShim:
    """Verify that the etlpipe.* import paths still work after the spinoff."""

    def test_expect_schema_importable_from_etlpipe(self):
        from etlpipe import expect_schema as es

        assert callable(es)

    def test_infer_schema_importable_from_etlpipe(self):
        from etlpipe import infer_schema as is_

        assert callable(is_)

    def test_schema_violation_error_importable_from_etlpipe(self):
        from etlpipe import SchemaViolationError

        assert issubclass(SchemaViolationError, Exception)

    def test_shim_and_governance_are_same_class(self):
        from etlpipe._contracts import SchemaViolationError as shim_cls
        from etlpipe_governance.contracts import SchemaViolationError as gov_cls

        assert shim_cls is gov_cls

    def test_shim_expect_schema_works_end_to_end(self):
        from etlpipe import expect_schema

        df = pd.DataFrame({"ID": [1, 2, 3]})
        result = expect_schema(df, {"columns": {"ID": {"dtype": "int64"}}})
        assert result is df

    def test_shim_infer_schema_works_end_to_end(self):
        from etlpipe import infer_schema

        df = pd.DataFrame({"X": [1.0, 2.0]})
        schema = infer_schema(df)
        assert "columns" in schema
        assert "X" in schema["columns"]
