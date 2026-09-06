"""Audit trail for governance scan and contract results.

Persists every :class:`ContractSuite` run and PII scan to a structured
log file so that governance history is queryable and auditable.

Supports pluggable **forwarders** so audit records can be simultaneously
streamed to enterprise SIEM / observability systems (Splunk, Sentinel, S3)
without losing local persistence.

Example::

    from etlpipe_governance import AuditTrail, ContractSuite
    from etlpipe_governance.audit import SplunkHECForwarder, WebhookForwarder

    # Configure forwarders
    splunk = SplunkHECForwarder(
        url="https://splunk.bank.internal:8088/services/collector/event",
        token=os.environ["SPLUNK_HEC_TOKEN"],
    )
    teams = WebhookForwarder(
        url=os.environ["TEAMS_WEBHOOK_URL"],
        headers={"Content-Type": "application/json"},
    )

    trail = AuditTrail(path="./governance_logs", forwarders=[splunk, teams])

    # Automatically log every suite run
    results = suite.run(dataframes, audit_trail=trail, run_id="daily_2026-08-01")

    # Query history
    history = trail.load()
    last_7 = trail.load(days=7)
    failed = history[history["Status"] == "FAIL"]
"""

from __future__ import annotations

import abc
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("etlpipe_governance.audit")


# ---------------------------------------------------------------------------
# Forwarder base class and built-in implementations
# ---------------------------------------------------------------------------


class AuditForwarder(abc.ABC):
    """Abstract base class for SIEM / observability audit forwarders.

    Implement :meth:`forward` to push audit records to any external system.
    Forwarders are registered via :class:`AuditTrail` ``forwarders`` parameter.

    Example::

        class MyForwarder(AuditForwarder):
            def forward(self, records: list[dict]) -> None:
                for rec in records:
                    my_siem_client.send(rec)
    """

    @abc.abstractmethod
    def forward(self, records: list[dict[str, Any]]) -> None:
        """Forward a batch of audit records to the target system.

        Args:
            records: A list of audit record dicts as stored in the JSONL log.
        """


