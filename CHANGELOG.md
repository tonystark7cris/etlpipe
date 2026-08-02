# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] — 2026-08-01

### Added (`etlpipe-governance` v0.2.0)
- **Value-Level Expectation Rules**: `expect_schema` now supports `min_value`, `max_value`, `allowed_values`, `value_regex`, `min_length`, `max_length`, and `unique` constraints per column. Old schemas remain fully backward-compatible.
- **Volume Checks**: New `expect_row_count()` function and `ContractSuite.add_volume_check()` method to guard against empty tables, truncated feeds, or unexpected data explosions.
- **Freshness Checks**: New `expect_freshness()` function and `ContractSuite.add_freshness_check()` method to assert datetime columns contain sufficiently recent data (stale feed detection).
- **YAML / JSON Schema-as-Code**: New `load_schema()` and `save_schema()` functions to store schema contracts as version-controlled files (`.yaml`, `.yml`, `.json`). Optional `PyYAML` dependency.
- **Audit Trail**: New `AuditTrail` class that persists every `ContractSuite.run()` result to a queryable JSONL log with `run_id`, timestamps, and custom metadata. Supports filtering by `days` or `run_id`.
- **HTML / JSON Report Export**: New `export_report()` function that generates self-contained dark-mode HTML reports or structured JSON reports from governance results.
- **`ContractSuite` Integration**: `suite.run()` now accepts `audit_trail` and `run_id` parameters for automatic persistence. Volume and freshness checks appear as rows in the combined report.

### Changed
- **`etlpipe-governance` version bumped to 0.2.0**.
- **`ContractSuite.__len__`** now includes volume and freshness checks in the count.
- **`pyproject.toml`** updated with optional `[yaml]` and `[all]` dependency extras.

## [2.0.0] — 2026-07-22

### Added
- **`.yxmd` Workflow Converter**: New `YxmdConverter` class and `etlpipe-convert` CLI tool to convert proprietary visual ETL workflow XML files into Etlpipe YAML pipelines. Supports 15+ tool mappings with expression translation, topological sorting, and graceful degradation for unparseable tools.
- **Enterprise Governance Sub-Package (`etlpipe-governance`)**: Extracted and expanded data quality toolkit into a standalone package:
  - `scan_pii()` — Detects PII across 12 international patterns (email, phone, SSN, credit card, Aadhaar, IBAN, passport, etc.) with confidence scoring.
  - `mask_pii()` — Three masking strategies: `redact`, `hash` (SHA-256), and `pseudonymise` (reversible labels with mapping). Competitive differentiator vs. Great Expectations/Pandera.
  - `expect_schema()` / `infer_schema()` — Schema contract validation with dtype aliases, nullability checks, strict/non-strict modes.
  - `profile()` — Statistical profiler with cardinality, null rates, min/max/mean/std, and top-N value distributions.
  - `ContractSuite` — Batch contract runner for pipeline audit checkpoints with PASS/FAIL/SKIPPED/WARN/ERROR reporting.
- **Structured Logging**: Replaced all `print()` statements in pipeline engine with `logging.getLogger()` using hierarchical names (`etlpipe.pipeline`, `etlpipe.engines.pandas`, etc.). Pipeline metrics emitted as structured JSON.
- **Pipeline Execution Metrics**: Per-step timing (`duration_s`), row counts, output types, and status tracking. Metrics accessible via `Pipeline.metrics` after execution.
- **Pipeline Event Hooks**: Four lifecycle callbacks (`on_step_start`, `on_step_complete`, `on_step_error`, `on_pipeline_complete`) for integrating with Slack, PagerDuty, Teams, or any alerting system without adding those as dependencies.
- **Retry/Backoff for Downloads**: `Developer.download()` now supports configurable `max_retries` (default 3) and `retry_delay` (default 1.0s) with exponential backoff. Handles `URLError`, `TimeoutError`, `OSError`, and HTTP 5xx responses.
- **Schema Contracts in YAML Pipelines**: Steps can declare `output_schema` to enforce data contracts as part of pipeline execution.
- **Spark Integration Tests in CI**: Dedicated non-blocking CI job running Spark backend tests on Python 3.12.
- **Security Policy**: Added `SECURITY.md` with vulnerability reporting process, response timeline, and security track record.
- **Contributing Guide**: Added `CONTRIBUTING.md` with dev setup, code standards, testing requirements, and PR process.
- **Architecture Decision Records**: Added `doc/adr/` with template and records for dual-backend architecture and eval() removal.
- **Enterprise Governance Documentation**: New section in `USER_GUIDE.md` covering PII scanning, data contracts, event hooks, OpenLineage integration patterns, and data catalog recommendations.

