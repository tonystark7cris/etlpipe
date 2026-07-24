# etlpipe â€” Comprehensive User Guide

> **etlpipe** is the fastest path from proprietary visual ETL to open-source Python.
> It provides a 1:1 API mapping of visual ETL tool palettes to standard Python functions and declarative YAML pipelines â€” running on **Pandas** locally or **PySpark** at billion-record scale with a single config change.

---

## Table of Contents

1. [Overview & Purpose](#1-overview--purpose)
2. [Installation & Setup](#2-installation--setup)
3. [Core Concepts](#3-core-concepts)
4. [Engine Configuration](#4-engine-configuration)
5. [InOut Palette â€” Reading & Writing Data](#5-inout-palette--reading--writing-data)
6. [Preparation Palette â€” Cleaning & Transforming Rows](#6-preparation-palette--cleaning--transforming-rows)
7. [Join Palette â€” Blending DataFrames](#7-join-palette--blending-dataframes)
8. [Transform Palette â€” Aggregating & Reshaping](#8-transform-palette--aggregating--reshaping)
9. [Parse Palette â€” Text, Dates & Regex](#9-parse-palette--text-dates--regex)
10. [Developer Palette â€” Utilities & Quality Checks](#10-developer-palette--utilities--quality-checks)
11. [Pipeline â€” Declarative YAML Execution](#11-pipeline--declarative-yaml-execution)
12. [Enterprise Governance](#12-enterprise-governance)
13. [Scale & Performance Guide](#13-scale--performance-guide)
14. [End-to-End Examples](#14-end-to-end-examples)
15. [Troubleshooting & FAQ](#15-troubleshooting--faq)
16. [Roadmap & Contributing](#16-roadmap--contributing)

---

## 1. Overview & Purpose

### What is etlpipe?

etlpipe is a Python library that replicates every major **visual ETL tool palette** as clean, testable Python functions. Teams migrating from proprietary GUI ETL software (Alteryx, Dataiku, Informatica, SSIS) can adopt etlpipe's familiar vocabulary â€” `Preparation.filter()`, `Join.join()`, `Transform.summarize()` â€” and immediately produce correct, production-grade pipelines without deep Pandas expertise.

### Key Design Principles

| Principle | Detail |
|---|---|
| **Immutability** | Every function returns a **new** DataFrame. Originals are never mutated. |
| **Output Anchors** | Multi-output tools return tuples mirroring visual T/F, L/J/R anchors. |
| **Dual-Engine** | Same code runs on **Pandas** (local) or **PySpark** (distributed cluster). |
| **Security-first** | Formula evaluation uses `df.eval()` only â€” no `eval()`/`exec()`. XML uses `defusedxml`. |
| **Static API** | All palette methods are `@staticmethod` â€” no instance state, fully thread-safe. |

### Value Proposition

- **Automated Workflow Conversion**: `etlpipe-convert` translates `.yxmd` files automatically into etlpipe YAML.
- **Escape Vendor Lock-In**: Run pipelines anywhere Python runs â€” locally, Airflow, AWS Lambda, Databricks, Kubernetes.
- **Enterprise Governance Built-in**: PII scanning, schema contracts, and pipeline event hooks ship out of the box.

---

## 2. Installation & Setup

### Requirements

- Python 3.9+
- pandas >= 1.5

### Standard Installation (Pandas engine)

```bash
pip install etlpipe
```

### Big-Data Installation (Pandas + PySpark engine)

```bash
pip install "etlpipe[spark]"
```

### Cloud Storage Support (s3://, gs://, abfs://)

```bash
pip install "etlpipe[cloud]"   # installs fsspec + storage adapters
```

### Development Installation

```bash
git clone https://github.com/your-org/etlpipe
pip install -e ".[dev]"
pytest tests/
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir etlpipe
COPY . /app
CMD ["python", "pipeline.py"]
```

### Databricks / Cloud Spark

Install `etlpipe[spark]` as a cluster library. etlpipe automatically detects the active `SparkSession` via `SparkSession.builder.getOrCreate()` â€” no additional configuration needed.

---

## 3. Core Concepts

### The Six Tool Palettes

| Palette | Purpose |
|---|---|
| **InOut** | Reading files, writing files, inline data creation |
| **Preparation** | Row-level cleaning, filtering, sorting, generating, sampling |
| **Join** | Merging, stacking, fuzzy matching, cross-joining DataFrames |
| **Transform** | Aggregating, pivoting, reshaping, running totals |
| **Parse** | Date parsing, regex extraction, XML/JSON parsing, text splitting |
| **Developer** | Assertions, schema inspection, encoding, HTTP download |

### Immutability

Every etlpipe function returns a **new** DataFrame. The original is never modified:

```python
clean = Preparation.data_cleansing(raw_df, strip_whitespace=True)
# raw_df is unchanged
assert "Name" in raw_df.columns  # True
```

### Output Anchors (Tuples)

Visual ETL tools have named output anchors. etlpipe mirrors this with tuples:

```python
# Filter -> T (True) and F (False) anchors
high_value, low_value = Preparation.filter(df, "Revenue > 1000")

# Join -> L (Left Unjoined), J (Joined), R (Right Unjoined) anchors
left_only, joined, right_only = Join.join(orders, customers, on="CustomerID")

# Unique -> U (Unique) and D (Duplicate) anchors
unique_records, duplicates = Preparation.unique(df, "Email")

# Create Samples -> Estimation, Validation, Holdout
train, val, test = Preparation.create_samples(df, 0.7, 0.2, 0.1)
```

---

## 4. Engine Configuration

### Switching Backends

```python
import etlpipe

# Default â€” Pandas (single machine)
etlpipe.set_backend("pandas")

# Distributed â€” PySpark
etlpipe.set_backend("spark")

# Check current backend
print(etlpipe.get_backend())  # "pandas"
```

### Advanced Spark Engine Tuning

For production billion-record workloads, configure the engine directly:

```python
from pyspark.sql import SparkSession
from etlpipe import set_engine
from etlpipe.engines.spark_engine import SparkEngine

spark = SparkSession.builder \
    .appName("etlpipeProd") \
    .config("spark.sql.shuffle.partitions", "2000") \
    .config("spark.checkpoint.dir", "s3://your-bucket/checkpoints") \
    .getOrCreate()

set_engine(SparkEngine(
    spark=spark,
    broadcast_threshold=50 * 1024 * 1024,   # 50 MB â€” auto-broadcast small tables
    max_collect_bytes=500 * 1024 * 1024,     # 500 MB â€” driver collect safety limit
    checkpoint_interval=5,                    # Auto-checkpoint every 5 pipeline steps
))
```

### Engine Scale Guide

| Data Size | Recommended Engine | Notes |
|---|---|---|
| < 10M rows | **Pandas** | Fast, no JVM overhead |
| 10M â€“ 100M rows | **Pandas + pyarrow** | `pip install pyarrow` for Arrow-accelerated CSV reads |
| 100M â€“ 1B rows | **Spark** | Requires PySpark cluster |
| 1B+ rows | **Spark** | Use parquet format; enable checkpointing |

---

## 5. InOut Palette â€” Reading & Writing Data

### `InOut.input_data(path, **kwargs)`

Read data from a file into a DataFrame. Format is auto-detected from the file extension. Any additional keyword arguments are forwarded to the underlying pandas reader.

**Supported formats:**

| Extension | Format | Notes |
|---|---|---|
| `.csv` | CSV | Uses PyArrow engine automatically if installed |
| `.tsv` | Tab-separated | `sep="\t"` applied automatically |
| `.xlsx`, `.xls` | Excel | Pass `sheet_name=` to select sheet |
| `.json` | JSON | |
| `.parquet` | Parquet | Recommended for large datasets |
| `.feather` | Feather | Fastest local format |
| `.html` | HTML table | Returns first table by default |
| `.sas7bdat`, `.xpt` | SAS | |
| `.dta` | Stata | |
| `.sav` | SPSS | |
| `.pkl`, `.pickle` | Pickle | Deprecated â€” security risk (CWE-502) |

**Cloud paths** (`s3://`, `gs://`, `abfs://`) require `pip install "etlpipe[cloud]"`.

```python
from etlpipe import InOut

# Local file â€” format auto-detected
df = InOut.input_data("sales.csv")

# Excel with specific sheet
df = InOut.input_data("report.xlsx", sheet_name="Q1")

# Cloud storage (requires etlpipe[cloud])
df = InOut.input_data("s3://my-bucket/data/customers.parquet")

# Pass extra pandas kwargs
df = InOut.input_data("data.csv", nrows=10000, dtype={"ID": str})
```

> **Spark engine note:** Supports `.csv`, `.tsv`, `.json`, `.parquet`, `.orc`. Excel and statistical formats require conversion to Parquet first.

---

### `InOut.output_data(df, path, **kwargs)`

Write a DataFrame to a file. Format auto-detected from extension. Parent directories are created automatically.

**Supported write formats:** `.csv`, `.tsv`, `.xlsx`, `.xls`, `.json`, `.parquet`, `.feather`, `.html`, `.dta`, `.pkl`/`.pickle` (deprecated).

```python
# CSV (index excluded by default)
InOut.output_data(df, "output.csv")

# Parquet â€” best for large data
InOut.output_data(df, "output.parquet")

# Excel with no index
InOut.output_data(df, "report.xlsx", index=False)

# JSON
InOut.output_data(df, "data.json")
```

---

### `InOut.text_input(data, columns=None)`

Create a DataFrame from inline Python data. Accepts three formats:

```python
# Column-oriented dict
df = InOut.text_input({"Name": ["Alice", "Bob"], "Age": [30, 25]})

# List of row dicts (records format)
df = InOut.text_input([{"id": 1, "val": "A"}, {"id": 2, "val": "B"}])

# List of lists â€” requires columns parameter
df = InOut.text_input([[1, "Alice"], [2, "Bob"]], columns=["ID", "Name"])
```

---

### `InOut.browse(df, n=10)`

Print a rich profile of a DataFrame to stdout and return it **unchanged**. Use mid-pipeline for debugging without breaking the chain:

```python
df = InOut.browse(df)  # prints stats, then continues pipeline
# Prints: shape, column types, null counts, descriptive statistics, first n rows
```

---

### `InOut.directory(path, pattern="*")`

List all files in a directory matching a glob pattern. Returns a DataFrame with one row per file.

```python
files_df = InOut.directory("./data", "*.csv")
# Columns: FullPath, Directory, FileName, ShortFileName,
#          CreationTime, LastWriteTime, LastAccessTime, Size
```

---

### `InOut.date_time_now()`

Return the current timestamp as a single-row DataFrame with column `DateTime`.

```python
now_df = InOut.date_time_now()
```

> **Spark engine:** Uses `F.current_timestamp()` â€” cluster-synchronized across all executors, not driver-only `datetime.now()`.

---

## 6. Preparation Palette â€” Cleaning & Transforming Rows

### `Preparation.filter(df, condition=None, *, column=None, operator=None, value=None)`

Split a DataFrame into rows that match and rows that do not. Returns `(true_df, false_df)`.

**Mode 1 â€” Custom Filter** (string expression or callable):

```python
# String expression â€” uses df.eval(), safe (no arbitrary code execution)
high, low = Preparation.filter(df, "Revenue > 1000")

# Multi-condition
valid, invalid = Preparation.filter(df, "Age >= 18 and Status == 'Active'")

# Callable (lambda or function)
boston, other = Preparation.filter(df, lambda d: d["City"] == "Boston")
```

**Mode 2 â€” Basic Filter** (column + operator + value):

All supported operators:

| Operator | Aliases | Description |
|---|---|---|
| `==` | `=`, `equals` | Exact equality |
| `!=` | `does not equal` | Inequality |
| `>` | | Greater than |
| `>=` | | Greater than or equal |
| `<` | | Less than |
| `<=` | | Less than or equal |
| `is null` | | Value is NaN/None |
| `is not null` | | Value is not NaN/None |
| `is empty` | | NaN/None **or** empty string `""` |
| `is not empty` | | Not NaN/None and not `""` |
| `contains` | | Substring match (case-sensitive) |
| `does not contain` | | Substring non-match |
| `is true` | | Boolean column equals `True` (vectorized, NaN-safe) |
| `is false` | | Boolean column equals `False` (vectorized, NaN-safe) |

```python
# Equality
active, inactive = Preparation.filter(df, column="Status", operator="==", value="Active")

# Null handling
nulls, not_nulls = Preparation.filter(df, column="Email", operator="is null")

# Empty (null OR empty string)
empty, non_empty = Preparation.filter(df, column="Name", operator="is empty")

# Substring
has_li, no_li = Preparation.filter(df, column="Name", operator="contains", value="li")

# Boolean columns â€” ALWAYS use operator mode for bool, never string eval
flagged, _ = Preparation.filter(df, column="IsActive", operator="is true")
```

---

### `Preparation.formula(df, column, expression)`

Create or update a column using a string expression or callable.

```python
# String expression â€” uses df.eval() (safe, no arbitrary execution)
df = Preparation.formula(df, "Profit", "Revenue - Cost")

# Column names with spaces are auto-backticked
df = Preparation.formula(df, "IsAlice", "Customer Name == 'Alice'")

# Callable lambda â€” for complex Python logic not expressible in df.eval()
df = Preparation.formula(df, "UpperName", lambda d: d["Name"].str.upper())

# Complex conditional logic
df = Preparation.formula(df, "Category",
    lambda d: d["Score"].apply(lambda s: "High" if s >= 80 else ("Mid" if s >= 50 else "Low")))
```

> **Security:** String expressions use `df.eval()` only. Calls like `print()`, `len()`, or custom functions raise `ValueError: Could not safely evaluate formula`. Use a lambda for complex logic.

---

### `Preparation.select(df, columns=None, renames=None, dtypes=None)`

Select, rename, and retype columns in one step. Operations are applied in order: select, then rename, then cast.

| Parameter | Type | Description |
|---|---|---|
| `columns` | `list[str]` or `None` | Columns to keep (in specified order). `None` keeps all. |
| `renames` | `dict[str, str]` or `None` | `{old_name: new_name}` mapping. |
| `dtypes` | `dict[str, str or type]` or `None` | `{column: dtype}` type casting applied after rename. |

```python
# Select and reorder columns only
df = Preparation.select(df, columns=["Name", "Age", "City"])

# Rename columns only
df = Preparation.select(df, renames={"CustomerName": "Name", "DOB": "DateOfBirth"})

# Cast types only
df = Preparation.select(df, dtypes={"Age": "float64", "ID": str})

# All three at once
df = Preparation.select(df,
    columns=["Name", "Age", "Revenue"],
    renames={"Name": "FullName"},
    dtypes={"Revenue": "float64"})
```

---

### `Preparation.data_cleansing(df, columns=None, *, remove_null_rows=False, replace_nulls_with=None, strip_whitespace=True, remove_letters=False, remove_numbers=False, remove_punctuation=False, modify_case=None)`

Clean string columns. When `columns=None`, all object/string columns are automatically processed.

| Parameter | Default | Description |
|---|---|---|
| `columns` | `None` | Columns to clean. `None` = all string columns. |
| `remove_null_rows` | `False` | Drop rows where any selected column is null. |
| `replace_nulls_with` | `None` | Fill null values before string operations. |
| `strip_whitespace` | `True` | Remove leading/trailing whitespace. |
| `remove_letters` | `False` | Strip all A-Z characters. |
| `remove_numbers` | `False` | Strip all digit characters. |
| `remove_punctuation` | `False` | Strip all punctuation (`[^\w\s]`). |
| `modify_case` | `None` | `"lower"`, `"upper"`, or `"title"`. |

```python
# Strip whitespace from all string columns (default behavior)
df = Preparation.data_cleansing(df)

# Specific columns only
df = Preparation.data_cleansing(df, columns=["Name", "City"])

# Fill nulls and standardize case
df = Preparation.data_cleansing(df, replace_nulls_with="Unknown", modify_case="title")

# Remove punctuation from text column
df = Preparation.data_cleansing(df, columns=["Notes"], remove_punctuation=True)

# Drop rows where critical columns are null
df = Preparation.data_cleansing(df, columns=["Name", "Email"], remove_null_rows=True)
```

> **NaN-safety:** Original null values are preserved after string operations. etlpipe explicitly prevents `.astype(str)` from converting NaN to the string `"nan"`.

---

### `Preparation.sort(df, columns, ascending=True)`

Sort a DataFrame by one or more columns.

```python
# Single column ascending (default)
df = Preparation.sort(df, "Age")

# Single column descending
df = Preparation.sort(df, "Revenue", ascending=False)

# Multi-column with mixed directions
df = Preparation.sort(df, ["Region", "Revenue"], ascending=[True, False])
```

---

### `Preparation.unique(df, columns, ignore_case=False)`

Split into unique and duplicate rows. Returns `(unique_df, duplicate_df)`. The **first occurrence** of each key goes to `unique_df`; subsequent duplicates go to `duplicate_df`.

```python
# Single column
unique, dups = Preparation.unique(df, "CustomerID")

# Multi-column key
unique, dups = Preparation.unique(df, ["FirstName", "LastName"])

# Case-insensitive (treats "Alice" and "alice" as duplicates)
unique, dups = Preparation.unique(df, "Email", ignore_case=True)
```

---

### `Preparation.sample(df, n=None, pct=None, random=False, position="first", random_state=None)`

Extract a subset of rows. Specify either `n` or `pct`, not both.

| Parameter | Description |
|---|---|
| `n` | Exact number of rows to extract. |
| `pct` | Fraction of rows (0.0 to 1.0). |
| `random` | If `True` with `n`, sample randomly. |
| `position` | `"first"` (head) or `"last"` (tail). Ignored when `random=True`. |
| `random_state` | Integer seed for reproducible random sampling. |

```python
# First 100 rows
df = Preparation.sample(df, n=100)

# Last 50 rows
df = Preparation.sample(df, n=50, position="last")

# Random 10%
df = Preparation.sample(df, pct=0.10, random=True, random_state=42)

# Random 500 rows (reproducible)
df = Preparation.sample(df, n=500, random=True, random_state=0)
```

---

### `Preparation.record_id(df, column_name="RecordID", start=1)`

Prepend an auto-incrementing integer ID column to a DataFrame.

```python
df = Preparation.record_id(df)                         # Adds "RecordID" starting at 1
df = Preparation.record_id(df, "RowNum", start=1000)   # Custom name and start value
```

> **Spark engine:** IDs are unique and monotonically increasing but not strictly sequential â€” avoids a catastrophic full cluster sort. If you need `1, 2, 3, ...` globally, use the Pandas engine.

---

### `Preparation.generate_rows(count, expression=None, columns=None)`

Generate rows programmatically. When no `expression` is given, returns a DataFrame with column `RowNum` (values 0 to count-1).

```python
# Simple sequential counter
df = Preparation.generate_rows(10)  # RowNum: 0, 1, 2, ..., 9

# Custom expression returning a dict per row index
df = Preparation.generate_rows(5, lambda i: {"x": i, "y": i ** 2})

# With explicit column ordering
df = Preparation.generate_rows(3, lambda i: {"y": i, "x": i}, columns=["x", "y"])
```

---

### `Preparation.auto_field(df)`

Automatically optimize column data types to reduce memory footprint:

- **Integers:** Downcasts `int64` to the smallest fitting type (`int8`, `int16`, `int32`).
- **Floats:** Downcasts `float64` to `float32` where possible.
- **Strings:** Converts low-cardinality object columns (< 50% unique values) to `category` type.

```python
df = Preparation.auto_field(df)
# Can reduce memory footprint by 50â€“80% on typical datasets
```

> **Spark engine:** Collects all LongType column min/max stats in **one Spark job** (not one job per column) â€” safe to call on wide DataFrames with many integer columns.

---

### `Preparation.multi_field_formula(df, columns, expression)`

Apply the same transformation to multiple columns at once.

```python
# Double all quarterly sales columns
df = Preparation.multi_field_formula(df, ["Q1", "Q2", "Q3", "Q4"], lambda s: s * 2)

# Uppercase multiple string columns
df = Preparation.multi_field_formula(df, ["City", "State"], lambda s: s.str.upper())
```

---

### `Preparation.multi_row_formula(df, column, expression, rows_back=1, group_by=None)`

Apply a formula that references values from previous or future rows.

| Parameter | Description |
|---|---|
| `column` | The column to compute and overwrite. |
| `expression` | Callable `f(current_series, shifted_series) -> series`. |
| `rows_back` | Positive = look back N rows; negative = look forward N rows. |
| `group_by` | Column(s) to partition the shift (resets at each group boundary). |

```python
# Row-over-row delta (first row = NaN â€” no previous value)
df = Preparation.multi_row_formula(df, "Delta",
    lambda cur, prev: cur - prev, rows_back=1)

# Grouped delta (resets per region)
df = Preparation.multi_row_formula(df, "Delta",
    lambda cur, prev: cur - prev, rows_back=1, group_by="Region")

# Percentage change
df = Preparation.multi_row_formula(df, "PctChange",
    lambda cur, prev: (cur - prev) / prev * 100, rows_back=1)
```

---

### `Preparation.tile(df, column, n_tiles, method="equal_records", output_column="Tile")`

Assign rows to tile/quantile groups numbered 1 to `n_tiles`.

| `method` | Description |
|---|---|
| `"equal_records"` | Each tile has approximately equal row count (quantile-based). Uses `NTILE` in Spark. |
| `"equal_range"` | Each tile covers an equal value range (equal-width bins). |

```python
# Split into 4 quartiles by sales (equal rows per group)
df = Preparation.tile(df, "Sales", 4)
# Adds column "Tile" with values 1, 2, 3, or 4

# Equal-width age bands
df = Preparation.tile(df, "Age", 5, method="equal_range", output_column="AgeBand")
```

---

### `Preparation.imputation(df, columns, method="mean", replacement_value=None, add_indicator=True)`

Fill missing values with computed or fixed replacements. When `add_indicator=True` (default), a boolean column `{col}_WasImputed` is added to track which values were filled.

| `method` | Description |
|---|---|
| `"mean"` | Column mean (numeric only) |
| `"median"` | Column median |
| `"mode"` | Most frequent value |
| `"value"` | Fixed value â€” requires `replacement_value` parameter |

```python
# Mean imputation with indicator flag
df = Preparation.imputation(df, "Age", method="mean")
# Adds: Age (values filled), Age_WasImputed (True where filled)

# Multiple columns at once
df = Preparation.imputation(df, ["Age", "Salary"], method="median")

# Fixed value
df = Preparation.imputation(df, "Score", method="value", replacement_value=0)

# Without indicator column
df = Preparation.imputation(df, "Revenue", method="mean", add_indicator=False)
```

---

### `Preparation.create_samples(df, estimation_pct, validation_pct, holdout_pct, random_state=None)`

Split a DataFrame into three non-overlapping ML samples. The three percentages **must sum to exactly 1.0**.

```python
# 70/20/10 ML split (reproducible)
train, val, test = Preparation.create_samples(df, 0.70, 0.20, 0.10, random_state=42)

# 50/30/20 split
est, val, hold = Preparation.create_samples(df, 0.50, 0.30, 0.20)
```

---

### `Preparation.date_filter(df, column, start_date=None, end_date=None)`

Filter a DataFrame by date range. Both bounds are **inclusive**. Returns `(true_df, false_df)`.

```python
# Closed date range
in_range, out = Preparation.date_filter(df, "TransactionDate",
    start_date="2023-01-01", end_date="2023-12-31")

# Open-ended (only start date)
recent, older = Preparation.date_filter(df, "Date", start_date="2024-01-01")

# pandas Timestamp is also accepted
import pandas as pd
t, f = Preparation.date_filter(df, "Date", start_date=pd.Timestamp("2023-06-01"))
```

---

### `Preparation.oversample_field(df, column, value, target_pct=0.5, random_state=None)`

Balance a class-imbalanced dataset by oversampling a minority class **with replacement**.

```python
# Balance "Churn=Yes" to 50% of the output
df = Preparation.oversample_field(df, "Churn", "Yes", target_pct=0.5, random_state=42)

# Balance fraud flag to 30%
df = Preparation.oversample_field(df, "IsFraud", True, target_pct=0.30)
```

> `target_pct` must be strictly between 0.0 and 1.0. Raises `ValueError` otherwise.

---

### `Preparation.rank(df, column, group_by=None, ascending=False, method="min", output_column="Rank")`

Add a rank column. By default, the highest value receives rank 1 (`ascending=False`).

| `method` | Description |
|---|---|
| `"min"` | Equal values share the lowest rank (standard competition ranking) |
| `"dense"` | Like `"min"` but no rank gaps after ties |
| `"first"` | Ties broken by order of appearance in the data |
| `"average"` | Equal values share the average of their ranks |
| `"max"` | Equal values share the highest rank |

```python
# Global rank by revenue (highest = rank 1)
df = Preparation.rank(df, "Revenue")

# Rank within each region (partitioned ranking)
df = Preparation.rank(df, "Revenue", group_by="Region")

# Ascending rank (lowest value = rank 1)
df = Preparation.rank(df, "Cost", ascending=True)

# Dense rank with custom output column
df = Preparation.rank(df, "Score", method="dense", output_column="DenseRank")

# Multi-column group-by
df = Preparation.rank(df, "Sales", group_by=["Region", "Year"])
```

---

## 7. Join Palette â€” Blending DataFrames

### `Join.join(left, right, on=None, left_on=None, right_on=None, suffixes=("_left", "_right"))`

Merge two DataFrames. Returns `(left_unjoined, joined, right_unjoined)` â€” equivalent to **L**, **J**, **R** visual output anchors.

The implementation performs an outer merge with an indicator, then slices the three result sets. The Spark engine persists both inputs and auto-broadcasts small tables.

```python
# Same key name in both DataFrames
L, J, R = Join.join(orders, customers, on="CustomerID")

# Different key names in each DataFrame
L, J, R = Join.join(orders, customers,
                     left_on="CustID", right_on="CustomerID")

# Multi-column key
L, J, R = Join.join(sales, targets, on=["Region", "Year"])

# Custom suffixes for overlapping non-key columns
L, J, R = Join.join(df1, df2, on="ID", suffixes=("_actual", "_forecast"))

# Most common usage â€” just the matched result
_, enriched, _ = Join.join(transactions, product_lookup, on="ProductCode")
```

---

### `Join.join_multiple(*dfs, on=None, join_type="outer")`

Join three or more DataFrames on a shared key in a single call.

```python
# Outer join (keeps all rows from all DataFrames)
combined = Join.join_multiple(df1, df2, df3, on="ID")

# Inner join (only rows with matches in all DataFrames)
inner = Join.join_multiple(df1, df2, df3, on="ID", join_type="inner")
```

---

### `Join.union(*dfs, by="name")`

Stack DataFrames vertically (equivalent to UNION ALL in SQL).

| `by` | Behaviour |
|---|---|
| `"name"` (default) | Aligns by column name. Missing columns filled with NaN. |
| `"position"` | Aligns by ordinal position. Column names taken from first DataFrame. |

```python
# Stack monthly files (aligned by column name)
all_months = Join.union(jan_df, feb_df, mar_df)

# Stack files with same column count but different names
aligned = Join.union(df1, df2, by="position")
```

---

### `Join.find_replace(df, find_df, find_col, replace_col, target_col=None, mode="entire", append=False)`

VLOOKUP/dictionary-style replacement using a separate lookup DataFrame.

| Parameter | Description |
|---|---|
| `find_df` | Lookup DataFrame containing find/replace pairs. |
| `find_col` | Column in `find_df` with values to search for. |
| `replace_col` | Column in `find_df` with replacement values. |
| `target_col` | Column in `df` to search against. Defaults to `find_col`. |
| `mode` | `"entire"` replaces whole cell value; `"partial"` replaces substring occurrences. |
| `append` | If `True`, adds a new column instead of replacing the original. |

```python
lookup = pd.DataFrame({"Code": ["CA", "NY", "TX"],
                        "Name": ["California", "New York", "Texas"]})

# Replace state codes with full names in-place
df = Join.find_replace(df, lookup, "Code", "Name", target_col="StateCode")

# Append full name as a new column
df = Join.find_replace(df, lookup, "Code", "Name",
                        target_col="State", append=True)

# Partial substring replacement
replacements = pd.DataFrame({"Find": ["Corp.", "Inc."],
                              "Replace": ["Corporation", "Incorporated"]})
df = Join.find_replace(df, replacements, "Find", "Replace",
                        target_col="CompanyName", mode="partial")
```

> **Spark engine:** `mode="entire"` uses a native broadcast join. `mode="partial"` or `append=True` falls back to `_safe_collect()` â€” protected by the driver memory guard.

---

### `Join.append_fields(left, right)`

Cartesian (cross) join â€” every row in `left` combined with every row in `right`.

```python
# 3 sizes Ã— 4 colors = 12 product variants
product_variants = Join.append_fields(sizes_df, colors_df)
```

> **Spark engine:** Small `right` tables are automatically broadcast for efficiency.

---

### `Join.fuzzy_match(left, right, left_on, right_on, threshold=0.6, score_column="MatchScore")`

Approximate string matching using `difflib.SequenceMatcher` ratio scoring. Returns all pairs with similarity >= `threshold`.

```python
# Match company names (70% similarity minimum)
matches = Join.fuzzy_match(df1, df2, "CompanyName", "Name", threshold=0.7)
# Output includes all left and right columns plus "MatchScore" (float 0.0â€“1.0)

# Stricter matching for person names
name_matches = Join.fuzzy_match(df1, df2, "CustomerName", "FullName",
                                 threshold=0.85, score_column="Similarity")
```

> **Scale note:** O(NÃ—M) comparison â€” avoid on tables > 100K rows without pre-filtering. Spark engine vectorizes per pair via `@pandas_udf`.

---

### `Join.make_group(df, key1, key2)`

Group relationship pairs into connected components (union-find graph traversal). Returns a DataFrame with columns `Group` and `Key`.

```python
pairs = pd.DataFrame({
    "PersonA": ["Alice", "Alice", "Dave"],
    "PersonB": ["Bob", "Charlie", "Eve"]
})
groups = Join.make_group(pairs, "PersonA", "PersonB")
# Group | Key
# Alice | Alice
# Alice | Bob
# Alice | Charlie
# Dave  | Dave
# Dave  | Eve
```

> **Scale note:** Graph traversal requires collecting all data to the driver. The Spark engine uses `_safe_collect()` which enforces a configurable byte limit to protect driver memory.

---

## 8. Transform Palette â€” Aggregating & Reshaping

### `Transform.summarize(df, group_by=None, aggregations=None)`

Group and aggregate a DataFrame. Output column names follow the pattern `{Action}_{Column}` (e.g., `Sum_Revenue`, `Count_ID`).

**All built-in aggregation names:**

| Name | Description |
|---|---|
| `"sum"` | Total |
| `"mean"` | Arithmetic mean |
| `"count"` | Non-null row count |
| `"count distinct"` | Count of unique non-null values |
| `"count null"` | Count of null values |
| `"count blank"` | Count of empty strings (after stripping whitespace) |
| `"count non blank"` | Count of non-empty, non-null strings |
| `"min"` | Minimum value |
| `"max"` | Maximum value |
| `"first"` | First value in group |
| `"last"` | Last value in group |
| `"std"` | Standard deviation |
| `"median"` | Median (exact for Pandas; approximate via `percentile_approx` for Spark) |
| `"concatenate"` | Comma-joined string of all values |
| `"concatenate distinct"` | Comma-joined string of unique values |
| `"longest"` | Longest string in group |
| `"shortest"` | Shortest string in group |
| `"mode"` | Most frequent value |

```python
# Single aggregation per column
summary = Transform.summarize(df, group_by="Region",
    aggregations={"Revenue": "sum", "Orders": "count"})
# Output columns: Region, Sum_Revenue, Count_Orders

# Multiple aggregations per column
summary = Transform.summarize(df, group_by=["Region", "Year"],
    aggregations={"Revenue": ["sum", "mean", "max"]})
# Output columns: Region, Year, Sum_Revenue, Mean_Revenue, Max_Revenue

# No group-by (aggregate entire DataFrame)
totals = Transform.summarize(df, aggregations={"Revenue": "sum", "ID": "count distinct"})

# String aggregations
summary = Transform.summarize(df, group_by="Category",
    aggregations={"Tags": "concatenate distinct", "Note": "longest"})
```

---

### `Transform.transpose(df, key_columns, data_columns=None, var_name="Name", value_name="Value")`

Unpivot (melt) from wide format to long format. Equivalent to SQL UNPIVOT or pandas `melt()`.

```python
# Each quarter becomes a separate row
long_df = Transform.transpose(df,
    key_columns="CustomerID",
    data_columns=["Q1", "Q2", "Q3", "Q4"],
    var_name="Quarter",
    value_name="Revenue")

# Unpivot all non-key columns automatically
long_df = Transform.transpose(df, key_columns=["ID", "Name"])

# Multi-column identifier
long_df = Transform.transpose(df,
    key_columns=["Region", "Year"],
    data_columns=["Jan", "Feb", "Mar"])
```

---

### `Transform.cross_tab(df, group_by, pivot_col, value_col, agg="sum")`

Pivot from long format to wide format. Equivalent to SQL PIVOT or pandas `pivot_table()`.

```python
# Each quarter becomes a column
wide_df = Transform.cross_tab(df,
    group_by="Region",
    pivot_col="Quarter",
    value_col="Revenue",
    agg="sum")
# Output columns: Region, Q1, Q2, Q3, Q4

# Multi-column row index
wide_df = Transform.cross_tab(df, ["Region", "Category"], "Year", "Sales", "mean")
```

---

### `Transform.running_total(df, column, group_by=None, output_column=None)`

Compute a cumulative sum. The output column name defaults to `RunningTotal_{column}`.

```python
# Global running total (entire DataFrame)
df = Transform.running_total(df, "Sales")

# Partitioned running total (resets at each group boundary)
df = Transform.running_total(df, "Sales", group_by="Region")

# Multi-column partition with custom output column name
df = Transform.running_total(df, "Revenue",
    group_by=["Region", "Year"],
    output_column="CumulativeRevenue")
```

---

### `Transform.count_records(df, output_col="Count")`

Return the total row count as a single-row, single-column DataFrame.

```python
count_df = Transform.count_records(df)
# Returns: DataFrame with column "Count" and one row, e.g. 1,250,000

# Custom column name
count_df = Transform.count_records(df, output_col="TotalRows")
```

---

### `Transform.arrange(df, key_columns=None, output_mapping=None)`

Manually rearrange multiple input columns into a smaller set of output columns. Useful for normalizing wide denormalized survey or report layouts. Each input row generates N output rows (one per mapping index).

```python
# Wide report with Q1/Q2/Q3 labels and values in separate columns
result = Transform.arrange(df,
    key_columns="ID",
    output_mapping={
        "Quarter": ["Q1_Label", "Q2_Label", "Q3_Label"],
        "Revenue": ["Q1_Revenue", "Q2_Revenue", "Q3_Revenue"],
    })
# Each input row produces 3 output rows
```

---

### `Transform.make_columns(df, num_columns)`

Wrap sequential rows into side-by-side column groups. Useful for multi-column report formatting.

```python
# 9 rows -> 3 groups of 3, placed side by side
wide = Transform.make_columns(df, 3)
# If original column is "Sales":
# Output has columns Sales_1, Sales_2, Sales_3 and only 3 rows
```

---

### `Transform.weighted_average(df, value_column, weight_column, group_by=None, output_column="WeightedAverage")`

Calculate a weighted average: `sum(value * weight) / sum(weight)`.

```python
# Global weighted average price by quantity
wa = Transform.weighted_average(df, "Price", "Quantity")

# Per-category weighted discount
wa = Transform.weighted_average(df, "Discount", "Revenue",
    group_by="Category",
    output_column="WeightedDiscount")
```

---

## 9. Parse Palette â€” Text, Dates & Regex

### `Parse.date_time(df, column, input_fmt=None, output_fmt=None)`

Convert or reformat date/time values. Uses standard Python `strftime` format codes.

```python
# Parse date string into datetime64 (infer format)
df = Parse.date_time(df, "DateStr")

# Parse with explicit format
df = Parse.date_time(df, "DateStr", input_fmt="%m/%d/%Y")

# Parse and reformat as string
df = Parse.date_time(df, "Date", input_fmt="%Y-%m-%d", output_fmt="%d/%m/%Y")
```

> **Spark engine:** Format codes are automatically transpiled from Python `strftime` (e.g., `%Y-%m-%d`) to Java `SimpleDateFormat` (e.g., `yyyy-MM-dd`). Use the same format strings on both engines â€” etlpipe handles the conversion.

---

### `Parse.regex_match(df, column, pattern, output_column="Match")`

Add a boolean column indicating whether each row matches a regex pattern.

```python
# Email validation â€” adds boolean column "Match"
df = Parse.regex_match(df, "Email", r"^[\w.]+@[\w.]+\.\w+$")

# Custom output column name
df = Parse.regex_match(df, "Phone", r"^\d{10}$", output_column="ValidPhone")

# Check for specific content
df = Parse.regex_match(df, "Address", r"\b\d{5}\b", output_column="HasZipCode")
```

---

### `Parse.regex_parse(df, column, pattern, output_cols=None)`

Extract regex capture groups into new columns. The number of output columns must match the number of capturing groups.

```python
# Two groups â€” auto-named Group_1, Group_2
df = Parse.regex_parse(df, "FullName", r"(\w+)\s+(\w+)")

# Named output columns
df = Parse.regex_parse(df, "FullName", r"(\w+)\s+(\w+)", output_cols=["First", "Last"])

# Extract from email address
df = Parse.regex_parse(df, "Email", r"([^@]+)@(.+)", output_cols=["User", "Domain"])

# Extract date components
df = Parse.regex_parse(df, "Date", r"(\d{4})-(\d{2})-(\d{2})",
                        output_cols=["Year", "Month", "Day"])
```

---

### `Parse.regex_replace(df, column, pattern, replacement)`

Replace regex pattern matches within a column. Supports backreferences.

```python
# Strip all non-numeric characters from phone numbers
df = Parse.regex_replace(df, "Phone", r"\D", "")

# Redact SSN-like patterns
df = Parse.regex_replace(df, "Notes", r"\d{3}-\d{2}-\d{4}", "***-**-****")

# Swap name format using backreferences: "Last, First" -> "First Last"
df = Parse.regex_replace(df, "Name", r"(\w+), (\w+)", r"\2 \1")

# Normalize whitespace
df = Parse.regex_replace(df, "Text", r"\s+", " ")
```

---

### `Parse.regex_tokenize(df, column, pattern, split_to="rows")`

Split a column's values by a regex delimiter.

| `split_to` | Description |
|---|---|
| `"rows"` | Each token becomes a separate row (explode). All other columns are duplicated per token. |
| `"columns"` | Each token becomes a separate new column (`Split_1`, `Split_2`, etc.). |

```python
# Expand comma-separated tags into one row per tag
df = Parse.regex_tokenize(df, "Tags", r",\s*", split_to="rows")

# Split product code "ABC-123-XYZ" into parts
df = Parse.regex_tokenize(df, "Code", r"-", split_to="columns")
# Adds: Code_Split_1 = "ABC", Code_Split_2 = "123", Code_Split_3 = "XYZ"
```

---

### `Parse.text_to_columns(df, column, delimiter, split_to="columns", num_columns=None)`

Split a column on a **literal** string delimiter (not regex).

```python
# Split "First,Last,City" into 3 columns
df = Parse.text_to_columns(df, "CSVField", ",", split_to="columns", num_columns=3)

# Split address on " | " into rows
df = Parse.text_to_columns(df, "Addresses", " | ", split_to="rows")

# Split tab-delimited field
df = Parse.text_to_columns(df, "TabField", "\t", split_to="columns")
```

---

### `Parse.xml_parse(df, column, xpath, output_column="ParsedXML", return_child_values=False, return_outer_xml=False)`

Extract data from XML string columns using XPath expressions. Uses `defusedxml` â€” protected against XXE injection attacks (CVE category).

| Parameter | Description |
|---|---|
| `xpath` | XPath expression to select a node (e.g. `.//OrderDate`). |
| `output_column` | Name for the extracted value column. |
| `return_child_values` | If `True`, flattens all child tags and attributes into separate columns instead of extracting node text. |
| `return_outer_xml` | If `True`, adds an additional column with the raw XML string of the matched node. |

```python
# Extract text content of a specific element
df = Parse.xml_parse(df, "XMLPayload", ".//OrderDate", "OrderDate")

# Flatten all children of <Customer> into separate columns
df = Parse.xml_parse(df, "XML", ".//Customer",
                     output_column="Customer", return_child_values=True)
# Adds: Customer_Name, Customer_Email, Customer_Address, etc.

# Get both text and raw XML
df = Parse.xml_parse(df, "XML", ".//Item",
                     return_child_values=True, return_outer_xml=True)
```

---

## 10. Developer Palette â€” Utilities & Quality Checks

### `Developer.test(df, condition_func, error_msg="Test condition failed")`

Assert a condition against a DataFrame. Raises `ValueError` if `condition_func(df)` returns `False`. Returns the DataFrame **unchanged** on success, enabling inline chaining with `.pipe()`.

```python
# Inline assertion
df = Developer.test(df, lambda d: d["Revenue"].sum() > 0, "Revenue total is zero!")

# Assert no nulls in critical column
df = Developer.test(df, lambda d: d["CustomerID"].isna().sum() == 0, "Null CustomerIDs!")

# Assert row count
df = Developer.test(df, lambda d: len(d) > 0, "Empty DataFrame!")

# Chain multiple tests using .pipe()
df = (df
    .pipe(lambda d: Developer.test(d, lambda x: len(x) > 0, "Empty!"))
    .pipe(lambda d: Developer.test(d, lambda x: x["Amount"].min() >= 0, "Negative amounts!")))
```

---

### `Developer.test_equal(df_left, df_right, **kwargs)`

Assert two DataFrames are identical. Wraps `pd.testing.assert_frame_equal`. Raises `AssertionError` if they differ. Any `**kwargs` are forwarded to `assert_frame_equal`.

```python
# Strict equality check (shape, dtypes, column names, values, index)
Developer.test_equal(expected_df, actual_df)

# Ignore column order
Developer.test_equal(expected_df, actual_df, check_like=True)

# Approximate numeric equality (useful for float comparisons)
Developer.test_equal(expected_df, actual_df, atol=1e-6, rtol=0)

# Ignore dtype differences
Developer.test_equal(expected_df, actual_df, check_dtype=False)
```

---

### `Developer.column_info(df)`

Return a schema/metadata DataFrame describing each column.

```python
schema = Developer.column_info(df)
# Returns a DataFrame with columns:
# Name | Type | Size | NonNullCount | NullCount | UniqueCount
print(schema)
```

---

### `Developer.dynamic_select(df, dtype_include=None, dtype_exclude=None, pattern=None)`

Select columns dynamically based on data type or column name regex pattern, without hardcoding column names.

```python
# Keep only numeric columns
df_num = Developer.dynamic_select(df, dtype_include="number")

# Keep only object (string) columns
df_str = Developer.dynamic_select(df, dtype_include="object")

# Exclude boolean columns
df = Developer.dynamic_select(df, dtype_exclude="bool")

# Columns whose names match a regex pattern
df_sales = Developer.dynamic_select(df, pattern=r"^Sales_")

# Combine: numeric columns ending with "_Amount"
df = Developer.dynamic_select(df, dtype_include="number", pattern=r"_Amount$")
```

---

### `Developer.dynamic_rename(df, rename_df, key_col="OldName", new_name_col="NewName", mode="mapping")`

Rename columns dynamically using a lookup DataFrame rather than hardcoded strings.

| `mode` | Description |
|---|---|
| `"mapping"` | Renames using the `key_col` â†’ `new_name_col` lookup. |
| `"prefix"` | Prepends a prefix to all columns (from a single-value `rename_df`). |
| `"suffix"` | Appends a suffix to all columns. |

```python
# Mapping mode (rename specific columns)
mapping = pd.DataFrame({"OldName": ["col_a", "col_b"],
                         "NewName": ["Column A", "Column B"]})
df = Developer.dynamic_rename(df, mapping)

# Prefix mode
prefix_df = pd.DataFrame({"Prefix": ["raw_"]})
df = Developer.dynamic_rename(df, prefix_df, mode="prefix")
# All columns get "raw_" prepended

# Suffix mode
suffix_df = pd.DataFrame({"Suffix": ["_v2"]})
df = Developer.dynamic_rename(df, suffix_df, mode="suffix")
```

---

### `Developer.json_parse(df, column, prefix=None)`

Expand a JSON string column into separate columns. The original JSON column is preserved.

```python
# Parse JSON payload â€” prefix defaults to column name
df = Developer.json_parse(df, "EventPayload")
# If EventPayload = '{"city": "NY", "score": 9}'
# Adds: EventPayload_city, EventPayload_score

# Custom prefix
df = Developer.json_parse(df, "Metadata", prefix="meta")
# Adds: meta_city, meta_score
```

---

### `Developer.base64_encode(df, column, output_column=None)`

Encode a string column to Base64. Output column defaults to `{column}_Base64`.

```python
df = Developer.base64_encode(df, "SecretKey")
# Adds column: SecretKey_Base64
```

---

### `Developer.base64_decode(df, column, output_column=None)`

Decode a Base64 string column back to plaintext. Output column defaults to `{column}_Decoded`.

```python
df = Developer.base64_decode(df, "SecretKey_Base64")
# Adds column: SecretKey_Base64_Decoded
```

---

### `Developer.download(url, params=None, output_column="DownloadData", max_retries=3, retry_delay=1.0)`

Fetch data from a URL with automatic retry and exponential backoff. Attempts JSON parsing first; falls back to raw text in a single-column DataFrame.

| Parameter | Default | Description |
|---|---|---|
| `url` | â€” | The URL to fetch. |
| `params` | `None` | Optional `dict` of query parameters. |
| `output_column` | `"DownloadData"` | Column name for raw text fallback. |
| `max_retries` | `3` | Maximum retry attempts for transient failures. |
| `retry_delay` | `1.0` | Base delay in seconds (exponential: delay Ã— 2^attempt). |

```python
# Simple GET
df = Developer.download("https://api.example.com/data")

# With query parameters
df = Developer.download("https://api.example.com/search",
                         params={"q": "etlpipe", "limit": 100})

# Aggressive retry for unreliable endpoints
df = Developer.download("https://api.example.com/data",
                         max_retries=5, retry_delay=2.0)
```

> Uses `urllib` from the Python standard library â€” no `requests` dependency required.

---

## 11. Pipeline â€” Declarative YAML Execution

### YAML Structure Reference

```yaml
name: "Pipeline Name"
backend: "pandas"        # optional: "pandas" (default) or "spark"
steps:
  - id: "unique_step_id"
    tool: "Palette.method_name"
    inputs:              # Reference outputs of earlier steps by their id
      df: "earlier_step_id"
    args:                # Method keyword arguments
      key: value
```

### Input Reference Syntax

Steps reference earlier step outputs by `step_id`. For tools that return tuples, append `.0`, `.1`, `.2`:

```yaml
# Filter returns (true_df, false_df):
df: "filter_step.0"    # True anchor (matching rows)
df: "filter_step.1"    # False anchor (non-matching rows)

# Join returns (left_unjoined, joined, right_unjoined):
df: "join_step.0"      # Left unjoined (L anchor)
df: "join_step.1"      # Joined result (J anchor) â€” most common
df: "join_step.2"      # Right unjoined (R anchor)

# Unique returns (unique_df, duplicate_df):
df: "unique_step.0"    # Unique records
df: "unique_step.1"    # Duplicate records

# Create Samples returns (train, val, test):
df: "samples_step.0"   # Estimation/Training
df: "samples_step.1"   # Validation
df: "samples_step.2"   # Holdout/Test
```

### Running a Pipeline

```bash
# Command-line
etlpipe run pipeline.yaml
```

```python
from etlpipe import Pipeline

# Basic execution
pipeline = Pipeline("pipeline.yaml")
pipeline.execute()

# Access per-step metrics after execution
for m in pipeline.metrics:
    print(f"{m['step_id']}: {m['duration_s']:.2f}s, {m.get('output_rows', 'N/A')} rows")
```

### Event Hooks for Alerting

```python
import requests
from etlpipe import Pipeline

SLACK_WEBHOOK = "https://hooks.slack.com/services/..."

def on_error(step_id, tool_name, error):
    requests.post(SLACK_WEBHOOK, json={
        "text": f"Pipeline step `{step_id}` ({tool_name}) failed: {error}"
    })

def on_complete(pipeline_name, metrics):
    total = sum(m["duration_s"] for m in metrics)
    requests.post(SLACK_WEBHOOK, json={
        "text": f"Pipeline `{pipeline_name}` completed in {total:.1f}s ({len(metrics)} steps)"
    })

pipeline = Pipeline(
    "pipeline.yaml",
    on_step_error=on_error,
    on_step_complete=lambda sid, tool, m: print(f"OK: {sid}"),
    on_pipeline_complete=on_complete,
)
pipeline.execute()
```

### Complete YAML Example

```yaml
name: "Customer Analytics Pipeline"
backend: "pandas"
steps:
  - id: "load_customers"
    tool: "InOut.input_data"
    args:
      path: "customers.csv"

  - id: "load_orders"
    tool: "InOut.input_data"
    args:
      path: "orders.csv"

  - id: "filter_active"
    tool: "Preparation.filter"
    inputs:
      df: "load_customers"
    args:
      condition: "Status == 'Active'"

  - id: "clean_customers"
    tool: "Preparation.data_cleansing"
    inputs:
      df: "filter_active.0"
    args:
      strip_whitespace: true
      modify_case: "title"

  - id: "join_data"
    tool: "Join.join"
    inputs:
      left: "clean_customers"
      right: "load_orders"
    args:
      on: "CustomerID"

  - id: "summarize"
    tool: "Transform.summarize"
    inputs:
      df: "join_data.1"
    args:
      group_by: "Region"
      aggregations:
        Revenue: ["sum", "mean"]
        CustomerID: "count distinct"

  - id: "save_output"
    tool: "InOut.output_data"
    inputs:
      df: "summarize"
    args:
      path: "output/regional_summary.parquet"
```

---

## 12. Enterprise Governance

### PII Detection

Automatically detect columns containing Personally Identifiable Information before data flows downstream:

```python
from etlpipe import InOut, scan_pii

df = InOut.input_data("customer_data.csv")
pii_report = scan_pii(df)
print(pii_report[["Column", "PII_Type", "Confidence"]])
#    Column      PII_Type Confidence
# 0  Email         email       high
# 1  Phone      phone_us     medium
# 2    SSN           ssn       high
```

**Supported PII pattern types:** email, phone (US/international), SSN, credit card, IP address, Aadhaar (India), IBAN, passport numbers, and more.

**Custom patterns:**

```python
custom = {
    "employee_id": {
        "value_regex": r"EMP-\d{6}",
        "name_regex": r"(?i)emp.*id",
        "description": "Internal Employee ID",
    }
}
report = scan_pii(df, patterns=custom)
```

---

### Data Contracts (Schema Validation)

Enforce expected schema to catch column drift, type changes, or unexpected nulls early:

```python
from etlpipe import expect_schema, infer_schema, InOut, SchemaViolationError

# Bootstrap: infer schema from reference data and save for version control
df = InOut.input_data("reference_data.csv")
schema = infer_schema(df)

# Enforce: validate new data against the saved contract
new_df = InOut.input_data("new_data.csv")
try:
    expect_schema(new_df, {
        "columns": {
            "CustomerID": {"dtype": "int", "nullable": False},
            "Name":       {"dtype": "str", "nullable": True},
            "Revenue":    {"dtype": "float", "nullable": False},
        }
    })
except SchemaViolationError as e:
    print(f"Schema violation: {e}")
    raise
```

**Inline in YAML pipelines:**

```yaml
steps:
  - id: "load_data"
    tool: "InOut.input_data"
    args:
      path: "data.csv"
    output_schema:
      columns:
        CustomerID: {dtype: "int", nullable: false}
        Revenue:    {dtype: "float", nullable: false}
        Name:       {dtype: "str", nullable: true}
```

---

### Data Lineage (OpenLineage Integration)

```python
from openlineage.client import OpenLineageClient
from etlpipe import Pipeline

client = OpenLineageClient(url="http://marquez:5000")

def emit_lineage(step_id, tool_name, metrics):
    client.emit(run_event=build_run_event(step_id, tool_name, metrics))

Pipeline("pipeline.yaml", on_step_complete=emit_lineage).execute()
```

### Recommended Data Catalog Integration

| Catalog | Integration Pattern |
|---|---|
| **Microsoft Purview** | Use Purview REST API in pipeline hooks to register datasets |
| **Atlan** | Use Atlan SDK in `on_step_complete` to push metadata |
| **DataHub** | Emit metadata change events via DataHub REST API |
| **Apache Atlas** | Use Atlas REST API for Hadoop/Spark-centric environments |

---

## 13. Scale & Performance Guide

### Engine Decision Matrix

| Data Size | Engine | Notes |
|---|---|---|
| < 10M rows | **Pandas** | Fast, no JVM overhead |
| 10M â€“ 100M rows | **Pandas + PyArrow** | `pip install pyarrow` for Arrow-accelerated CSV reads |
| 100M â€“ 1B rows | **Spark** | Parquet input; tune `spark.sql.shuffle.partitions` |
| 1B+ rows | **Spark** | Enable checkpointing; tune `broadcast_threshold` |

### Best Practices

**Filter and select columns early:**

```python
# Filter before joins â€” reduces data flowing into merge
active, _ = Preparation.filter(df, "Status == 'Active'")
df = Preparation.select(active, columns=["ID", "Revenue", "Region"])
_, joined, _ = Join.join(df, lookup, on="ID")
```

**Always prefer Parquet over CSV for large data:**

```python
InOut.output_data(df, "output.parquet")  # Columnar, compressed, 3-5x smaller and faster
```

**Use `auto_field` immediately after loading:**

```python
df = InOut.input_data("data.parquet")
df = Preparation.auto_field(df)  # Can reduce memory by 50â€“80%
```

**Spark shuffle partition tuning:**

```python
# Default is 200 â€” too low for large joins, too high for small data
spark.conf.set("spark.sql.shuffle.partitions", "2000")  # ~200MB per partition target
```

**SparkEngine direct configuration:**

```python
SparkEngine(
    spark=spark,
    broadcast_threshold=50 * 1024 * 1024,  # Auto-broadcast tables < 50 MB
    max_collect_bytes=500 * 1024 * 1024,    # Driver memory guard (default 500 MB)
    checkpoint_interval=5,                   # Truncate lineage DAG every 5 steps
)
```

---

## 14. End-to-End Examples

### Example 1: Sales Analytics Pipeline (Python API)

```python
from etlpipe import InOut, Preparation, Join, Transform, Developer

def run_sales_pipeline():
    # 1. Load
    sales = InOut.input_data("s3://bucket/sales.csv")
    customers = InOut.input_data("s3://bucket/customers.csv")

    # 2. Validate inputs
    sales = Developer.test(sales, lambda d: len(d) > 0, "Empty sales file!")

    # 3. Cleanse and enrich
    sales = Preparation.data_cleansing(sales, replace_nulls_with=0, strip_whitespace=True)
    sales = Preparation.formula(sales, "Profit", "Revenue - Cost")

    # 4. Filter valid records
    valid, invalid = Preparation.filter(sales, "Revenue > 0")

    # 5. Join with customer data
    _, joined, _ = Join.join(valid, customers, on="CustomerID")

    # 6. Aggregate by region
    summary = Transform.summarize(joined, group_by="Region",
        aggregations={"Profit": ["sum", "mean"], "CustomerID": "count distinct"})

    # 7. Validate and output
    Developer.test(summary, lambda d: d["Sum_Profit"].sum() > 0, "Total profit <= 0!")
    InOut.output_data(summary, "s3://bucket/sales_summary.parquet")
    InOut.output_data(invalid, "s3://bucket/audit/invalid_records.csv")

run_sales_pipeline()
```

---

### Example 2: ML Feature Engineering Pipeline

```python
from etlpipe import InOut, Preparation

def build_features():
    df = InOut.input_data("raw_data.parquet")
    df = Preparation.auto_field(df)  # Optimize memory first

    # Impute missing values
    df = Preparation.imputation(df, ["Age", "Income"], method="median")
    df = Preparation.imputation(df, "Category", method="mode")

    # Feature engineering
    df = Preparation.formula(df, "AgeIncome", "Age * Income")
    df = Preparation.formula(df, "IsHighIncome",
        lambda d: (d["Income"] > 100000).astype(int))

    # Tile age into 10 deciles
    df = Preparation.tile(df, "Age", 10, output_column="AgeTile")

    # Balance the dataset (oversample minority class to 50%)
    df = Preparation.oversample_field(df, "Churn", 1, target_pct=0.50, random_state=42)

    # Split for ML training
    train, val, test = Preparation.create_samples(df, 0.70, 0.20, 0.10, random_state=0)
    InOut.output_data(train, "data/train.parquet")
    InOut.output_data(val,   "data/val.parquet")
    InOut.output_data(test,  "data/test.parquet")

build_features()
```

---

### Example 3: Enterprise Spark Pipeline (Billions of Records)

```python
from pyspark.sql import SparkSession
from etlpipe import set_engine, InOut, Preparation, Join, Transform, Parse, Developer
from etlpipe.engines.spark_engine import SparkEngine

spark = SparkSession.builder \
    .appName("EnterpriseETL") \
    .config("spark.sql.shuffle.partitions", "2000") \
    .config("spark.checkpoint.dir", "s3://checkpoints/") \
    .getOrCreate()

set_engine(SparkEngine(spark=spark, broadcast_threshold=50_000_000))

# Load from data lake (Spark reads all partition files in parallel)
transactions = InOut.input_data("s3://datalake/transactions/*.parquet")
stores       = InOut.input_data("s3://datalake/dim_stores.parquet")
products     = InOut.input_data("s3://datalake/dim_products.parquet")

# Parse and enrich
transactions = Parse.date_time(transactions, "TxDate", input_fmt="%Y-%m-%d")
transactions = Developer.json_parse(transactions, "Metadata", prefix="meta")

# Filter â€” reduce data before expensive joins
valid_tx, invalid_tx = Preparation.filter(transactions,
    column="Amount", operator=">", value=0)

# Join dimensions (stores/products are small â€” auto-broadcast)
_, tx_with_stores, _ = Join.join(valid_tx, stores, on="StoreID")
_, enriched, _       = Join.join(tx_with_stores, products, on="ProductID")

# Aggregate
summary = Transform.summarize(enriched,
    group_by=["Region", "ProductCategory"],
    aggregations={"Amount": ["sum", "count"], "Margin": "mean"})

# Validate
Developer.test(summary,
    lambda d: d["Sum_Amount"].min() >= 0, "Negative aggregated amounts!")

# Output
InOut.output_data(summary,    "s3://output/summary.parquet")
InOut.output_data(invalid_tx, "s3://audit/invalid.parquet")
```

---

### Example 4: Text Processing & Data Quality Pipeline

```python
from etlpipe import InOut, Preparation, Parse, Developer

df = InOut.input_data("raw_contacts.csv")

# Flag invalid emails
df = Parse.regex_match(df, "Email", r"^[\w.]+@[\w.]+\.\w{2,}$",
                        output_column="ValidEmail")

# Extract first/last from "Last, First" format
df = Parse.regex_parse(df, "FullName", r"(\w+),\s*(\w+)",
                        output_cols=["LastName", "FirstName"])

# Standardize phone number (remove non-digits)
df = Parse.regex_replace(df, "Phone", r"\D", "")

# Expand comma-separated tags into individual rows
df = Parse.regex_tokenize(df, "Tags", r",\s*", split_to="rows")

# Normalize text
df = Preparation.data_cleansing(df,
    columns=["FirstName", "LastName"],
    strip_whitespace=True,
    modify_case="title")

# Quality score and rank
df = Preparation.formula(df, "Completeness",
    lambda d: d["ValidEmail"].astype(int) + d["Phone"].str.len().gt(9).astype(int))
df = Preparation.rank(df, "Completeness", method="dense", output_column="QualityRank")

# Validate and save
df = Developer.test(df, lambda d: len(d) > 0, "All contacts filtered out!")
InOut.output_data(df, "contacts_clean.parquet")
```

---

## 15. Troubleshooting & FAQ

**Q: MemoryError when processing a large file.**

Install PyArrow (`pip install pyarrow`) â€” etlpipe uses it automatically for CSV reads, significantly reducing memory. If data still exceeds available RAM, switch to the Spark engine on a cluster.

---

**Q: `Join.join` returns three DataFrames. Which one should I use?**

The three outputs mirror visual ETL output anchors:
- `left_unjoined` (L): rows in the left DataFrame with **no match** in right
- `joined` (J): rows that matched in **both** DataFrames â€” this is usually what you want
- `right_unjoined` (R): rows in the right DataFrame with **no match** in left

```python
_, joined, _ = Join.join(orders, customers, on="CustomerID")
```

---

**Q: `Preparation.formula` raises `ValueError: Could not safely evaluate formula`.**

String expressions use `df.eval()` which only supports column references and math/comparison operators. Use a lambda callable for any Python function calls:

```python
# Fails â€” .upper() is not supported in df.eval()
df = Preparation.formula(df, "Upper", "Name.upper()")

# Works â€” lambda executes full Python
df = Preparation.formula(df, "Upper", lambda d: d["Name"].str.upper())
```

---

**Q: Filter on a boolean column raises `ValueError: The truth value of a Series is ambiguous`.**

Always use the operator-based Basic Filter mode for boolean columns. Never use string expressions like `"IsActive == True"`:

```python
# Correct â€” vectorized, NaN-safe
active, inactive = Preparation.filter(df, column="IsActive", operator="is true")
```

---

**Q: How do I use etlpipe on Databricks?**

Install `etlpipe[spark]` as a cluster library via the Databricks UI or init script. Databricks has an active `SparkSession` â€” etlpipe finds it automatically when you call `set_backend("spark")`.

---

**Q: Spark `record_id` does not produce sequential integers (1, 2, 3, ...).**

This is intentional. `monotonically_increasing_id()` avoids a full global sort which would require funneling all partitions through a single node â€” catastrophic at scale. IDs are guaranteed unique and monotonically increasing within each partition. If you need strict global sequences, use the Pandas engine or apply native Spark `zipWithIndex`.

---

**Q: How do I debug a failing YAML pipeline step?**

Insert a `browse` step between suspect steps â€” it prints a full data profile without stopping execution:

```yaml
- id: "debug_inspect"
  tool: "InOut.browse"
  inputs:
    df: "previous_step"
  args:
    n: 20
```

---

**Q: Does etlpipe support incremental/streaming data?**

Not natively. etlpipe is a batch-oriented library. For streaming, use PySpark Structured Streaming directly and call etlpipe functions on each micro-batch via `foreachBatch`.

---

## 16. Roadmap & Contributing

### Current Roadmap (H2)

- **Polars backend**: Third engine for ultra-fast single-machine processing without JVM.
- **dbt integration**: Native etlpipe â†’ dbt model compilation.
- **Enhanced YAML validation**: JSON Schema validation of pipeline YAML before execution begins.
- **Additional PII patterns**: GDPR-focused European identifier patterns.

### How to Contribute

1. **Report Bugs**: Open a GitHub issue with Python version, OS, and a minimal reproducer.
2. **Add Tools**: Submit a PR adding to the appropriate palette. Every new tool needs tests in `tests/`.
3. **Optimize Spark UDFs**: Help write better vectorized Pandas UDFs for the Spark backend.
4. **Improve Documentation**: Add examples, tutorials, or correct inaccuracies.

```bash
git clone https://github.com/your-org/etlpipe
pip install -e ".[dev]"
pytest tests/    # All 445 tests must pass before submitting a PR
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution guide, code style requirements, and PR review checklist.