class SplunkHECForwarder(AuditForwarder):
    """Forward audit records to Splunk via the HTTP Event Collector (HEC).

    Uses only ``urllib`` from the standard library — no ``requests`` dependency.

    Args:
        url: Splunk HEC endpoint URL
            (e.g. ``"https://splunk.bank.internal:8088/services/collector/event"``).
        token: Splunk HEC token. Retrieve from your bank's secret manager —
            never hardcode.
        index: Optional Splunk index name.
        source: Optional Splunk source value.
        sourcetype: Splunk sourcetype (default ``"etlpipe:governance"``).
        timeout: HTTP request timeout in seconds.

    Example::

        forwarder = SplunkHECForwarder(
            url="https://splunk.internal:8088/services/collector/event",
            token=os.environ["SPLUNK_HEC_TOKEN"],
        )
        trail = AuditTrail(forwarders=[forwarder])
    """

    def __init__(
        self,
        url: str,
        token: str,
        *,
        index: str | None = None,
        source: str = "etlpipe",
        sourcetype: str = "etlpipe:governance",
        timeout: int = 10,
    ) -> None:
        self._url = url
        self._token = token
        self._index = index
        self._source = source
        self._sourcetype = sourcetype
        self._timeout = timeout

    def forward(self, records: list[dict[str, Any]]) -> None:
        for record in records:
            event: dict[str, Any] = {
                "time": datetime.now(timezone.utc).timestamp(),
                "source": self._source,
                "sourcetype": self._sourcetype,
                "event": record,
            }
            if self._index:
                event["index"] = self._index

            payload = json.dumps(event, default=str).encode("utf-8")
            req = urllib.request.Request(
                self._url,
                data=payload,
                headers={
                    "Authorization": f"Splunk {self._token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
                    if resp.status >= 300:
                        logger.warning(
                            "SplunkHECForwarder: unexpected HTTP %d for record run_id=%s",
                            resp.status,
                            record.get("run_id", "?"),
                        )
            except urllib.error.URLError as exc:
                logger.error("SplunkHECForwarder: failed to send record: %s", exc)


class WebhookForwarder(AuditForwarder):
    """Forward audit records to any HTTP webhook (Teams, Slack, PagerDuty, etc.).

    Uses only ``urllib`` from the standard library.

    Args:
        url: Webhook URL.
        headers: HTTP headers dict (e.g. ``{"Content-Type": "application/json"}``).
        timeout: HTTP request timeout in seconds.

    Example::

        # Microsoft Teams incoming webhook
        forwarder = WebhookForwarder(
            url=os.environ["TEAMS_WEBHOOK_URL"],
            headers={"Content-Type": "application/json"},
        )
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        *,
        timeout: int = 10,
    ) -> None:
        self._url = url
        self._headers = headers or {"Content-Type": "application/json"}
        self._timeout = timeout

    def forward(self, records: list[dict[str, Any]]) -> None:
        payload = json.dumps({"audit_records": records}, default=str).encode("utf-8")
        req = urllib.request.Request(
            self._url,
            data=payload,
            headers=self._headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
                if resp.status >= 300:
                    logger.warning("WebhookForwarder: unexpected HTTP %d from webhook", resp.status)
        except urllib.error.URLError as exc:
            logger.error("WebhookForwarder: failed to send records: %s", exc)


class S3Forwarder(AuditForwarder):
    """Forward audit records to Amazon S3 as a JSONL file.

    Requires the ``s3fs`` optional dependency (``pip install etlpipe[cloud]``).

    Args:
        bucket: S3 bucket name.
        prefix: Key prefix for the audit log files (default ``"etlpipe/audit/"``).
            Records are written to ``{prefix}{run_id}.jsonl``.
        storage_options: Additional ``s3fs.S3FileSystem`` options
            (e.g. ``{"key": ..., "secret": ...}``).

    Example::

        forwarder = S3Forwarder(
            bucket="bank-audit-logs",
            prefix="etlpipe/governance/",
        )
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "etlpipe/audit/",
        *,
        storage_options: dict[str, Any] | None = None,
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._storage_options = storage_options or {}

    def forward(self, records: list[dict[str, Any]]) -> None:
        try:
            import s3fs
        except ImportError as exc:
            raise ImportError("s3fs is required for S3Forwarder. Install with: pip install etlpipe[cloud]") from exc

        run_id = records[0].get("run_id", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")) if records else "empty"
        key = f"{self._prefix}/{run_id}.jsonl"
        s3_path = f"s3://{self._bucket}/{key}"

        fs = s3fs.S3FileSystem(**self._storage_options)
        with fs.open(s3_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")

        logger.info("S3Forwarder: wrote %d record(s) to %s", len(records), s3_path)


class AuditTrail:
    """Persistent audit log for governance results.

    Stores results as newline-delimited JSON (``.jsonl``) and optionally
    fans out to enterprise SIEM / observability forwarders.

    Args:
        path: Directory where audit log files are stored.  Created
            automatically if it does not exist.
        filename: Name of the log file.  Defaults to ``"audit_log.jsonl"``.
        forwarders: Optional list of :class:`AuditForwarder` instances.
            Every :meth:`log` call will fan out to all registered forwarders
            in addition to the local file. Forwarder failures are logged
            as errors but do not interrupt pipeline execution.

    Example::

        from etlpipe_governance.audit import SplunkHECForwarder

        splunk = SplunkHECForwarder(
            url="https://splunk.internal:8088/services/collector/event",
            token=os.environ["SPLUNK_HEC_TOKEN"],
        )
        trail = AuditTrail("./governance_logs", forwarders=[splunk])
        trail.log(results_df, run_id="nightly_2026-08-01")
        history = trail.load(days=30)
    """

    def __init__(
        self,
        path: str | Path = "./governance_logs",
        filename: str = "audit_log.jsonl",
        forwarders: list[AuditForwarder] | None = None,
    ) -> None:
        self._dir = Path(path)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._dir / filename
        self._forwarders: list[AuditForwarder] = forwarders or []

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

        merged_records = [{**extra, **record} for record in records]

        # Fan out to registered SIEM forwarders
        if self._forwarders:
            for forwarder in self._forwarders:
                try:
                    forwarder.forward(merged_records)
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Audit forwarder %s raised an error (records still saved locally): %s",
                        type(forwarder).__name__,
                        exc,
                    )

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
