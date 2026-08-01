"""Tests for value-level expectation rules in expect_schema."""

from __future__ import annotations

import pandas as pd
import pytest

from etlpipe_governance import SchemaViolationError, expect_schema


class TestMinValue:
    def test_pass(self):
        df = pd.DataFrame({"age": [18, 25, 65]})
        result = expect_schema(df, {"columns": {"age": {"dtype": "int", "min_value": 0}}})
        assert len(result) == 3

    def test_fail(self):
        df = pd.DataFrame({"age": [18, -5, 65]})
        with pytest.raises(SchemaViolationError, match="below min_value"):
            expect_schema(df, {"columns": {"age": {"dtype": "int", "min_value": 0}}})

    def test_nulls_ignored(self):
        df = pd.DataFrame({"age": pd.array([18, None, 65], dtype="Int64")})
        result = expect_schema(df, {"columns": {"age": {"dtype": "int", "min_value": 0, "nullable": True}}})
        assert len(result) == 3


class TestMaxValue:
    def test_pass(self):
        df = pd.DataFrame({"score": [0.1, 0.5, 1.0]})
        result = expect_schema(df, {"columns": {"score": {"dtype": "float", "max_value": 1.0}}})
        assert len(result) == 3

    def test_fail(self):
        df = pd.DataFrame({"score": [0.1, 0.5, 1.5]})
        with pytest.raises(SchemaViolationError, match="above max_value"):
            expect_schema(df, {"columns": {"score": {"dtype": "float", "max_value": 1.0}}})

    def test_combined_min_max(self):
        df = pd.DataFrame({"age": [-1, 50, 200]})
        with pytest.raises(SchemaViolationError) as exc_info:
            expect_schema(df, {"columns": {"age": {"dtype": "int", "min_value": 0, "max_value": 120}}})
        assert len(exc_info.value.violations) == 2  # both min and max violated


class TestAllowedValues:
    def test_pass(self):
        df = pd.DataFrame({"status": ["pending", "shipped", "cancelled"]})
        schema = {"columns": {"status": {"dtype": "str", "allowed_values": ["pending", "shipped", "cancelled"]}}}
        result = expect_schema(df, schema)
        assert len(result) == 3

    def test_fail(self):
        df = pd.DataFrame({"status": ["pending", "invalid_status", "shipped"]})
        schema = {"columns": {"status": {"dtype": "str", "allowed_values": ["pending", "shipped", "cancelled"]}}}
        with pytest.raises(SchemaViolationError, match="not in allowed_values"):
            expect_schema(df, schema)


class TestValueRegex:
    def test_pass(self):
        df = pd.DataFrame({"code": ["ABC-001", "DEF-002", "GHI-003"]})
        schema = {"columns": {"code": {"dtype": "str", "value_regex": r"[A-Z]{3}-\d{3}"}}}
        result = expect_schema(df, schema)
        assert len(result) == 3

    def test_fail(self):
        df = pd.DataFrame({"code": ["ABC-001", "bad", "GHI-003"]})
        schema = {"columns": {"code": {"dtype": "str", "value_regex": r"[A-Z]{3}-\d{3}"}}}
        with pytest.raises(SchemaViolationError, match="do not match value_regex"):
            expect_schema(df, schema)


class TestMinMaxLength:
    def test_max_length_pass(self):
        df = pd.DataFrame({"name": ["Alice", "Bob"]})
        schema = {"columns": {"name": {"dtype": "str", "max_length": 10}}}
        result = expect_schema(df, schema)
        assert len(result) == 2

    def test_max_length_fail(self):
        df = pd.DataFrame({"name": ["Alice", "A very long name indeed"]})
        schema = {"columns": {"name": {"dtype": "str", "max_length": 10}}}
        with pytest.raises(SchemaViolationError, match="longer than max_length"):
            expect_schema(df, schema)

    def test_min_length_pass(self):
        df = pd.DataFrame({"code": ["ABC", "DEFG"]})
        schema = {"columns": {"code": {"dtype": "str", "min_length": 3}}}
        result = expect_schema(df, schema)
        assert len(result) == 2

    def test_min_length_fail(self):
        df = pd.DataFrame({"code": ["AB", "DEFG"]})
        schema = {"columns": {"code": {"dtype": "str", "min_length": 3}}}
        with pytest.raises(SchemaViolationError, match="shorter than min_length"):
            expect_schema(df, schema)


class TestUnique:
    def test_pass(self):
        df = pd.DataFrame({"id": [1, 2, 3, 4]})
        schema = {"columns": {"id": {"dtype": "int", "unique": True}}}
        result = expect_schema(df, schema)
        assert len(result) == 4

    def test_fail(self):
        df = pd.DataFrame({"id": [1, 2, 2, 3]})
        schema = {"columns": {"id": {"dtype": "int", "unique": True}}}
        with pytest.raises(SchemaViolationError, match="duplicate"):
            expect_schema(df, schema)


class TestNonStrictMode:
    def test_value_violations_logged_not_raised(self):
        df = pd.DataFrame({"age": [-5, 200]})
        schema = {"columns": {"age": {"dtype": "int", "min_value": 0, "max_value": 120}}}
        result = expect_schema(df, schema, strict=False)
        assert len(result) == 2  # Returns the df without raising


class TestBackwardsCompatibility:
    def test_old_schema_still_works(self):
        """Old schemas with only dtype and nullable should still work."""
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        schema = {
            "columns": {
                "id": {"dtype": "int64", "nullable": False},
                "name": {"dtype": "object"},
            }
        }
        result = expect_schema(df, schema)
        assert len(result) == 3
