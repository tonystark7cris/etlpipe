"""Tests for HTML and JSON report export."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from etlpipe_governance import export_report


@pytest.fixture
def sample_results():
    return pd.DataFrame(
        {
            "Suite": ["Audit", "Audit", "Audit"],
            "Contract": ["schema_a", "schema_b", "schema_c"],
            "Description": ["Check A", "Check B", "Check C"],
            "Status": ["PASS", "FAIL", "SKIPPED"],
            "Violation_Count": [0, 2, 0],
            "Violations": ["", "Missing column: 'x'\nBad dtype", ""],
        }
    )


class TestHTMLExport:
    def test_creates_file(self, sample_results, tmp_path):
        path = tmp_path / "report.html"
        result = export_report(sample_results, path, format="html")
        assert result.exists()
        assert result.stat().st_size > 0

    def test_contains_status_badges(self, sample_results, tmp_path):
        path = tmp_path / "report.html"
        export_report(sample_results, path, format="html")
        html = path.read_text(encoding="utf-8")
        assert "badge-pass" in html
        assert "badge-fail" in html
        assert "badge-skip" in html

    def test_contains_contract_names(self, sample_results, tmp_path):
        path = tmp_path / "report.html"
        export_report(sample_results, path, format="html")
        html = path.read_text(encoding="utf-8")
        assert "schema_a" in html
        assert "schema_b" in html

    def test_contains_violations(self, sample_results, tmp_path):
        path = tmp_path / "report.html"
        export_report(sample_results, path, format="html")
        html = path.read_text(encoding="utf-8")
        assert "Missing column" in html

    def test_custom_title(self, sample_results, tmp_path):
        path = tmp_path / "report.html"
        export_report(sample_results, path, format="html", title="My Custom Audit")
        html = path.read_text(encoding="utf-8")
        assert "My Custom Audit" in html

    def test_self_contained(self, sample_results, tmp_path):
        """HTML should not reference external CDNs."""
        path = tmp_path / "report.html"
        export_report(sample_results, path, format="html")
        html = path.read_text(encoding="utf-8")
        assert "http" not in html  # No external references

    def test_creates_parent_dirs(self, sample_results, tmp_path):
        path = tmp_path / "deep" / "nested" / "report.html"
        export_report(sample_results, path, format="html")
        assert path.exists()


class TestJSONExport:
    def test_creates_file(self, sample_results, tmp_path):
        path = tmp_path / "report.json"
        result = export_report(sample_results, path, format="json")
        assert result.exists()

    def test_valid_json(self, sample_results, tmp_path):
        path = tmp_path / "report.json"
        export_report(sample_results, path, format="json")
        with open(path) as f:
            data = json.load(f)
        assert "title" in data
        assert "results" in data
        assert "summary" in data
        assert "run_timestamp" in data

    def test_result_count(self, sample_results, tmp_path):
        path = tmp_path / "report.json"
        export_report(sample_results, path, format="json")
        with open(path) as f:
            data = json.load(f)
        assert data["total_checks"] == 3
        assert len(data["results"]) == 3

    def test_summary_counts(self, sample_results, tmp_path):
        path = tmp_path / "report.json"
        export_report(sample_results, path, format="json")
        with open(path) as f:
            data = json.load(f)
        assert data["summary"]["PASS"] == 1
        assert data["summary"]["FAIL"] == 1

    def test_custom_title(self, sample_results, tmp_path):
        path = tmp_path / "report.json"
        export_report(sample_results, path, format="json", title="Custom Title")
        with open(path) as f:
            data = json.load(f)
        assert data["title"] == "Custom Title"


class TestUnsupportedFormat:
    def test_raises(self, sample_results, tmp_path):
        with pytest.raises(ValueError, match="Unsupported format"):
            export_report(sample_results, tmp_path / "report.csv", format="csv")
