# 🐦 Etlpipe: The Visual ETL-to-Python Migration Engine

**The fastest path from proprietary visual ETL to open-source Python.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/etlpipe.svg)](https://pypi.org/project/etlpipe/)

---

Welcome to the **Etlpipe Documentation**! Etlpipe is the translation layer designed for data directors, consultants, analysts, and engineers moving enterprise workflows off expensive proprietary visual ETL software onto open-source Python.

---

## Overview & Purpose

### What is Etlpipe?
Etlpipe is the **Visual ETL Migration Accelerator**. It provides a 1:1 API mapping of visual ETL tool palettes (`Preparation`, `Join`, `Transform`, `Parse`, `InOut`, `Developer`) to clean Python code and declarative YAML—allowing enterprise teams to eliminate per-seat licensing costs and migrate workflows to Python in weeks, not months.

### Why Etlpipe Exists
1. **The Cost Trap:** Proprietary visual ETL software costs **$3,000 to $5,000+ per user annually**. A team of 20 analysts costs $100k+ every single year just for desktop GUI licenses.
2. **The Cognitive Gap:** Companies want to move to free, open-source Python (`pandas`/`PySpark`), but their analysts only understand visual ETL concepts (Filter T/F anchors, Join L/J/R anchors, Summarize). Teaching an analyst Pandas from scratch takes months and stalls productivity.
3. **The Etlpipe Solution:** Etlpipe bridges this gap. Analysts write `Preparation.filter()` using familiar mental models or auto-convert `.yxmd` workflow files using `etlpipe-convert`. Data Engineers get clean, testable Python code ready for Airflow or Databricks.

### Value Proposition by Persona
- **For CIOs & Data Directors:** Eliminates expensive visual ETL desktop licensing fees, saving $100k+ annually while eliminating vendor lock-in.
- **For Data Analysts:** Zero friction. Workflows translate 1:1 using familiar concepts (`Summarize`, `Join`, `Formula`) and visual anchors (`L, J, R` or `T, F` tuples).
- **For Data Engineers & Consultants:** Automated CLI tool (`etlpipe-convert`) translates `.yxmd` XML workflows into executable Etlpipe YAML/Python pipelines automatically.
- **Enterprise Scalability (Dual Backend):** Develop locally using **Pandas**, then switch backend to **PySpark** with one line (`etlpipe.set_backend("spark")`) to scale across distributed clusters without altering business logic.
- **Standalone Data Governance:** Integrated or modular data quality via `etlpipe-governance` (PII scanning/masking with 20 patterns, schema contracts, volume & freshness checks, YAML schemas, audit trails, HTML reporting).
- **Bank & Enterprise Security (v2.2.0):** 9-component security hardening — pickle permanently removed (CWE-502), HTTPS enforcement, secrets management, RBAC pipeline guards, OpenLineage data lineage (BCBS 239), SIEM audit forwarding (Splunk/Teams/S3), and AES-256-GCM encrypted PII mapping storage. See [`SECURITY.md`](SECURITY.md).

---

## Installation & Setup

Etlpipe runs anywhere Python 3.10+ is supported.

### Installation Options

```bash
# Core Etlpipe Engine (Includes Converter & Bundled Governance Tools)
pip install etlpipe

# With PySpark Support (For Big Data Clusters & Distributed Pipelines)
pip install etlpipe[spark]

# With Cloud Storage Support (S3, GCS, ADLS via fsspec & s3fs)
pip install etlpipe[cloud]

# Standalone Data Governance Package (If only using PII/Contracts without Etlpipe engine)
pip install etlpipe-governance

# Install All Dependencies (Spark + Cloud + Governance)
pip install etlpipe[all]
```

### Docker
To run Etlpipe in a containerized environment (e.g., for Kubernetes or AWS ECS):
```dockerfile
FROM python:3.10-slim
WORKDIR /app
# Install Etlpipe with standard backend
RUN pip install --no-cache-dir etlpipe
COPY . /app
CMD ["python", "pipeline.py"]
```

### Cloud Environments (Airflow, Databricks)
- **Airflow**: Add `etlpipe` to your `requirements.txt`. Your DAGs can wrap Etlpipe logic inside `PythonOperator`.
- **Databricks**: Install `etlpipe` as a cluster library (do not use `[spark]` as Databricks provides it natively). Your Etlpipe pipelines will transparently dispatch execution to the Databricks Spark cluster.

---

## Core Concepts

Etlpipe revolves around several core principles:

### 1. The Six Core Palettes
Etlpipe implements all core visual ETL tools grouped into logical palettes:
- **InOut**: Reading/writing data (`input_data`, `output_data`).
- **Preparation**: Cleaning, filtering, sorting, and row-level generation (`filter`, `formula`, `select`, `data_cleansing`).
- **Join**: Blending datasets together (`join`, `union`, `find_replace`).
- **Transform**: Aggregating and reshaping data (`summarize`, `cross_tab`, `transpose`).
- **Parse**: Extracting strings, regex, and datetimes (`date_time`, `regex_parse`).
- **Developer**: Assertions, testing, and dynamic metadata (`test`, `column_info`).

### 2. Immutability
All Etlpipe functions are pure. The original DataFrames are never mutated. Every tool execution returns a brand-new DataFrame (or tuple of DataFrames).

### 3. Output Anchors (Tuples)
In a visual ETL tool, a tool like `Filter` has a 'True' and 'False' output anchor. In Etlpipe, these return as a tuple:
```python
high_value, low_value = Preparation.filter(df, "Revenue > 1000")
```

### 4. Dual Engines
Set the backend dynamically based on scale requirements:
```python
import etlpipe
etlpipe.set_backend("spark") # Defaults to "pandas"
```

---

## Comprehensive Tool Reference

Below is a detailed breakdown of every tool available in Etlpipe, complete with usage examples in Python. For YAML usage, you can map the arguments directly.

### 🔌 InOut Palette

- **`InOut.input_data(path: str)`**: Reads data from CSV, Excel, JSON, or Parquet. Auto-detects format. **Note: `.pkl`/`.pickle` files raise `PickleRemovedError` (CWE-502 — permanently blocked).**
  *Usage*: `df = InOut.input_data("data.csv")`
- **`InOut.output_data(df, path: str)`**: Writes a DataFrame to a specified file format. **Note: `.pkl`/`.pickle` destinations raise `PickleRemovedError`. Use Parquet instead.**
  *Usage*: `InOut.output_data(df, "output.parquet")`
- **`InOut.text_input(data: list|dict)`**: Creates a DataFrame from inline dictionaries or lists.
  *Usage*: `df = InOut.text_input([{"id": 1, "val": "A"}, {"id": 2, "val": "B"}])`
- **`InOut.browse(df)`**: Prints rich summary statistics, types, and head to stdout (similar to Browse tool).
  *Usage*: `InOut.browse(df)`
- **`InOut.directory(path: str)`**: Returns a DataFrame listing files in a directory with metadata.
  *Usage*: `df_files = InOut.directory("./data_folder")`
- **`InOut.date_time_now()`**: Returns a single-row DataFrame with the current timestamp.
  *Usage*: `df_time = InOut.date_time_now()`

### 🔧 Preparation Palette

- **`Preparation.filter(df, condition: str)`**: Splits data based on a SQL-like string condition. Returns `(true_df, false_df)`.
  *Usage*: `high, low = Preparation.filter(df, "Sales > 100")`
- **`Preparation.formula(df, column: str, expression: str | callable)`**: Adds or updates a column. (Note: Column names with spaces are automatically backticked for you. For complex Python logic, pass a `lambda` callable instead of a string to ensure strict security).
  *Usage*: `df = Preparation.formula(df, "Profit", "Revenue - Cost")`
- **`Preparation.select(df, columns: list, rename: dict=None, cast_types: dict=None)`**: Subsets, renames, and casts types.
  *Usage*: `df = Preparation.select(df, ["A", "B"], rename={"A": "Alpha"}, cast_types={"B": "str"})`
- **`Preparation.data_cleansing(df, columns: list, strip_whitespace: bool, modify_case: str, replace_nulls_with: Any)`**: Cleanses text columns.
  *Usage*: `df = Preparation.data_cleansing(df, ["Name", "City"], strip_whitespace=True, modify_case="upper")`
- **`Preparation.sort(df, columns: list, ascending: bool|list)`**: Sorts the DataFrame.
  *Usage*: `df = Preparation.sort(df, ["Date", "Sales"], ascending=[True, False])`
- **`Preparation.unique(df, columns: list)`**: Splits into `(unique_df, duplicate_df)`.
  *Usage*: `uniq, dupes = Preparation.unique(df, ["CustomerID"])`
- **`Preparation.sample(df, n: int, position: str, random: bool)`**: Extracts first N, last N, random N, or percent.
  *Usage*: `df = Preparation.sample(df, n=100, random=True, random_state=42)`
- **`Preparation.record_id(df, column_name: str="RecordID")`**: Adds an auto-incrementing integer ID. *Note: When using the Spark engine, IDs are unique and monotonically increasing, but not strictly sequential (to prevent cluster sorting bottlenecks).*
  *Usage*: `df = Preparation.record_id(df)`
- **`Preparation.generate_rows(count: int, expression: callable)`**: Generates sequential rows.
  *Usage*: `df = Preparation.generate_rows(10, lambda i: {"Row": i, "Value": i * 2})`
- **`Preparation.auto_field(df)`**: Optimizes data types to save memory footprint.
  *Usage*: `df = Preparation.auto_field(df)`
- **`Preparation.multi_field_formula(df, columns: list, expression: callable)`**: Applies one formula across many columns.
  *Usage*: `df = Preparation.multi_field_formula(df, ["Q1", "Q2"], lambda s: s * 1.1)`
- **`Preparation.multi_row_formula(df, column: str, expression: callable, rows_back: int, group_by: list)`**: Formulas referencing prior/next rows.
  *Usage*: `df = Preparation.multi_row_formula(df, "Running", lambda curr, prev: curr + prev.fillna(0), group_by=["Region"])`
- **`Preparation.tile(df, column: str, tiles: int, method: str)`**: Groups data into quantiles/bins.
  *Usage*: `df = Preparation.tile(df, "Sales", 4, method="quantiles")`
- **`Preparation.imputation(df, column: str, method: str)`**: Fills missing values (mean/median/mode).
  *Usage*: `df = Preparation.imputation(df, "Age", method="mean")`
- **`Preparation.create_samples(df, estimation: float, validation: float, holdout: float)`**: Splits for ML (fractions must sum to 1.0). Returns `(est_df, val_df, hold_df)`.
  *Usage*: `train, val, test = Preparation.create_samples(df, 0.7, 0.2, 0.1)`
- **`Preparation.date_filter(df, column: str, start: str, end: str)`**: Filters by date range.
  *Usage*: `df = Preparation.date_filter(df, "Date", "2023-01-01", "2023-12-31")`
- **`Preparation.oversample_field(df, column: str, value: Any, target_pct: float)`**: Balances target classes via stratified sampling.
  *Usage*: `df = Preparation.oversample_field(df, "Churn_Flag", "Yes", target_pct=0.5)`
- **`Preparation.rank(df, column: str, group_by: list=None)`**: Assigns numeric ranks.
  *Usage*: `df = Preparation.rank(df, "Sales", group_by=["Region"])`

### 🔗 Join Palette

- **`Join.join(left, right, on: str)`**: Standard join. Returns `(Left_Unjoined, Joined, Right_Unjoined)`. *Note: Etlpipe always performs a full outer join internally to provide all three output anchors, mirroring a visual ETL tool's Join behavior.*
  *Usage*: `L, J, R = Join.join(df1, df2, on="ID")`
- **`Join.join_multiple(*dfs, on: str)`**: Joins 3+ DataFrames on a common key.
  *Usage*: `df = Join.join_multiple(df1, df2, df3, on="ID")`
- **`Join.union(*dfs, by: str)`**: Stacks DataFrames vertically.
  *Usage*: `df = Join.union(df2023, df2024, by="name")`
- **`Join.find_replace(df, lookup_df, find_col: str, replace_col: str, append: bool)`**: VLOOKUP-style replacement.
  *Usage*: `df = Join.find_replace(df, dict_df, "RegionCode", "RegionName", append=True)`
- **`Join.append_fields(df, append_df)`**: Cross/Cartesian join appending all rows.
  *Usage*: `df = Join.append_fields(sales_df, constants_df)`
- **`Join.fuzzy_match(left, right, left_on: str, right_on: str, threshold: float)`**: Approximate string matching.
  *Usage*: `df = Join.fuzzy_match(left, right, "CompanyName", "Name", threshold=0.85)`
- **`Join.make_group(df, left_key: str, right_key: str)`**: Groups relationship keys.
  *Usage*: `df = Join.make_group(df, "PersonA", "PersonB")`

### 📊 Transform Palette

- **`Transform.summarize(df, group_by: list, aggregations: dict)`**: GroupBy with named aggregations.
  *Usage*: `df = Transform.summarize(df, ["Region"], {"Sales": ["sum", "mean"]})`
- **`Transform.transpose(df, key_columns: list, data_columns: list)`**: Wide-to-long (unpivot).
  *Usage*: `df = Transform.transpose(df, ["ID"], ["Q1", "Q2", "Q3"])`
- **`Transform.cross_tab(df, group_by: list, header_column: str, value_column: str, aggregation: str)`**: Long-to-wide (pivot).
  *Usage*: `df = Transform.cross_tab(df, ["ID"], "Quarter", "Sales", "sum")`
- **`Transform.running_total(df, column: str, group_by: list=None)`**: Cumulative sum.
  *Usage*: `df = Transform.running_total(df, "Sales", ["Region"])`
- **`Transform.count_records(df)`**: Outputs row count as a single-value DataFrame.
  *Usage*: `df = Transform.count_records(df)`
- **`Transform.arrange(df, columns: list)`**: Manually transposes/rearranges multiple columns.
  *Usage*: `df = Transform.arrange(df, ["Col1", "Col2"])`
- **`Transform.make_columns(df, columns: int)`**: Wraps sequential rows into columns.
  *Usage*: `df = Transform.make_columns(df, 3)`
- **`Transform.weighted_average(df, value_col: str, weight_col: str, group_by: list=None)`**: Calculates weighted average.
  *Usage*: `df = Transform.weighted_average(df, "Price", "Volume", ["Category"])`

### 📝 Parse Palette

- **`Parse.date_time(df, column: str, format: str)`**: Converts strings to DateTime.
  *Usage*: `df = Parse.date_time(df, "DateStr", "%Y-%m-%d")`
- **`Parse.regex_match(df, column: str, pattern: str)`**: Creates boolean flag if pattern is found.
  *Usage*: `df = Parse.regex_match(df, "Email", r"^\S+@\S+$")`
- **`Parse.regex_parse(df, column: str, pattern: str)`**: Extracts regex capture groups into columns.
  *Usage*: `df = Parse.regex_parse(df, "Email", r"(?P<User>[^@]+)@(?P<Domain>.+)")`
- **`Parse.regex_replace(df, column: str, pattern: str, replacement: str)`**: Replaces text via regex.
  *Usage*: `df = Parse.regex_replace(df, "Phone", r"\D", "")`
- **`Parse.regex_tokenize(df, column: str, pattern: str, split_to_rows: bool)`**: Splits string via regex delimiter.
  *Usage*: `df = Parse.regex_tokenize(df, "Tags", r",", split_to_rows=True)`
- **`Parse.text_to_columns(df, column: str, delimiter: str, num_columns: int)`**: Splits delimited text.
  *Usage*: `df = Parse.text_to_columns(df, "Address", ",", 3)`
- **`Parse.xml_parse(df, column: str)`**: Extracts XML nodes and flattens child tags.
  *Usage*: `df = Parse.xml_parse(df, "XMLPayload")`

### 🛠️ Developer Palette

- **`Developer.base64_encode(df, column: str)`**: Encodes strings to Base64.
  *Usage*: `df = Developer.base64_encode(df, "SecretString")`
- **`Developer.base64_decode(df, column: str)`**: Decodes Base64 to strings.
  *Usage*: `df = Developer.base64_decode(df, "EncodedString")`
- **`Developer.download(df, url_column: str)`**: Performs HTTP GET requests into a DataFrame.
  *Usage*: `df = Developer.download(df, "API_Endpoint")`
- **`Developer.column_info(df)`**: Returns a schema/metadata DataFrame.
  *Usage*: `schema_df = Developer.column_info(df)`
- **`Developer.dynamic_rename(df, mapping: dict)`**: Renames columns via a lookup mapping.
  *Usage*: `df = Developer.dynamic_rename(df, {"Old": "New"})`
- **`Developer.json_parse(df, column: str)`**: Flattens JSON string columns dynamically.
  *Usage*: `df = Developer.json_parse(df, "JSONPayload")`
- **`Developer.dynamic_select(df, data_type: str)`**: Subsets columns by type or regex.
  *Usage*: `df = Developer.dynamic_select(df, "numeric")`
- **`Developer.test(df, condition: callable, message: str)`**: Asserts condition; halts on failure.
  *Usage*: `Developer.test(df, lambda x: x["Sales"].min() >= 0, "Negative sales!")`
- **`Developer.test_equal(df1, df2)`**: Strictly validates if two DataFrames are identical.
  *Usage*: `Developer.test_equal(expected_df, actual_df)`

---

## Usage Scenarios

Etlpipe easily fits into real-world enterprise architectures.

### 1. Traditional ETL / ELT
Extract data from S3 (`InOut.input_data`), clean out nulls (`Preparation.data_cleansing`), join with dimensional data (`Join.join`), aggregate to a summary level (`Transform.summarize`), and load to a data warehouse (`InOut.output_data`).

### 2. Machine Learning Pipelines
Use Etlpipe as the data preparation layer for ML pipelines.
- Standardize features using `Preparation.formula`.
- Create holdout sets using `Preparation.create_samples`.
- Balance datasets using `Preparation.oversample_field`.

### 3. Financial Analytics & Reporting
Etlpipe is commonly used in finance to replicate complicated legacy spreadsheets or visual ETL workflows, providing strict `Developer.test` validations before outputting month-end financial reporting.

---

## Advanced Features

### Scalability and Distributed Execution
Because Etlpipe can switch to a `spark` backend dynamically, it scales infinitely. When the PySpark engine is active, Etlpipe utilizes native Spark SQL, Vectorized Pandas UDFs (Arrow), and lazy evaluation to optimize execution over massive datasets on a cluster.

### Fault Tolerance
By keeping operations completely stateless and pure, Etlpipe gracefully handles retry logic. If an Airflow task running a Etlpipe step fails due to transient network issues, the step can safely be rerun without causing data corruption or state duplication.

### Integration with Other Systems
- **Databases**: Database connectivity can be achieved by passing a `pandas.read_sql()` result to Etlpipe, or using Spark JDBC with the `spark` backend.
- **Orchestration**: Wrap YAML pipelines in bash operators, or Python API code in standard Python functions.
- **Secret Management**: Pass standard connection strings populated by AWS Secrets Manager or HashiCorp Vault.

---

## Best Practices

### Performance Tuning
- **Filter Early**: Use `Preparation.filter` as early as possible in your pipeline to reduce the working dataset size.
- **Select Necessary Columns**: Use `Preparation.select` immediately after `input_data` to drop unneeded columns and reduce memory overhead.
- **Choose the Right Engine**: Do not use the `spark` engine for small datasets (e.g., < 1M rows); the `pandas` engine will be significantly faster due to the lack of JVM overhead.

### Security and Compliance
- **Never Hardcode Credentials**: Do not pass raw passwords to `InOut.input_data()`. Use environment variables.
- **Validate Data Inputs**: Use `Developer.test` after loading data to assert that PII is masked or that revenue figures are strictly positive before processing.

### Maintainability
- Standardize around the YAML execution engine for non-technical analysts.
- Use explicit naming conventions for DataFrames (e.g., `df_sales_raw`, `df_sales_clean`).
- Keep individual pipeline YAML or Python scripts under 300 lines; orchestrate larger DAGs using external tools like Airflow or Prefect.

---

## Examples & Tutorials

### Example 1: Full Python API Pipeline
```python
import etlpipe
from etlpipe import InOut, Preparation, Join, Transform, Developer

def run_sales_pipeline():
    # 1. Load Data
    sales = InOut.input_data("sales.csv")
    customers = InOut.input_data("customers.csv")
    
    # 2. Cleanse and Prepare
    sales = Preparation.data_cleansing(sales, replace_nulls_with=0, strip_whitespace=True)
    sales = Preparation.formula(sales, "Profit", "Revenue - Cost")
    
    # 3. Join
    left_only, joined_data, right_only = Join.join(sales, customers, on="CustomerID")
    
    # 4. Aggregate
    summary = Transform.summarize(
        joined_data,
        group_by=["Region"],
        aggregations={"Profit": ["sum", "mean"]}
    )
    
    # 5. Test & Output
    Developer.test(summary, lambda df: df["Sum_Profit"].sum() > 0, "Warning: Total Profit <= 0!")
    InOut.output_data(summary, "sales_summary.parquet")

if __name__ == "__main__":
    run_sales_pipeline()
```

### Example 2: No-Code YAML Pipeline
Store this as `pipeline.yaml` and execute via `etlpipe run pipeline.yaml`.
```yaml
name: "Customer Analytics Pipeline"
backend: "pandas"
steps:
  - id: "load_customers"
    tool: "InOut.input_data"
    args:
      path: "customers.csv"
      
  - id: "filter_active"
    tool: "Preparation.filter"
    inputs:
      df: "load_customers"
    args:
      condition: "Status == 'Active'"
      
  - id: "save_active"
    tool: "InOut.output_data"
    inputs:
      df: "filter_active.0"  # Grabs the TRUE anchor
    args:
      path: "active_customers.csv"
```

---

## 🔄 Visual Workflow Converter (`etlpipe-convert`)

Etlpipe includes an automated CLI tool to parse `.yxmd` XML visual workflows and auto-generate Etlpipe YAML pipelines:

```bash
# Convert a .yxmd file into a Etlpipe YAML pipeline
etlpipe-convert my_workflow.yxmd -o my_pipeline.yaml

# Dry-run mode to preview converted YAML in stdout
etlpipe-convert my_workflow.yxmd --dry-run
```

Python API usage:
```python
from etlpipe.convert import YxmdConverter

converter = YxmdConverter("my_workflow.yxmd")
yaml_content = converter.to_yaml()
converter.save("my_pipeline.yaml")
```

---

## 🛡️ Data Governance & Quality (`etlpipe-governance`)

Etlpipe comes with enterprise-grade data quality, PII detection, masking, and schema contract tools built-in (also available as the standalone package `etlpipe-governance`).

### 1. PII Detection & Compliance Masking (`scan_pii` / `mask_pii`)
Detect Personally Identifiable Information across **20 pattern types** — 12 international patterns plus 8 banking-sector extensions (routing numbers, account numbers, SWIFT/BIC codes, masked PANs, UK sort codes, Australian BSB codes, EINs, and internal CIF identifiers). Covers GDPR, HIPAA, SOX, CCPA, and PCI-DSS.

```python
from etlpipe import scan_pii
from etlpipe_governance import mask_pii
from etlpipe_governance.pii import save_mapping
import os

# 1. Scan for PII
report = scan_pii(df)
print(report[["Column", "PII_Type", "Confidence"]])

# 2. Mask sensitive columns
safe_df = mask_pii(df, report, strategy="redact")                  # Replaces with "***REDACTED***"
hashed_df = mask_pii(df, report, strategy="hash")                  # Replaces with SHA-256 tokens
pseudo_df, mapping = mask_pii(df, report, strategy="pseudonymise") # Replaces with labels (e.g. EMAIL_1)

# 3. Store the pseudonymise mapping securely (AES-256-GCM encrypted)
save_mapping(mapping, "mappings/daily.enc", encrypt_key=os.environ["MAPPING_KEY"])
```

### 2. Schema Contracts with Value-Level Rules (`expect_schema` / `infer_schema`)
Enforce schema integrity with dtype checks, nullability, **and value-level constraints** — catch bad data before it propagates:

```python
from etlpipe import expect_schema, infer_schema

# Validate with value-level rules
expect_schema(new_df, {
    "columns": {
        "CustomerID": {"dtype": "int", "nullable": False, "unique": True},
        "Email": {"dtype": "str", "value_regex": r".+@.+\..+"},
        "Revenue": {"dtype": "float", "min_value": 0.0},
        "Status": {"dtype": "str", "allowed_values": ["active", "inactive", "pending"]},
    }
})
```

### 3. Volume & Freshness Checks
Guard against empty tables, truncated feeds, and stale data:

```python
from etlpipe_governance import expect_row_count, expect_freshness
from datetime import timedelta

expect_row_count(df, min_rows=1000, max_rows=5_000_000)
expect_freshness(df, column="updated_at", max_age=timedelta(hours=6))
```

### 4. YAML Schema-as-Code
Store schemas as version-controlled files alongside your pipelines:

```python
from etlpipe_governance import load_schema, save_schema

schema = load_schema("schemas/sales.yaml")  # or .json
expect_schema(df, schema)
```

### 5. Audit Suites, Trail & Reporting
Execute batch audits with volume/freshness checks, persist results, export HTML reports, and stream to your SIEM:

```python
from etlpipe_governance import ContractSuite, AuditTrail, export_report, profile
from etlpipe_governance.audit import SplunkHECForwarder
from datetime import timedelta
import os

# Profile column metrics
profile_df = profile(df)

# Configure SIEM forwarder (Splunk, Teams, S3 — all supported)
splunk = SplunkHECForwarder(
    url="https://splunk.bank.internal:8088/services/collector/event",
    token=os.environ["SPLUNK_HEC_TOKEN"],
)

# Execute batch audit suite with volume and freshness gates
trail = AuditTrail("./governance_logs", forwarders=[splunk])  # Streams to Splunk + local JSONL
suite = ContractSuite("ETL Pipeline Ingestion Audit")
suite.add_contract("raw_sales", raw_schema, strict=True)
suite.add_contract("cleaned_sales", cleaned_schema, strict=False)
suite.add_volume_check("raw_sales", min_rows=500)
suite.add_freshness_check("raw_sales", column="created_at", max_age=timedelta(days=1))

audit_report = suite.run(
    {"raw_sales": sales_df, "cleaned_sales": cleaned_df},
    audit_trail=trail,
    run_id="daily_2026-08-01",
)

# Export a self-contained HTML report
export_report(audit_report, "reports/audit.html")
print(audit_report[["Contract", "Status", "Violation_Count"]])
```

---

## 🏦 Bank & Enterprise Security (v2.2.0)

Etlpipe v2.2.0 ships a 9-component security overhaul qualifying it for deployment inside major financial institutions (JPMorgan, Bank of America, HSBC) and Big 4 firms. All controls are tested by `tests/test_security.py`.

### Secrets Management
Use `${ENV_VAR}` tokens in pipeline YAML — credentials are **never** stored in files:
```yaml
# pipeline.yaml
steps:
  - id: load_customers
    tool: InOut.input_data
    args:
      path: "${DATA_PATH}"
      connection_string: "${env:DB_CONN_STRING}"
```
```python
# Tokens resolved automatically at Pipeline.run() — raises SecretResolutionError if any are missing
Pipeline.run("pipeline.yaml")
```

### RBAC Pipeline Guard
Plug in your bank's IAM or LDAP service:
```python
from etlpipe._rbac import PipelineGuard, EnvRoleGuard
import os

# Option 1: Custom IAM callable (plug in Active Directory, Okta, etc.)
guard = PipelineGuard(role_checker=lambda pipeline, action: my_iam.check(pipeline, action))

# Option 2: Environment variable-based roles (works with Kubernetes service accounts)
guard = EnvRoleGuard(
    allowed_roles_env="ETLPIPE_ALLOWED_ROLES",  # e.g. "data_engineer,data_analyst"
    user_role_env="ETLPIPE_USER_ROLE",
)

Pipeline.run("pipeline.yaml", guard=guard)  # Raises AccessDeniedError if denied
```

### Data Lineage (BCBS 239 / OpenLineage)
Record per-step I/O for regulatory data lineage requirements:
```python
from etlpipe._lineage import LineageCollector

collector = LineageCollector(namespace="prod.data-engineering", job_prefix="bank")
Pipeline.run("pipeline.yaml", lineage_collector=collector)

# Push to Marquez or Apache Atlas
collector.emit_to_marquez("http://marquez.internal:5000")

# Or export as OpenLineage events for custom integration
events = collector.to_openlineage_events()
```

### HTTPS Enforcement
`Developer.download()` rejects HTTP by default — update all URLs to HTTPS:
```python
# This now raises InsecureURLError:
# df = Developer.download("http://api.example.com/data")  # ❌

# Use HTTPS:
df = Developer.download("https://api.example.com/data")  # ✅
```

### Encrypted PII Mapping Storage
Store pseudonymisation mappings encrypted at rest:
```python
from etlpipe_governance.pii import save_mapping, load_mapping
import os

pseudo_df, mapping = mask_pii(df, report, strategy="pseudonymise")

# Encrypt with AES-256-GCM (key from your bank's secret manager)
save_mapping(mapping, "mappings/2026-09-07.enc", encrypt_key=os.environ["MAPPING_KEY"])

# Restore later
mapping = load_mapping("mappings/2026-09-07.enc", encrypt_key=os.environ["MAPPING_KEY"])
```

See [`SECURITY.md`](SECURITY.md) for the full security policy and [ADR 004](doc/adr/004-bank-production-hardening.md) for architectural rationale.

---

## Troubleshooting & FAQ

**Q: I get a MemoryError when processing a large file locally.**
*A: Etlpipe automatically mitigates this by utilizing the `pyarrow` multi-threaded C++ engine for CSVs, which significantly reduces RAM footprint. If your data is so massive it still exceeds physical RAM despite PyArrow, you must switch to the `spark` backend on a distributed cluster.*

**Q: How do I handle missing Etlpipe tools?**
*A: Etlpipe covers all core data preparation tools. Tools related to reporting (Render, Charting) or physical pipeline infrastructure (Block Until Done) are deliberately excluded. If you need bespoke logic, use a standard Python script step.*

**Q: `Join.join` returns three DataFrames. Which one do I want?**
*A: By standard convention, a Join returns Left Unjoined (L), Joined (J), and Right Unjoined (R). Typically, you want the Joined DataFrame (the 2nd item in the tuple).*

**Debugging Tip:** Use `InOut.browse(df)` inside a Python script to print a rich metadata profile and a sample of your dataset midway through a pipeline to debug data shape issues.

---

## 🧪 Testing & Development

Etlpipe boasts an extensive test suite verifying 1:1 parity with visual ETL tools. 

```bash
# Clone the repository
git clone https://github.com/tonystark7cris/etlpipe.git
cd etlpipe

# Install development dependencies
pip install -e ".[dev]"

# Run the test suite with coverage
pytest tests/ -v --cov=etlpipe --cov-report=term-missing
```

## 🤝 Contributing

Contributions are heavily encouraged! Etlpipe is community-driven. If you find a missing edge-case, want to optimize a pandas operation, or want to add support for a new community marketplace tool, please open an issue or submit a pull request on GitHub!

## 📄 License

[MIT License](LICENSE) — see the [LICENSE](LICENSE) file for details.
