"""etlpipe-governance — Data Quality & Compliance toolkit.

A standalone sub-package for enterprise-grade data quality, PII detection,
masking, schema contracts, and statistical profiling.

Competes with Pandera and Great Expectations with a leaner footprint and
deeper PII-specific tooling.

Quick start::

    from etlpipe_governance import (
        scan_pii, mask_pii,
        expect_schema, infer_schema, profile,
        ContractSuite, SchemaViolationError,
    )

    # Detect PII
    report = scan_pii(df)

    # Mask it
    masked_df = mask_pii(df, report, strategy="redact")

    # Profile column statistics
    stats = profile(df)

    # Enforce a schema contract
    expect_schema(df, {"columns": {"ID": {"dtype": "int", "nullable": False}}})

    # Run multiple contracts in one audit
    suite = ContractSuite("My Pipeline Audit")
    suite.add_contract("raw_schema", schema_dict)
    results = suite.run(df)

Not affiliated with or endorsed by Pandera or Great Expectations.
"""

from __future__ import annotations

from etlpipe_governance._version import __version__
from etlpipe_governance.contracts import (
    ContractSuite,
    SchemaViolationError,
    expect_schema,
    infer_schema,
    profile,
)
from etlpipe_governance.pii import PIIWarning, mask_pii, scan_pii

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
]
