"""HTML and JSON report export for governance results.

Provides a one-liner to turn a :class:`ContractSuite` result DataFrame
into a shareable, self-contained HTML report or structured JSON file.

Example::

    from etlpipe_governance import export_report

    results = suite.run(dataframes)
    export_report(results, path="reports/audit_2026-08-01.html", format="html")
    export_report(results, path="reports/audit_2026-08-01.json", format="json")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("etlpipe_governance.reporting")

# ---------------------------------------------------------------------------
# HTML template (self-contained, no CDN dependencies)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --bg: #0f172a;
    --surface: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --pass: #22c55e;
    --pass-bg: rgba(34,197,94,0.12);
    --fail: #ef4444;
    --fail-bg: rgba(239,68,68,0.12);
    --warn: #f59e0b;
    --warn-bg: rgba(245,158,11,0.12);
    --skip: #64748b;
    --skip-bg: rgba(100,116,139,0.12);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 2rem;
    line-height: 1.6;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{
    font-size: 1.75rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .subtitle {{ color: var(--text-muted); margin-bottom: 1.5rem; font-size: 0.9rem; }}
  .summary {{
    display: flex;
    gap: 1rem;
    margin-bottom: 2rem;
    flex-wrap: wrap;
  }}
  .stat {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.5rem;
    min-width: 140px;
    text-align: center;
  }}
  .stat-value {{ font-size: 2rem; font-weight: 700; }}
  .stat-label {{ font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }}
  .stat-pass .stat-value {{ color: var(--pass); }}
  .stat-fail .stat-value {{ color: var(--fail); }}
  .stat-warn .stat-value {{ color: var(--warn); }}
  .stat-skip .stat-value {{ color: var(--skip); }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--surface);
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border);
  }}
  th {{
    background: rgba(100,116,139,0.15);
    padding: 0.75rem 1rem;
    text-align: left;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border);
  }}
  td {{
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.9rem;
    vertical-align: top;
  }}
  tr:last-child td {{ border-bottom: none; }}
  .badge {{
    display: inline-block;
    padding: 0.2rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .badge-pass {{ background: var(--pass-bg); color: var(--pass); }}
  .badge-fail {{ background: var(--fail-bg); color: var(--fail); }}
  .badge-warn {{ background: var(--warn-bg); color: var(--warn); }}
  .badge-skip {{ background: var(--skip-bg); color: var(--skip); }}
  .badge-error {{ background: var(--fail-bg); color: var(--fail); }}
  .violations {{
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 0.8rem;
    white-space: pre-wrap;
    color: var(--text-muted);
    max-width: 400px;
  }}
  footer {{
    margin-top: 2rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.75rem;
  }}
</style>
</head>
<body>
<div class="container">
  <h1>{title}</h1>
  <p class="subtitle">Generated at {timestamp}</p>
  <div class="summary">
    <div class="stat stat-pass"><div class="stat-value">{pass_count}</div><div class="stat-label">Passed</div></div>
    <div class="stat stat-fail"><div class="stat-value">{fail_count}</div><div class="stat-label">Failed</div></div>
    <div class="stat stat-warn"><div class="stat-value">{warn_count}</div><div class="stat-label">Warnings</div></div>
    <div class="stat stat-skip"><div class="stat-value">{skip_count}</div><div class="stat-label">Skipped</div></div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Contract</th>
        <th>Description</th>
        <th>Status</th>
        <th>Violations</th>
      </tr>
    </thead>
    <tbody>
{table_rows}
    </tbody>
  </table>
  <footer>etlpipe-governance audit report</footer>
</div>
</body>
</html>"""


def _status_badge(status: str) -> str:
    """Return an HTML badge for a status string."""
    css_class = {
        "PASS": "badge-pass",
        "FAIL": "badge-fail",
        "WARN": "badge-warn",
        "SKIPPED": "badge-skip",
        "ERROR": "badge-error",
    }.get(status.upper(), "badge-skip")
    return f'<span class="badge {css_class}">{status}</span>'


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def export_report(
    results: pd.DataFrame,
    path: str | Path,
    *,
    format: str = "html",
    title: str = "Governance Audit Report",
) -> Path:
    """Export a governance results DataFrame as an HTML or JSON report.

    Args:
        results: A results DataFrame (as returned by
            :meth:`ContractSuite.run`).
        path: Destination file path.
        format: Output format — ``"html"`` (default) or ``"json"``.
        title: Report title (used in HTML heading and JSON metadata).

    Returns:
        The resolved :class:`Path` that was written.

    Raises:
        ValueError: If *format* is not ``"html"`` or ``"json"``.

    Example::

        >>> export_report(results, "reports/audit.html")
        >>> export_report(results, "reports/audit.json", format="json")
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if format == "html":
        _export_html(results, path, title)
    elif format == "json":
        _export_json(results, path, title)
    else:
        raise ValueError(f"Unsupported format: {format!r}. Use 'html' or 'json'.")

    logger.info("Exported %s report to %s (%d results)", format, path, len(results))
    return path


def _export_html(results: pd.DataFrame, path: Path, title: str) -> None:
    """Write a self-contained HTML report."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Count statuses
    status_counts = results["Status"].value_counts() if "Status" in results.columns else pd.Series(dtype=int)
    pass_count = int(status_counts.get("PASS", 0))
    fail_count = int(status_counts.get("FAIL", 0))
    warn_count = int(status_counts.get("WARN", 0))
    skip_count = int(status_counts.get("SKIPPED", 0)) + int(status_counts.get("ERROR", 0))

    # Build table rows
    table_rows = []
    for _, row in results.iterrows():
        contract = _escape_html(str(row.get("Contract", "")))
        description = _escape_html(str(row.get("Description", "")))
        status = str(row.get("Status", ""))
        violations = _escape_html(str(row.get("Violations", "")))

        table_rows.append(
            f"      <tr>\n"
            f"        <td>{contract}</td>\n"
            f"        <td>{description}</td>\n"
            f"        <td>{_status_badge(status)}</td>\n"
            f'        <td><div class="violations">{violations}</div></td>\n'
            f"      </tr>"
        )

    html = _HTML_TEMPLATE.format(
        title=_escape_html(title),
        timestamp=timestamp,
        pass_count=pass_count,
        fail_count=fail_count,
        warn_count=warn_count,
        skip_count=skip_count,
        table_rows="\n".join(table_rows),
    )

    path.write_text(html, encoding="utf-8")


def _export_json(results: pd.DataFrame, path: Path, title: str) -> None:
    """Write a structured JSON report."""
    timestamp = datetime.now(timezone.utc).isoformat()

    report: dict[str, Any] = {
        "title": title,
        "run_timestamp": timestamp,
        "total_checks": len(results),
        "summary": {},
        "results": results.to_dict(orient="records"),
    }

    if "Status" in results.columns:
        report["summary"] = results["Status"].value_counts().to_dict()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str, ensure_ascii=False)
