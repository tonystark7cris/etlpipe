# ADR-003: Spin Off Governance Tools into `etlpipe-governance`

## Status

**ACCEPTED**

*Date: 2026-07-22*

## Context

etlpipe's core positioning is "The Visual ETL Migration Accelerator" â€” a tool
that helps companies move from proprietary GUI tools to open-source Python ETL. This message
is clean, specific, and targets a well-defined buyer (CFO/CIO who wants to cut
expensive desktop visual ETL licensing costs, consultants, Data Analysts in transition).

However, etlpipe also ships two powerful features that belong to a completely
different market:

1. **`scan_pii`** â€” a PII detection scanner for GDPR/HIPAA compliance
2. **`expect_schema` / `infer_schema`** â€” a schema contract validation system

These features are excellent, but:

- They target a different buyer (Data Quality engineers, compliance teams,
  platform teams running data observability tooling).
- They dilute the migration-accelerator message on the README and marketing pages.
- Competitors in this space (Pandera, Great Expectations, ydata-profiling) are
  established but have gaps: none of them offer integrated **PII masking**
  alongside detection.
- Releasing as a separate package signals professionalism and allows independent
  versioning, changelog, and PyPI discoverability.

## Decision

Extract `_pii.py` and `_contracts.py` into a standalone installable Python
package named **`etlpipe-governance`**, living at
`src/etlpipe_governance/` within the same monorepo.

### Key constraints honoured

1. **Zero breaking changes.** All existing public imports continue to work:
   ```python
   from etlpipe import scan_pii, expect_schema, infer_schema, SchemaViolationError
   ```
   This is enforced by thin re-export shims in `etlpipe/_pii.py` and
   `etlpipe/_contracts.py`.

2. **Single source of truth.** The implementation lives exclusively in
   `etlpipe_governance/`. The shims import from there. No code is duplicated.

3. **Independent installability.** `etlpipe-governance` depends only on
   `pandas>=1.5` â€” it does not require `etlpipe` to be installed. This
   allows data quality teams to adopt it without committing to the ETL layer.

4. **Optional integration.** `etlpipe` users can get both packages with:
   ```bash
   pip install etlpipe[governance]
   ```

### New features added at spinoff time

To immediately differentiate from Pandera / Great Expectations and create a
compelling standalone value proposition:

| Feature | Description |
|---|---|
| `mask_pii(df, report, strategy)` | Three masking strategies: `redact`, `hash`, `pseudonymise`. Fills the gap that GE/Pandera leave open â€” they detect but don't mask. |
| `profile(df)` | Rich per-column statistics (cardinality, null rate, min/max/mean/std, top-N values). Lighter than `ydata-profiling`. |
| `ContractSuite` | Run N schema contracts in one call, producing a combined pass/fail audit DataFrame. Suitable for pipeline observability dashboards. |

## Consequences

### Positive

- `etlpipe`'s README can focus entirely on the visual ETL migration message.
- `etlpipe-governance` has a clear standalone identity competing with
  Pandera and Great Expectations.
- `mask_pii` makes etlpipe-governance uniquely useful â€” it doesn't just
  detect PII, it makes data safe to use downstream.
- Independent PyPI versioning: governance can ship releases without touching
  the ETL layer.
- Consulting firms can adopt `etlpipe-governance` on existing Pandas
  stacks (no ETL migration required), creating a funnel into `etlpipe`.

### Negative

- Users must `pip install etlpipe-governance` separately (or use the
  `etlpipe[governance]` extras) to access the new `mask_pii`, `profile`,
  and `ContractSuite` features.
- The shim imports add a one-hop indirection in `etlpipe`. This is
  invisible at runtime but visible when reading the source.
- Maintaining two `pyproject.toml` files in the monorepo requires slightly
  more release discipline.

### Neutral

- The shim re-exports are scheduled for removal in `etlpipe` 3.0. A
  `DeprecationWarning` can be added at that time if adoption of the direct
  import path is sufficiently high.
- Test coverage is distributed: `src/etlpipe_governance/tests/` for unit
  tests; `tests/test_pii.py` and `tests/test_contracts.py` for backward-compat
  integration tests.
