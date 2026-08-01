"""Audit trail for governance scan and contract results.

Persists every :class:`ContractSuite` run and PII scan to a structured
log file so that governance history is queryable and auditable.

Example::

    from etlpipe_governance import AuditTrail, ContractSuite

    trail = AuditTrail(path="./governance_logs")

    # Automatically log every suite run
    results = suite.run(dataframes, audit_trail=trail, run_id="daily_2026-08-01")

    # Query history
    history = trail.load()
    last_7 = trail.load(days=7)
    failed = history[history["Status"] == "FAIL"]
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("etlpipe_governance.audit")


class AuditTrail:
    """Persistent audit log for governance results.

    Stores results as newline-delimited JSON (``.jsonl``) by default,
    making the log append-friendly and easy to parse with standard tools.

    Args:
        path: Directory where audit log files are stored.  Created
            automatically if it does not exist.
        filename: Name of the log file.  Defaults to ``"audit_log.jsonl"``.

    Example::

        trail = AuditTrail("./governance_logs")
        trail.log(results_df, run_id="nightly_2026-08-01")
        history = trail.load(days=30)
    """

    def __init__(
        self,
        path: str | Path = "./governance_logs",
        filename: str = "audit_log.jsonl",
    ) -> None:
        self._dir = Path(path)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._dir / filename

    @property
    def log_path(self) -> Path:
        """Return the absolute path to the audit log file."""
        return self._log_file.resolve()

    def log(
        self,
        results: pd.DataFrame,
        *,
        run_id: str | None = None,
        suite_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Append governance results to the audit log.

        Each row in *results* is written as a single JSON line with
        additional context fields.

        Args:
            results: A results DataFrame (as returned by
                :meth:`ContractSuite.run` or :func:`scan_pii`).
            run_id: Optional identifier for this run (e.g. date string,
                DAG run ID, or CI build number).
            suite_name: Optional suite name to tag the records.
            metadata: Optional dict of extra metadata to attach to
                every record (e.g. environment, pipeline name).

        Returns:
            The path to the log file.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        extra: dict[str, Any] = {
            "run_id": run_id or timestamp,
            "run_timestamp": timestamp,
        }
        if suite_name:
            extra["suite_name"] = suite_name
        if metadata:
            extra.update(metadata)

        records = results.to_dict(orient="records")
        with open(self._log_file, "a", encoding="utf-8") as f:
            for record in records:
                merged = {**extra, **record}
                f.write(json.dumps(merged, default=str, ensure_ascii=False) + "\n")

        logger.info(
            "Audit trail: logged %d record(s) to %s (run_id=%s)",
            len(records),
            self._log_file,
            extra["run_id"],
        )
        return self._log_file

    def load(
        self,
        *,
        days: int | None = None,
        run_id: str | None = None,
    ) -> pd.DataFrame:
        """Load audit history from the log file.

        Args:
            days: If set, only return records from the last *days* days.
            run_id: If set, only return records matching this run ID.

        Returns:
            A DataFrame containing all matching audit records.  Returns
            an empty DataFrame if no log file exists or no records match.

        Example::

            >>> trail.load(days=7)
            >>> trail.load(run_id="nightly_2026-08-01")
        """
        if not self._log_file.exists():
            logger.debug("No audit log found at %s", self._log_file)
            return pd.DataFrame()

        records: list[dict[str, Any]] = []
        with open(self._log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed audit log line: %s", line[:80])

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # Filter by days
        if days is not None and "run_timestamp" in df.columns:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            df["run_timestamp"] = pd.to_datetime(df["run_timestamp"], errors="coerce", utc=True)
            df = df[df["run_timestamp"] >= cutoff]

        # Filter by run_id
        if run_id is not None and "run_id" in df.columns:
            df = df[df["run_id"] == run_id]

        return df.reset_index(drop=True)

    def clear(self) -> None:
        """Delete the audit log file.

        Use with caution — this permanently removes all history.
        """
        if self._log_file.exists():
            self._log_file.unlink()
            logger.info("Audit trail cleared: %s", self._log_file)

    def __repr__(self) -> str:
        exists = self._log_file.exists()
        size = self._log_file.stat().st_size if exists else 0
        return f"AuditTrail(path={self._dir!r}, file={self._log_file.name!r}, size={size}B)"
