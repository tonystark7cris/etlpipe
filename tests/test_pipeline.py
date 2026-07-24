"""Tests for etlpipe.pipeline — Declarative YAML pipelines."""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from etlpipe import Pipeline


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Fixture creating a temporary CSV file."""
    csv_path = tmp_path / "sales.csv"
    df = pd.DataFrame(
        {
            "Region": ["East", "West", "East", "West"],
            "Revenue": [500, 1500, 2000, 800],
        }
    )
    df.to_csv(csv_path, index=False)
    return csv_path


def test_linear_pipeline(tmp_path: Path, sample_csv: Path) -> None:
    """Test a basic pipeline reading, transforming, and saving."""
    out_csv = tmp_path / "out.csv"

    pipeline_config = {
        "name": "Test Pipeline",
        "steps": [
            {
                "id": "load",
                "tool": "InOut.input_data",
                "args": {"path": str(sample_csv)},
            },
            {
                "id": "add_tax",
                "tool": "Preparation.formula",
                "inputs": {"df": "load"},
                "args": {"column": "Tax", "expression": "Revenue * 0.1"},
            },
            {
                "id": "save",
                "tool": "InOut.output_data",
                "inputs": {"df": "add_tax"},
                "args": {"path": str(out_csv)},
            },
        ],
    }

    yaml_path = tmp_path / "pipeline.yaml"
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.dump(pipeline_config, f)

    Pipeline.run(yaml_path)

    assert out_csv.exists()
    result = pd.read_csv(out_csv)
    assert "Tax" in result.columns
    assert result["Tax"].iloc[0] == 50.0


def test_multi_output_resolution(tmp_path: Path, sample_csv: Path) -> None:
    """Test resolving outputs from tools that return tuples (e.g., Filter)."""
    pipeline_config = {
        "steps": [
            {
                "id": "load",
                "tool": "InOut.input_data",
                "args": {"path": str(sample_csv)},
            },
            {
                "id": "filter_high",
                "tool": "Preparation.filter",
                "inputs": {"df": "load"},
                "args": {"condition": "Revenue > 1000"},
            },
            {
                "id": "count_high",
                "tool": "Transform.count_records",
                "inputs": {"df": "filter_high.0"},  # T output
            },
            {
                "id": "count_low",
                "tool": "Transform.count_records",
                "inputs": {"df": "filter_high.1"},  # F output
            },
        ],
    }

    yaml_path = tmp_path / "pipeline.yaml"
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.dump(pipeline_config, f)

    pipeline = Pipeline(yaml_path)
    pipeline.execute()

    # Revenue > 1000 are index 1 (1500) and 2 (2000) -> 2 rows
    count_high_df = pipeline.state["count_high"]
    assert count_high_df["Count"].iloc[0] == 2

    # Revenue <= 1000 are index 0 (500) and 3 (800) -> 2 rows
    count_low_df = pipeline.state["count_low"]
    assert count_low_df["Count"].iloc[0] == 2


def test_missing_input_raises(tmp_path: Path) -> None:
    """Test error when referencing a step that hasn't run."""
    pipeline_config = {
        "steps": [
            {
                "id": "step2",
                "tool": "Transform.count_records",
                "inputs": {"df": "step1"},
            },
        ],
    }

    yaml_path = tmp_path / "pipeline.yaml"
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.dump(pipeline_config, f)

    pipeline = Pipeline(yaml_path)
    with pytest.raises(ValueError, match="not found in pipeline state"):
        pipeline.execute()


def test_invalid_tool_raises(tmp_path: Path) -> None:
    """Test error for invalid tool name."""
    pipeline_config = {
        "steps": [
            {
                "id": "step1",
                "tool": "InvalidClass.method",
            },
        ],
    }

    yaml_path = tmp_path / "pipeline.yaml"
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.dump(pipeline_config, f)

    pipeline = Pipeline(yaml_path)
    with pytest.raises(ValueError, match="Could not find tool"):
        pipeline.execute()
