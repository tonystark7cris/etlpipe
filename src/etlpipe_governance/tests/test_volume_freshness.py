"""Tests for volume (expect_row_count) and freshness (expect_freshness) checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from etlpipe_governance import (
    ContractSuite,
    FreshnessError,
    SchemaViolationError,
    expect_freshness,
    expect_row_count,
)


class TestExpectRowCount:
    def test_pass_min(self):
        df = pd.DataFrame({"a": range(100)})
        result = expect_row_count(df, min_rows=50)
        assert len(result) == 100

    def test_pass_max(self):
        df = pd.DataFrame({"a": range(100)})
        result = expect_row_count(df, max_rows=200)
        assert len(result) == 100

    def test_pass_both(self):
        df = pd.DataFrame({"a": range(100)})
        result = expect_row_count(df, min_rows=50, max_rows=200)
        assert len(result) == 100

    def test_fail_min(self):
        df = pd.DataFrame({"a": range(10)})
        with pytest.raises(SchemaViolationError, match="below minimum"):
            expect_row_count(df, min_rows=100)

    def test_fail_max(self):
        df = pd.DataFrame({"a": range(1000)})
        with pytest.raises(SchemaViolationError, match="exceeds maximum"):
            expect_row_count(df, max_rows=500)

    def test_fail_empty(self):
        df = pd.DataFrame({"a": []})
        with pytest.raises(SchemaViolationError, match="below minimum"):
            expect_row_count(df, min_rows=1)

    def test_non_strict(self):
        df = pd.DataFrame({"a": range(10)})
        result = expect_row_count(df, min_rows=100, strict=False)
        assert len(result) == 10  # Returns without raising

    def test_type_error(self):
        with pytest.raises(TypeError):
            expect_row_count("not a dataframe", min_rows=1)


class TestExpectFreshness:
    def test_pass_recent(self):
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({"ts": [now - timedelta(hours=1), now - timedelta(minutes=5)]})
        result = expect_freshness(df, column="ts", max_age=timedelta(hours=6), reference_time=now)
        assert len(result) == 2

    def test_fail_stale(self):
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({"ts": [now - timedelta(days=10), now - timedelta(days=8)]})
        with pytest.raises(FreshnessError, match="Freshness check failed"):
            expect_freshness(df, column="ts", max_age=timedelta(hours=6), reference_time=now)

    def test_freshness_error_attributes(self):
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({"ts": [now - timedelta(days=5)]})
        with pytest.raises(FreshnessError) as exc_info:
            expect_freshness(df, column="ts", max_age=timedelta(hours=1), reference_time=now)
        assert exc_info.value.column == "ts"
        assert exc_info.value.max_age == timedelta(hours=1)

    def test_non_strict(self):
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({"ts": [now - timedelta(days=10)]})
        result = expect_freshness(df, column="ts", max_age=timedelta(hours=1), reference_time=now, strict=False)
        assert len(result) == 1

    def test_missing_column(self):
        df = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(KeyError, match="not found"):
            expect_freshness(df, column="ts", max_age=timedelta(hours=1))

    def test_naive_timestamps(self):
        """Naive (tz-unaware) timestamps should work with UTC reference."""
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({"ts": [datetime(2026, 8, 1, 8, 0, 0)]})
        result = expect_freshness(df, column="ts", max_age=timedelta(days=365), reference_time=now)
        assert len(result) == 1

    def test_type_error(self):
        with pytest.raises(TypeError):
            expect_freshness("not a df", column="ts", max_age=timedelta(hours=1))


class TestSuiteVolumeCheck:
    def test_pass(self):
        suite = ContractSuite("test")
        suite.add_volume_check("data", min_rows=1, max_rows=100)
        df = pd.DataFrame({"a": range(50)})
        results = suite.run({"data": df})
        assert results.iloc[0]["Status"] == "PASS"

    def test_fail(self):
        suite = ContractSuite("test")
        suite.add_volume_check("data", min_rows=100)
        df = pd.DataFrame({"a": range(10)})
        results = suite.run({"data": df})
        assert results.iloc[0]["Status"] == "FAIL"

    def test_skipped(self):
        suite = ContractSuite("test")
        suite.add_volume_check("missing", min_rows=1)
        results = suite.run({})
        assert results.iloc[0]["Status"] == "SKIPPED"


class TestSuiteFreshnessCheck:
    def test_pass(self):
        now = datetime.now(timezone.utc)
        suite = ContractSuite("test")
        suite.add_freshness_check("events", column="ts", max_age=timedelta(hours=24))
        df = pd.DataFrame({"ts": [now - timedelta(hours=1)]})
        results = suite.run({"events": df})
        assert results.iloc[0]["Status"] == "PASS"

    def test_fail(self):
        now = datetime.now(timezone.utc)
        suite = ContractSuite("test")
        suite.add_freshness_check("events", column="ts", max_age=timedelta(hours=1))
        df = pd.DataFrame({"ts": [now - timedelta(days=5)]})
        results = suite.run({"events": df})
        assert results.iloc[0]["Status"] == "FAIL"

    def test_skipped(self):
        suite = ContractSuite("test")
        suite.add_freshness_check("missing", column="ts", max_age=timedelta(hours=1))
        results = suite.run({})
        assert results.iloc[0]["Status"] == "SKIPPED"
