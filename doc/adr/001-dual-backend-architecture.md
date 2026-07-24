# ADR 001: Dual-Backend Engine Architecture

## Status

**ACCEPTED**

*Date: 2026-07-04*

## Context

Etlpipe was originally built with a hardcoded Pandas implementation. Enterprise clients need to run the same pipeline logic on both local machines (development/testing) and distributed Spark clusters (production at scale). Rewriting pipeline code for each environment is error-prone and doubles maintenance burden.

We needed an architecture that:
1. Lets users write pipeline logic once and execute on either Pandas or Spark
2. Keeps the public API unchanged regardless of backend
3. Supports runtime backend switching (even within a single process)
4. Maintains thread-safety for concurrent pipeline execution

## Decision

Implement an **Abstract Backend Engine** pattern:

1. **`BackendEngine` (ABC)** — defines the contract for all 55+ tool methods
2. **`PandasEngine`** — concrete implementation using pandas/numpy
3. **`SparkEngine`** — concrete implementation using PySpark SQL + Vectorized UDFs
4. **Public palette classes** (`Preparation`, `Join`, etc.) become thin dispatchers that call `get_engine().<method>()`
5. **Thread-local config** (`_config.py`) manages the active backend per-thread using `threading.local()`
6. A **context manager** (`etlpipe.backend("spark")`) enables scoped backend switching

The Spark engine uses a 3-tier execution strategy:
- **Tier 1**: Native Spark SQL (preferred — fully distributed)
- **Tier 2**: Vectorized Pandas UDFs via PyArrow (for complex row logic)
- **Tier 3**: Driver-side fallback with `.toPandas()` (for operations that cannot be distributed)

## Consequences

### Positive

- Users write pipeline logic exactly once — same code runs on laptop or 100-node cluster
- Thread-safe — multiple backends can run concurrently in the same process
- No user-facing API changes when adding new backends in the future
- Auto-checkpointing in SparkEngine prevents DAG explosion for long pipelines

### Negative

- Engine implementations are large files (~55KB each) since every tool must be implemented twice
- Some Spark implementations have subtle behavioral differences (e.g., `record_id` uses `monotonically_increasing_id()` which is non-sequential)
- The `_log_operation()` method in SparkEngine avoids `.count()` to preserve lazy evaluation, which means row counts are not available in Spark debug logs

### Neutral

- Future backends (e.g., Polars, DuckDB) can be added by implementing `BackendEngine` without touching any existing code
