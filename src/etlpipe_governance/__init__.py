"""etlpipe-governance — Data Quality & Compliance toolkit.

A standalone sub-package for enterprise-grade data quality, PII detection,
masking, schema contracts, statistical profiling, audit trails, and reporting.

Competes with Pandera and Great Expectations with a leaner footprint and
deeper PII-specific tooling.

Quick start::

    from etlpipe_governance import (
        scan_pii, mask_pii,
        expect_schema, infer_schema, profile,
        expect_row_count, expect_freshness,
        load_schema, save_schema,
        AuditTrail, export_report,
        ContractSuite, SchemaViolationError, FreshnessError,
    )

    # Detect PII
    report = scan_pii(df)

    # Mask it
    masked_df = mask_pii(df, report, strategy="redact")

    # Profile column statistics
    stats = profile(df)

    # Enforce a schema contract (with value rules)
    expect_schema(df, {"columns": {
        "ID": {"dtype": "int", "nullable": False, "unique": True},
        "Age": {"dtype": "int", "min_value": 0, "max_value": 120},
    }})

    # Load schemas from YAML/JSON files
    schema = load_schema("schemas/sales.yaml")

    # Volume and freshness checks
    expect_row_count(df, min_rows=100)
    expect_freshness(df, column="updated_at", max_age=timedelta(hours=6))

    # Run multiple contracts in one audit with audit trail
    trail = AuditTrail("./governance_logs")
    suite = ContractSuite("My Pipeline Audit")
    suite.add_contract("raw_schema", schema_dict)
    results = suite.run(dataframes, audit_trail=trail)

    # Export a report
    export_report(results, "reports/audit.html")

Not affiliated with or endorsed by Pandera or Great Expectations.
"""

from __future__ import annotations

from etlpipe_governance._version import __version__
from etlpipe_governance.audit import AuditTrail
from etlpipe_governance.contracts import (
    ContractSuite,
    FreshnessError,
    SchemaViolationError,
    expect_freshness,
    expect_row_count,
    expect_schema,
    infer_schema,
    profile,
)
from etlpipe_governance.pii import PIIWarning, mask_pii, scan_pii
from etlpipe_governance.reporting import export_report
from etlpipe_governance.schema_io import load_schema, save_schema, schema_to_yaml

__all__ = [
    "__version__",
    # PII
    "scan_pii",
    "mask_pii",
    "PIIWarning",
    # Contracts & profiling
    "expect_schema",
    "infer_schema",
    "profile",
    "ContractSuite",
    "SchemaViolationError",
    # Volume & freshness
    "expect_row_count",
    "expect_freshness",
    "FreshnessError",
    # Schema I/O
    "load_schema",
    "save_schema",
    "schema_to_yaml",
    # Audit trail
    "AuditTrail",
    # Reporting
    "export_report",
]
