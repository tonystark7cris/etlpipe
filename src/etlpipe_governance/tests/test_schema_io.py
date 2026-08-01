"""Tests for YAML/JSON schema I/O."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from etlpipe_governance import expect_schema, infer_schema, load_schema, save_schema
from etlpipe_governance.schema_io import schema_to_yaml


@pytest.fixture
def sample_schema():
    return {
        "columns": {
            "id": {"dtype": "int64", "nullable": False},
            "name": {"dtype": "object", "nullable": True},
            "score": {"dtype": "float64", "min_value": 0.0, "max_value": 1.0},
        }
    }


class TestSaveAndLoadYAML:
    def test_round_trip(self, sample_schema, tmp_path):
        path = tmp_path / "schema.yaml"
        save_schema(sample_schema, path)
        loaded = load_schema(path)
        assert loaded["columns"]["id"]["dtype"] == "int64"
        assert loaded["columns"]["score"]["max_value"] == 1.0

    def test_yml_extension(self, sample_schema, tmp_path):
        path = tmp_path / "schema.yml"
        save_schema(sample_schema, path)
        loaded = load_schema(path)
        assert "id" in loaded["columns"]


class TestSaveAndLoadJSON:
    def test_round_trip(self, sample_schema, tmp_path):
        path = tmp_path / "schema.json"
        save_schema(sample_schema, path)
        loaded = load_schema(path)
        assert loaded["columns"]["id"]["dtype"] == "int64"
        assert loaded["columns"]["score"]["min_value"] == 0.0

    def test_json_structure(self, sample_schema, tmp_path):
        path = tmp_path / "schema.json"
        save_schema(sample_schema, path)
        with open(path) as f:
            raw = json.load(f)
        assert "columns" in raw


class TestLoadSchema:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_schema("nonexistent.yaml")

    def test_unsupported_format(self, tmp_path):
        path = tmp_path / "schema.txt"
        path.write_text("{}")
        with pytest.raises(ValueError, match="Unsupported"):
            load_schema(path)

    def test_auto_wrap_columns(self, tmp_path):
        """If file doesn't have a top-level 'columns' key, it should be wrapped."""
        path = tmp_path / "flat.json"
        flat_schema = {"id": {"dtype": "int64"}, "name": {"dtype": "object"}}
        with open(path, "w") as f:
            json.dump(flat_schema, f)
        loaded = load_schema(path)
        assert "columns" in loaded
        assert "id" in loaded["columns"]

    def test_creates_parent_dirs(self, sample_schema, tmp_path):
        path = tmp_path / "deeply" / "nested" / "schema.json"
        save_schema(sample_schema, path)
        assert path.exists()


class TestSchemaToYaml:
    def test_returns_string(self, sample_schema):
        result = schema_to_yaml(sample_schema)
        assert isinstance(result, str)
        assert "columns:" in result
        assert "int64" in result


class TestEndToEnd:
    def test_infer_save_load_validate(self, tmp_path):
        """Full round-trip: infer -> save -> load -> validate."""
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        schema = infer_schema(df)
        path = tmp_path / "inferred.yaml"
        save_schema(schema, path)
        loaded = load_schema(path)
        result = expect_schema(df, loaded)
        assert len(result) == 3
