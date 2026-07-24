"""Declarative pipeline engine for etlpipe.

Allows executing a series of etlpipe tools defined in a YAML configuration file.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

logger = logging.getLogger("etlpipe.pipeline")


class Pipeline:
    """Engine to execute a etlpipe pipeline from a YAML configuration.

    Attributes:
        name: Human-readable pipeline name from YAML config.
        metrics: List of per-step metric dicts populated after ``execute()``.
            Each dict contains: ``step_id``, ``tool``, ``duration_s``,
            ``output_rows``, ``output_type``, and ``status``.
    """

    def __init__(
        self,
        config_path: str | Path,
        *,
        on_step_start: Callable[[str, str], None] | None = None,
        on_step_complete: Callable[[str, str, dict], None] | None = None,
        on_step_error: Callable[[str, str, Exception], None] | None = None,
        on_pipeline_complete: Callable[[str, list[dict]], None] | None = None,
    ):
        """Initialize the pipeline with a path to a YAML configuration file.

        Args:
            config_path: Path to the YAML pipeline configuration file.
            on_step_start: Optional callback ``(step_id, tool_name) -> None``
                invoked before each step executes.
            on_step_complete: Optional callback ``(step_id, tool_name, metrics) -> None``
                invoked after each step succeeds.
            on_step_error: Optional callback ``(step_id, tool_name, exception) -> None``
                invoked when a step raises an exception.
            on_pipeline_complete: Optional callback ``(pipeline_name, all_metrics) -> None``
                invoked after the entire pipeline finishes successfully.
        """
        self.config_path = Path(config_path)
        with self.config_path.open("r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.name = self.config.get("name", "Unnamed Pipeline")
        self.backend_name = self.config.get("backend", None)
        self.steps = self.config.get("steps", [])
        self.state: dict[str, Any] = {}
        self.metrics: list[dict[str, Any]] = []

        # Event hooks for alerting integration
        self._on_step_start = on_step_start
        self._on_step_complete = on_step_complete
        self._on_step_error = on_step_error
        self._on_pipeline_complete = on_pipeline_complete

    def _resolve_input(self, ref: str) -> Any:
        """Resolve an input reference string to a DataFrame from state.

        Supports resolving tuple items (e.g., 'filter_step.0').
        """
        if not isinstance(ref, str):
            return ref

        parts = ref.split(".")
        step_id = parts[0]
        if step_id not in self.state:
            raise ValueError(f"Input reference '{step_id}' not found in pipeline state.")

        value = self.state[step_id]

        # Handle tuple indexing (e.g., filter_high_value.0)
        if len(parts) > 1:
            try:
                idx = int(parts[1])
                return value[idx]
            except (ValueError, TypeError, IndexError) as e:
                raise ValueError(
                    f"Could not resolve index '{parts[1]}' on output of step '{step_id}'. "
                    f"Output is of type {type(value)}."
                ) from e

        return value

    def _get_tool_callable(self, tool_path: str) -> Any:
        """Dynamically load a etlpipe method (e.g., 'Preparation.filter')."""
        try:
            class_name, method_name = tool_path.split(".")
        except ValueError as e:
            raise ValueError(f"Invalid tool format '{tool_path}'. Expected 'Class.method'") from e

        # All etlpipe tools are exported at the root module level
        try:
            module = importlib.import_module("etlpipe")
            tool_class = getattr(module, class_name)
            tool_func = getattr(tool_class, method_name)
            return tool_func
        except AttributeError as e:
            raise ValueError(f"Could not find tool '{tool_path}' in etlpipe.") from e

    @staticmethod
    def _measure_output(result: Any) -> dict[str, Any]:
        """Extract row count and type info from a step result."""
        info: dict[str, Any] = {"output_type": type(result).__name__}

        if isinstance(result, pd.DataFrame):
            info["output_rows"] = len(result)
            info["output_cols"] = len(result.columns)
        elif isinstance(result, tuple):
            info["output_type"] = f"tuple[{len(result)}]"
            # Report rows for each element if they are DataFrames
            for i, item in enumerate(result):
                if isinstance(item, pd.DataFrame):
                    info[f"output_{i}_rows"] = len(item)
                else:
                    try:
                        from pyspark.sql import DataFrame as SparkDF

                        if isinstance(item, SparkDF):
                            info[f"output_{i}_type"] = "SparkDataFrame"
                    except ImportError:
                        pass
        else:
            try:
                from pyspark.sql import DataFrame as SparkDF

                if isinstance(result, SparkDF):
                    info["output_type"] = "SparkDataFrame"
            except ImportError:
                pass

        return info

    def _validate_step_schema(self, step: dict, step_id: str, result: Any) -> None:
        """Validate step output against an optional schema contract."""
        output_schema = step.get("output_schema")
        if not output_schema:
            return

        from etlpipe._contracts import expect_schema

        # For tuple results, validate the first DataFrame by default
        df_to_validate = result
        if isinstance(result, tuple):
            schema_index = output_schema.get("_tuple_index", 0)
            df_to_validate = result[schema_index]

        expect_schema(df_to_validate, output_schema)
        logger.debug("Schema validation passed for step '%s'", step_id)

    def execute(self) -> None:
        """Run all steps in the pipeline sequentially.

        Populates ``self.metrics`` with per-step execution data. Invokes
        registered event hooks at each lifecycle point.
        """
        pipeline_start = time.perf_counter()
        self.metrics = []

        logger.info("Starting pipeline: '%s' (%d steps)", self.name, len(self.steps))

        if self.backend_name:
            from etlpipe._config import set_backend

            set_backend(self.backend_name, **self.config.get("spark_config", {}))
            logger.info("Backend set to '%s'", self.backend_name)

        for step in self.steps:
            step_id = step.get("id")
            tool_name = step.get("tool")
            inputs = step.get("inputs", {})
            args = step.get("args", {})

            if not step_id or not tool_name:
                raise ValueError("Each step must have an 'id' and a 'tool'.")

            # Fire on_step_start hook
            if self._on_step_start:
                self._on_step_start(step_id, tool_name)

            logger.info("Executing step: '%s' (%s)", step_id, tool_name)
            step_start = time.perf_counter()

            try:
                # 1. Resolve inputs
                resolved_inputs = {}
                for param_name, ref in inputs.items():
                    resolved_inputs[param_name] = self._resolve_input(ref)

                # 2. Merge inputs with other kwargs
                kwargs = {**resolved_inputs, **args}

                # 3. Get callable
                tool_func = self._get_tool_callable(tool_name)

                # 4. Execute
                result = tool_func(**kwargs)

                # 5. Store in state
                self.state[step_id] = result

                # 6. Validate schema contract if provided
                self._validate_step_schema(step, step_id, result)

            except Exception as e:
                duration = time.perf_counter() - step_start
                step_metric = {
                    "step_id": step_id,
                    "tool": tool_name,
                    "duration_s": round(duration, 4),
                    "status": "error",
                    "error": str(e),
                }
                self.metrics.append(step_metric)
                logger.error(
                    "Step '%s' failed after %.4fs: %s",
                    step_id,
                    duration,
                    e,
                )
                # Fire on_step_error hook
                if self._on_step_error:
                    self._on_step_error(step_id, tool_name, e)
                raise

            # 7. Record metrics
            duration = time.perf_counter() - step_start
            step_metric = {
                "step_id": step_id,
                "tool": tool_name,
                "duration_s": round(duration, 4),
                "status": "success",
                **self._measure_output(result),
            }
            self.metrics.append(step_metric)

            logger.info(
                "Step '%s' completed: %s",
                step_id,
                json.dumps(step_metric, default=str),
            )

            # Fire on_step_complete hook
            if self._on_step_complete:
                self._on_step_complete(step_id, tool_name, step_metric)

        # Pipeline summary
        total_duration = time.perf_counter() - pipeline_start
        summary = {
            "pipeline": self.name,
            "total_steps": len(self.metrics),
            "total_duration_s": round(total_duration, 4),
            "status": "success",
        }
        logger.info("Pipeline completed: %s", json.dumps(summary, default=str))

        # Fire on_pipeline_complete hook
        if self._on_pipeline_complete:
            self._on_pipeline_complete(self.name, self.metrics)

    @classmethod
    def run(
        cls,
        config_path: str | Path,
        *,
        on_step_start: Callable[[str, str], None] | None = None,
        on_step_complete: Callable[[str, str, dict], None] | None = None,
        on_step_error: Callable[[str, str, Exception], None] | None = None,
        on_pipeline_complete: Callable[[str, list[dict]], None] | None = None,
    ) -> Pipeline:
        """Convenience method to load and execute a pipeline.

        Returns:
            The ``Pipeline`` instance (with populated ``metrics``).
        """
        pipeline = cls(
            config_path,
            on_step_start=on_step_start,
            on_step_complete=on_step_complete,
            on_step_error=on_step_error,
            on_pipeline_complete=on_pipeline_complete,
        )
        pipeline.execute()
        return pipeline


def cli_main() -> None:
    """CLI entry point for running pipelines."""
    parser = argparse.ArgumentParser(description="Run a etlpipe YAML pipeline.")
    parser.add_argument("command", choices=["run"], help="Command to execute (e.g., 'run').")
    parser.add_argument("config_path", type=str, help="Path to the YAML pipeline configuration file.")

    args = parser.parse_args()

    # Configure root logger for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if args.command == "run":
        try:
            Pipeline.run(args.config_path)
        except Exception as e:
            logger.error("Pipeline failed: %s", e)
            sys.exit(1)


if __name__ == "__main__":
    cli_main()
