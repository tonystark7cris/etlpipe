"""Tests for AuditTrail persistence."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from etlpipe_governance import AuditTrail, ContractSuite


@pytest.fixture
def trail(tmp_path):
    return AuditTrail(path=tmp_path / "audit_logs")


@pytest.fixture
def sample_results():
    return pd.DataFrame(
        {
            "Suite": ["test_suite", "test_suite"],
            "Contract": ["schema_a", "schema_b"],
            "Description": ["Check A", "Check B"],
            "Status": ["PASS", "FAIL"],
            "Violation_Count": [0, 2],
            "Violations": ["", "Missing column: 'x'\nMissing column: 'y'"],
        }
    )


class TestAuditLog:
    def test_log_creates_file(self, trail, sample_results):
        trail.log(sample_results, run_id="test_run_001")
        assert trail.log_path.exists()

    def test_log_appends(self, trail, sample_results):
        trail.log(sample_results, run_id="run_1")
        trail.log(sample_results, run_id="run_2")
        with open(trail.log_path) as f:
            lines = f.readlines()
        assert len(lines) == 4  # 2 records * 2 runs

    def test_log_jsonl_format(self, trail, sample_results):
        trail.log(sample_results, run_id="test_run")
        with open(trail.log_path) as f:
            for line in f:
                record = json.loads(line)
                assert "run_id" in record
                assert "run_timestamp" in record
                assert "Status" in record

    def test_log_with_metadata(self, trail, sample_results):
        trail.log(
            sample_results,
            run_id="test_run",
            metadata={"env": "production", "pipeline": "daily_etl"},
        )
        with open(trail.log_path) as f:
            record = json.loads(f.readline())
        assert record["env"] == "production"
        assert record["pipeline"] == "daily_etl"


class TestAuditLoad:
    def test_load_all(self, trail, sample_results):
        trail.log(sample_results, run_id="run_1")
        history = trail.load()
        assert len(history) == 2
        assert "run_id" in history.columns

    def test_load_by_run_id(self, trail, sample_results):
        trail.log(sample_results, run_id="run_1")
        trail.log(sample_results, run_id="run_2")
        history = trail.load(run_id="run_1")
        assert len(history) == 2
        assert all(history["run_id"] == "run_1")

    def test_load_empty(self, trail):
        history = trail.load()
        assert len(history) == 0
        assert isinstance(history, pd.DataFrame)

    def test_load_by_days(self, trail, sample_results):
        trail.log(sample_results, run_id="recent")
        history = trail.load(days=1)
        assert len(history) == 2  # Just logged, so within 1 day


class TestAuditClear:
    def test_clear(self, trail, sample_results):
        trail.log(sample_results, run_id="test")
        assert trail.log_path.exists()
        trail.clear()
        assert not trail.log_path.exists()


class TestSuiteIntegration:
    def test_suite_run_with_audit_trail(self, trail):
        suite = ContractSuite("Integration Test")
        suite.add_contract(
            "data",
            {"columns": {"id": {"dtype": "int64"}}},
            description="ID check",
        )
        df = pd.DataFrame({"id": [1, 2, 3]})
        results = suite.run({"data": df}, audit_trail=trail, run_id="ci_build_42")

        assert results.iloc[0]["Status"] == "PASS"

        history = trail.load()
        assert len(history) == 1
        assert history.iloc[0]["run_id"] == "ci_build_42"
        assert history.iloc[0]["suite_name"] == "Integration Test"


class TestAuditRepr:
    def test_repr(self, trail):
        r = repr(trail)
        assert "AuditTrail" in r