### Changed
- **Version bump to 2.0.0** — reflects new sub-package, converter, and breaking packaging changes.
- **Development Status upgraded from Alpha to Beta** in PyPI classifiers.
- **Wheel now bundles `etlpipe_governance`** alongside `etlpipe` — governance features are available without separate installation.
- **Governance tests included in default pytest** via `testpaths` configuration.
- **Backward-compatible shim modules** (`etlpipe._contracts`, `etlpipe._pii`) re-export from `etlpipe_governance` with deprecation warnings targeting removal in 3.0.

### Security
- **Converter uses `defusedxml`** for safe XML parsing of `.yxmd` files (XXE/SSRF protection). Falls back with a hard error if `defusedxml` is not available (no silent downgrade).

## [1.0.0] — 2026-07-04

### Added
- **Automated CI/CD**: Added a GitHub Actions workflow using OIDC (Trusted Publishing) for automated, secure PyPI deployments on new GitHub Releases.
- **Enterprise Edge Case Protections**: Built a background transpiler to auto-backtick column headers containing spaces to support dirty real-world enterprise datasets without syntax crashes.

### Changed
- **Memory Optimization (Pandas)**: The Pandas backend now automatically requires the `pyarrow` multi-threaded C++ engine when loading large CSV files, heavily reducing physical RAM usage and preventing `MemoryError` crashes.
- **Datatype Coercion**: `Join.join` now dynamically casts mismatching datatypes between left and right anchor columns, eliminating strict PySpark `AnalysisException` errors when migrating disparate schemas.

### Fixed
- **Critical Security Fix**: Eradicated an arbitrary code execution vulnerability (RCE) in `Preparation.formula` by removing the insecure `eval()` fallback. The engine is now entirely zero-trust and sandboxed via `pd.eval` or strict `lambda` callables.
- **Spark Architecture (Sorting Death Trap)**: Completely refactored `Preparation.record_id` to utilize parallelized `F.monotonically_increasing_id()` instead of `Window.orderBy`, eliminating massive single-node memory bottlenecks when scaling Spark pipelines.
- **Spark Architecture (Tuple Bombs)**: Injected native `.persist()` boundaries directly into the upstream nodes of `Join.join` to prevent PySpark from redundantly computing the entire historical DAG multiple times during joins.
- **Regex Edge Cases**: Fixed an engine logic gap where Regex capture groups incorrectly counted non-capturing groups `(?:)` in the Spark backend.
## [0.2.0] — 2026-07-04

### Added
- **Enterprise Scalability (Dual-Backend Architecture)**: Added native support for distributed execution on big-data clusters using the new `SparkEngine`.
- **Thread-Safe Context Manager**: Added `Etlpipe.backend()` context manager to allow concurrent multi-threading with different execution engines.
- **Dynamic Dispatch**: `Etlpipe.set_backend("spark")` now seamlessly reroutes all tool executions down to Spark SQL and Vectorized Pandas UDFs (PyArrow).

### Changed
- All 55 Core tools have been refactored into thin dispatchers to support multiple engine backends without altering user-facing APIs.
- Updated `README.md` and created `USER_GUIDE.md` with complete documentation, tool reference tables, and declarative YAML pipeline configurations.

## [0.1.0] — 2025-06-28

- **InOut** class — `input_data`, `output_data`, `text_input`, `browse`, `directory`, `date_time_now`
- **Preparation** class — `filter`, `formula`, `select`, `data_cleansing`, `sort`, `unique`, `sample`, `record_id`, `generate_rows`, `auto_field`, `multi_field_formula`, `multi_row_formula`, `tile`, `imputation`
- **Join** class — `join`, `join_multiple`, `union`, `find_replace`, `append_fields`, `fuzzy_match`
- **Transform** class — `summarize`, `transpose`, `cross_tab`, `running_total`, `count_records`
- **Parse** class — `date_time`, `regex_match`, `regex_parse`, `regex_replace`, `regex_tokenize`, `text_to_columns`, `xml_parse`
- **Developer** class — `base64_encode`, `base64_decode`, `download`, `column_info`, `dynamic_rename`
- Full test suite with pytest
- Type hints and Google-style docstrings on all public methods
