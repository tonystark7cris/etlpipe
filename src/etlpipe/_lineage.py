"""OpenLineage-compatible data lineage collector for etlpipe pipelines.

Tracks the data flow through each pipeline step and produces lineage events
in the OpenLineage standard format (https://openlineage.io).  No OpenLineage
SDK dependency is required — events are emitted as plain Python dicts that
conform to the spec.

Use cases
---------
- **BCBS 239 compliance** — automated data lineage for regulatory reporting.
- **Data catalog integration** — push events to Apache Atlas, Collibra, or Alation.
- **Marquez / OpenLineage backend** — use :meth:`LineageCollector.emit_to_marquez`.
- **Custom integrations** — call :meth:`LineageCollector.to_dict` for the raw graph.

Usage::

    from etlpipe import Pipeline
    from etlpipe._lineage import LineageCollector

    collector = LineageCollector(
        namespace=\"prod.data-engineering\",
        job_prefix=\"bank\",
    )

    Pipeline.run(
        \"daily_reconciliation.yaml\",
        lineage_collector=collector,
    )

    # Get OpenLineage events
    events = collector.to_openlineage_events()

    # Optionally push to Marquez / any OpenLineage HTTP backend
    collector.emit_to_marquez(\"http://marquez.internal:5000\", namespace=\"prod\")

    # Or get the raw lineage graph
    graph = collector.to_dict()
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("etlpipe.lineage")


class LineageCollector:
    """Collects per-step lineage events during pipeline execution.

    Each :meth:`record_step` call captures the step's inputs, outputs,
    schema, row count, and timing — building a full lineage graph that
    can be exported in multiple formats.

    Args:
        namespace: OpenLineage namespace for the pipeline jobs
            (e.g. ``\"prod.data-engineering\"``).
        job_prefix: Optional prefix for job names in the lineage graph.

    Example::

        collector = LineageCollector(namespace=\"prod\", job_prefix=\"bank\")
        collector.record_step(
            step_id=\"filter_active\",
            tool=\"Preparation.filter\",
            inputs=[\"load_customers\"],
            output_schema={\"CustomerID\": \"int64\", \"Status\": \"object\"},
            row_count=5423,
            duration_s=0.045,
        )
        events = collector.to_openlineage_events()
    """

    def __init__(
        self,
        namespace: str = "etlpipe.default",
        job_prefix: str = "",
    ) -> None:
        self.namespace = namespace
        self.job_prefix = job_prefix
        self._steps: list[dict[str, Any]] = []
        self._pipeline_name: str = "unknown"
        self._run_id: str = ""
        self._started_at: str = ""

    def set_pipeline(self, name: str, run_id: str = "") -> None:
        """Register the pipeline name and optional run identifier.

        Args:
            name: Pipeline name (from YAML ``name:`` field).
            run_id: Optional unique run identifier (e.g. Airflow run ID, date string).
        """
        self._pipeline_name = name
        self._run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._started_at = datetime.now(timezone.utc).isoformat()

    def record_step(
        self,
        step_id: str,
        tool: str,
        inputs: list[str],
        *,
        output_schema: dict[str, Any] | None = None,
        row_count: int | None = None,
        duration_s: float | None = None,
        status: str = "COMPLETE",
    ) -> None:
        """Record a completed pipeline step's lineage.

        Args:
            step_id: The step identifier (from YAML ``id:`` field).
            tool: The etlpipe tool name (e.g. ``\"Preparation.filter\"``).
            inputs: List of upstream step IDs that produced this step's input data.
            output_schema: Optional dict mapping column names to dtype strings.
            row_count: Number of output rows produced by this step.
            duration_s: Step execution time in seconds.
            status: Completion status — ``\"COMPLETE\"`` or ``\"FAIL\"``.
        """
        self._steps.append(
            {
                "step_id": step_id,
                "tool": tool,
                "inputs": inputs,
                "output_schema": output_schema or {},
                "row_count": row_count,
                "duration_s": duration_s,
                "status": status,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.debug(
            "Lineage recorded: step='%s' tool='%s' inputs=%s rows=%s",
            step_id,
            tool,
            inputs,
            row_count,
        )

    def _job_name(self, step_id: str) -> str:
        """Build a qualified job name for a step."""
        parts = [p for p in [self.job_prefix, self._pipeline_name, step_id] if p]
        return ".".join(parts)

    def _dataset_name(self, step_id: str) -> str:
        """Build an OpenLineage dataset name for a step's output."""
        return f"{self._pipeline_name}.{step_id}"

    def to_openlineage_events(self) -> list[dict[str, Any]]:
        """Export lineage as OpenLineage-compatible ``RunEvent`` dicts.

        The returned list can be POSTed to any OpenLineage HTTP backend
        (Marquez, Atlan, etc.) without modification.

        Returns:
            A list of OpenLineage ``RunEvent`` dicts (one per recorded step).

        Example::

            events = collector.to_openlineage_events()
            for event in events:
                print(event[\"eventType\"], event[\"job\"][\"name\"])
        """
        events: list[dict[str, Any]] = []

        for step in self._steps:
            step_id = step["step_id"]
            tool = step["tool"]

            # Build input datasets
            input_datasets = []
            for upstream_id in step["inputs"]:
                input_datasets.append(
                    {
                        "namespace": self.namespace,
                        "name": self._dataset_name(upstream_id),
                    }
                )

            # Build output dataset with schema facet
            output_facets: dict[str, Any] = {}
            if step["output_schema"]:
                output_facets["schema"] = {
                    "_producer": "etlpipe",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SchemaDatasetFacet.json",
                    "fields": [{"name": col, "type": dtype} for col, dtype in step["output_schema"].items()],
                }
            if step["row_count"] is not None:
                output_facets["dataQualityMetrics"] = {
                    "_producer": "etlpipe",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsDatasetFacet.json",
                    "rowCount": step["row_count"],
                }

            output_datasets = [
                {
                    "namespace": self.namespace,
                    "name": self._dataset_name(step_id),
                    "facets": output_facets,
                }
            ]

            # Run facets
            run_facets: dict[str, Any] = {
                "etlpipe": {
                    "_producer": "etlpipe",
                    "tool": tool,
                    "pipeline": self._pipeline_name,
                }
            }
            if step["duration_s"] is not None:
                run_facets["processingEngine"] = {
                    "_producer": "etlpipe",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ProcessingEngineRunFacet.json",
                    "processingEngineVersion": "etlpipe",
                    "name": "etlpipe",
                    "openlineageAdapterVersion": "etlpipe-lineage-1.0",
                }

            event_type = "COMPLETE" if step["status"] == "COMPLETE" else "FAIL"

            events.append(
                {
                    "eventType": event_type,
                    "eventTime": step["recorded_at"],
                    "run": {
                        "runId": f"{self._run_id}-{step_id}",
                        "facets": run_facets,
                    },
                    "job": {
                        "namespace": self.namespace,
                        "name": self._job_name(step_id),
                        "facets": {
                            "jobType": {
                                "_producer": "etlpipe",
                                "_schemaURL": "https://openlineage.io/spec/facets/2-0-2/JobTypeJobFacet.json",
                                "processingType": "BATCH",
                                "integration": "etlpipe",
                                "jobType": tool,
                            }
                        },
                    },
                    "inputs": input_datasets,
                    "outputs": output_datasets,
                    "producer": "https://github.com/tonystark7cris/etlpipe",
                    "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
                }
            )

        return events

    def emit_to_marquez(
        self,
        marquez_url: str,
        namespace: str | None = None,
        *,
        timeout: int = 10,
    ) -> int:
        """POST lineage events to a Marquez or OpenLineage HTTP backend.

        Uses ``urllib`` from the standard library — no ``requests`` dependency.

        Args:
            marquez_url: Base URL of the Marquez/OpenLineage server,
                e.g. ``\"http://marquez.internal:5000\"``.
            namespace: Override namespace for this emission.
            timeout: HTTP request timeout in seconds.

        Returns:
            Number of events successfully sent.

        Raises:
            urllib.error.URLError: If the HTTP request fails.

        Example::

            sent = collector.emit_to_marquez(\"http://marquez.internal:5000\")
            print(f\"Sent {sent} lineage events\")
        """
        if namespace:
            self.namespace = namespace

        events = self.to_openlineage_events()
        endpoint = f"{marquez_url.rstrip('/')}/api/v1/lineage"
        sent = 0

        for event in events:
            payload = json.dumps(event, default=str).encode("utf-8")
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
                    if resp.status < 300:
                        sent += 1
                        logger.debug(
                            "Lineage event sent to Marquez: step=%s status=%d",
                            event["job"]["name"],
                            resp.status,
                        )
                    else:
                        logger.warning(
                            "Marquez returned HTTP %d for event: %s",
                            resp.status,
                            event["job"]["name"],
                        )
            except urllib.error.URLError as exc:
                logger.error("Failed to send lineage event to Marquez: %s", exc)

        logger.info("Emitted %d/%d lineage events to %s", sent, len(events), endpoint)
        return sent

    def to_dict(self) -> dict[str, Any]:
        """Return the raw lineage graph as a plain dict.

        Returns:
            A dict with ``pipeline``, ``namespace``, ``run_id``,
            ``started_at``, and ``steps`` keys.

        Example::

            graph = collector.to_dict()
            print(graph[\"steps\"][0][\"tool\"])
        """
        return {
            "pipeline": self._pipeline_name,
            "namespace": self.namespace,
            "run_id": self._run_id,
            "started_at": self._started_at,
            "steps": list(self._steps),
        }

    def __len__(self) -> int:
        return len(self._steps)

    def __repr__(self) -> str:
        return (
            f"LineageCollector(namespace={self.namespace!r}, "
            f"pipeline={self._pipeline_name!r}, steps={len(self._steps)})"
        )
