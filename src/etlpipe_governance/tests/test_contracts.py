"""Tests for etlpipe_governance.contracts — schema contracts, profiling, ContractSuite."""

from __future__ import annotations

import logging

import pandas as pd
import pytest

from etlpipe_governance.contracts import (
    ContractSuite,
    SchemaViolationError,
    _dtype_matches,
    expect_schema,
    infer_schema,
    profile,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# infer_schema
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# expect_schema — happy path
# ---------------------------------------------------------------------------


class TestExpectSchemaPass:
    def test_valid_schema(self, sample_df, sample_schema):
        result = expect_schema(sample_df, sample_schema)
        assert result is sample_df

    def test_round_trip(self, sample_df):
        schema = infer_schema(sample_df)
        result = expect_schema(sample_df, schema)
        assert result is sample_df

    def test_canonical_group_int(self, sample_df):
        expect_schema(sample_df, {"columns": {"ID": {"dtype": "int"}}})

    def test_canonical_group_str(self, sample_df):
        expect_schema(sample_df, {"columns": {"Name": {"dtype": "str"}}})

    def test_canonical_group_float(self, sample_df):
        expect_schema(sample_df, {"columns": {"Score": {"dtype": "float"}}})

    def test_any_dtype_wildcard(self, sample_df):
        schema = {"columns": {"ID": {"dtype": "any"}, "Name": {"dtype": "any"}}}
        expect_schema(sample_df, schema)

    def test_nullable_true_allows_nulls(self):
        df = pd.DataFrame({"A": [1, None, 3]})
        schema = {"columns": {"A": {"dtype": "any", "nullable": True}}}
        expect_schema(df, schema)

    def test_extra_columns_allowed(self, sample_df):
        schema = {"columns": {"ID": {"dtype": "int64"}}}
        expect_schema(sample_df, schema)

    def test_empty_schema_skips(self, sample_df):
        result = expect_schema(sample_df, {"columns": {}})
        assert result is sample_df


# ---------------------------------------------------------------------------
# expect_schema — violations
# ---------------------------------------------------------------------------


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

    def test_multiple_violations_collected(self):
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
        assert len(exc_info.value.violations) == 3  # 2 bad dtypes + 1 missing

    def test_non_strict_logs_warns(self, sample_df, caplog):
        schema = {"columns": {"NonExistent": {"dtype": "int64"}}}
        with caplog.at_level(logging.WARNING, logger="etlpipe_governance.contracts"):
            result = expect_schema(sample_df, schema, strict=False)
        assert result is sample_df
        assert "Schema violation" in caplog.text

    def test_type_error_non_dataframe(self):
        with pytest.raises(TypeError, match="Expected a pandas DataFrame"):
            expect_schema([1, 2, 3], {"columns": {}})


# ---------------------------------------------------------------------------
# _dtype_matches
# ---------------------------------------------------------------------------


class TestDtypeMatches:
    def test_exact_match(self):
        assert _dtype_matches("int64", "int64") is True

    def test_canonical_int(self):
        assert _dtype_matches("int64", "int") is True
        assert _dtype_matches("int32", "int") is True

    def test_canonical_float(self):
        assert _dtype_matches("float64", "float") is True

    def test_canonical_str(self):
        assert _dtype_matches("object", "str") is True
        assert _dtype_matches("string", "str") is True

    def test_any_wildcard(self):
        assert _dtype_matches("int64", "any") is True
        assert _dtype_matches("object", "any") is True

    def test_mismatch(self):
        assert _dtype_matches("int64", "float64") is False
        assert _dtype_matches("object", "int") is False


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


class TestProfile:
    def test_returns_dataframe(self, sample_df):
        result = profile(sample_df)
        assert isinstance(result, pd.DataFrame)

    def test_one_row_per_column(self, sample_df):
        result = profile(sample_df)
        assert len(result) == len(sample_df.columns)

    def test_column_names_present(self, sample_df):
        result = profile(sample_df)
        assert set(result["Column"]) == set(sample_df.columns)

    def test_required_output_columns(self, sample_df):
        result = profile(sample_df)
        required = {
            "Column",
            "Dtype",
            "Row_Count",
            "Null_Count",
            "Null_Rate_Pct",
            "Unique_Count",
            "Cardinality_Pct",
            "Min",
            "Max",
            "Mean",
            "Std",
            "Top_Values",
        }
        assert required.issubset(set(result.columns))

    def test_row_count_correct(self, sample_df):
        result = profile(sample_df)
        assert (result["Row_Count"] == len(sample_df)).all()

    def test_null_count_correct(self):
        df = pd.DataFrame({"A": [1, None, 3, None, 5]})
        result = profile(df)
        assert result[result["Column"] == "A"]["Null_Count"].iloc[0] == 2

    def test_null_rate_pct_correct(self):
        df = pd.DataFrame({"A": [1, None, None, None, 5]})
        result = profile(df)
        assert result[result["Column"] == "A"]["Null_Rate_Pct"].iloc[0] == 60.0

    def test_numeric_stats_computed(self, sample_df):
        result = profile(sample_df)
        score_row = result[result["Column"] == "Score"].iloc[0]
        assert score_row["Min"] == pytest.approx(72.5, abs=0.001)
        assert score_row["Max"] == pytest.approx(95.5, abs=0.001)
        assert score_row["Mean"] is not None
        assert score_row["Std"] is not None

    def test_non_numeric_stats_are_none(self, sample_df):
        result = profile(sample_df)
        name_row = result[result["Column"] == "Name"].iloc[0]
        assert name_row["Min"] is None or pd.isna(name_row["Min"])
        assert name_row["Max"] is None or pd.isna(name_row["Max"])

    def test_unique_count_correct(self, sample_df):
        result = profile(sample_df)
        id_row = result[result["Column"] == "ID"].iloc[0]
        assert id_row["Unique_Count"] == 3

    def test_top_values_populated(self, sample_df):
        result = profile(sample_df)
        name_row = result[result["Column"] == "Name"].iloc[0]
        assert len(name_row["Top_Values"]) > 0

    def test_top_n_zero_skips_top_values(self, sample_df):
        result = profile(sample_df, top_n=0)
        assert (result["Top_Values"] == "").all()

    def test_cardinality_100pct_for_all_unique(self, sample_df):
        result = profile(sample_df)
        id_row = result[result["Column"] == "ID"].iloc[0]
        assert id_row["Cardinality_Pct"] == pytest.approx(100.0, abs=0.01)

    def test_sample_size_reduces_rows(self):
        df = pd.DataFrame({"A": range(1000)})
        # Profiling a sample should still produce one row per column
        result = profile(df, sample_size=50)
        assert len(result) == 1
        assert result["Row_Count"].iloc[0] == 50

    def test_non_dataframe_raises(self):
        with pytest.raises(TypeError, match="Expected a pandas DataFrame"):
            profile([1, 2, 3])

    def test_empty_df_no_error(self):
        df = pd.DataFrame({"A": pd.Series([], dtype="int64")})
        result = profile(df)
        assert len(result) == 1
        assert result["Null_Count"].iloc[0] == 0


# ---------------------------------------------------------------------------
# ContractSuite
# ---------------------------------------------------------------------------


class TestContractSuite:
    @pytest.fixture
    def suite(self) -> ContractSuite:
        return ContractSuite("Test Suite")

    @pytest.fixture
    def good_schema(self) -> dict:
        return {"columns": {"ID": {"dtype": "int64", "nullable": False}}}

    @pytest.fixture
    def good_df(self) -> pd.DataFrame:
        return pd.DataFrame({"ID": [1, 2, 3]})

    def test_add_contract_returns_self(self, suite, good_schema):
        result = suite.add_contract("c1", good_schema)
        assert result is suite

    def test_chaining_add_contract(self, suite, good_schema):
        suite.add_contract("c1", good_schema).add_contract("c2", good_schema)
        assert len(suite) == 2

    def test_len_reflects_contract_count(self, suite, good_schema):
        assert len(suite) == 0
        suite.add_contract("c1", good_schema)
        assert len(suite) == 1

    def test_repr_contains_name(self, suite):
        assert "Test Suite" in repr(suite)

    def test_passing_contract_status_is_pass(self, suite, good_schema, good_df):
        suite.add_contract("check", good_schema)
        results = suite.run({"check": good_df})
        assert results[results["Contract"] == "check"]["Status"].iloc[0] == "PASS"

    def test_failing_contract_status_is_fail(self, suite, good_df):
        bad_schema = {"columns": {"ID": {"dtype": "str"}}}
        suite.add_contract("check", bad_schema)
        results = suite.run({"check": good_df})
        assert results[results["Contract"] == "check"]["Status"].iloc[0] == "FAIL"

    def test_missing_dataframe_status_is_skipped(self, suite, good_schema):
        suite.add_contract("check", good_schema)
        results = suite.run({})
        assert results[results["Contract"] == "check"]["Status"].iloc[0] == "SKIPPED"

    def test_violation_count_correct(self, suite, good_df):
        bad_schema = {
            "columns": {
                "ID": {"dtype": "str"},
                "Missing": {"dtype": "int"},
            }
        }
        suite.add_contract("check", bad_schema)
        results = suite.run({"check": good_df})
        count = results[results["Contract"] == "check"]["Violation_Count"].iloc[0]
        assert count == 2  # wrong dtype + missing column

    def test_violations_text_populated(self, suite, good_df):
        bad_schema = {"columns": {"ID": {"dtype": "str"}}}
        suite.add_contract("check", bad_schema)
        results = suite.run({"check": good_df})
        violations_text = results[results["Contract"] == "check"]["Violations"].iloc[0]
        assert len(violations_text) > 0

    def test_pass_violations_text_empty(self, suite, good_schema, good_df):
        suite.add_contract("check", good_schema)
        results = suite.run({"check": good_df})
        violations_text = results[results["Contract"] == "check"]["Violations"].iloc[0]
        assert violations_text == ""

    def test_result_has_suite_name(self, suite, good_schema, good_df):
        suite.add_contract("check", good_schema)
        results = suite.run({"check": good_df})
        assert (results["Suite"] == "Test Suite").all()

    def test_multiple_contracts_run_independently(self, suite, good_df):
        good_schema = {"columns": {"ID": {"dtype": "int64"}}}
        bad_schema = {"columns": {"ID": {"dtype": "str"}}}
        suite.add_contract("good", good_schema)
        suite.add_contract("bad", bad_schema)
        results = suite.run({"good": good_df, "bad": good_df})
        assert results[results["Contract"] == "good"]["Status"].iloc[0] == "PASS"
        assert results[results["Contract"] == "bad"]["Status"].iloc[0] == "FAIL"

    def test_raise_on_failure(self, suite, good_df):
        bad_schema = {"columns": {"ID": {"dtype": "str"}}}
        suite.add_contract("check", bad_schema)
        with pytest.raises(SchemaViolationError) as exc_info:
            suite.run({"check": good_df}, raise_on_failure=True)
        assert "[check]" in str(exc_info.value)

    def test_no_raise_when_all_pass(self, suite, good_schema, good_df):
        suite.add_contract("check", good_schema)
        # Should not raise
        results = suite.run({"check": good_df}, raise_on_failure=True)
        assert len(results) == 1

    def test_non_strict_contract_status_is_warn(self, suite, good_df):
        bad_schema = {"columns": {"ID": {"dtype": "str"}}}
        suite.add_contract("check", bad_schema, strict=False)
        results = suite.run({"check": good_df})
        assert results[results["Contract"] == "check"]["Status"].iloc[0] == "WARN"

    def test_description_appears_in_results(self, suite, good_schema, good_df):
        suite.add_contract("check", good_schema, description="Validates the ID column")
        results = suite.run({"check": good_df})
        assert results[results["Contract"] == "check"]["Description"].iloc[0] == "Validates the ID column"

    def test_empty_suite_returns_empty_df(self, suite):
        results = suite.run({})
        assert isinstance(results, pd.DataFrame)
        assert len(results) == 0
