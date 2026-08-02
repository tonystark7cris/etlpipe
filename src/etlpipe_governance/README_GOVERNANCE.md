# etlpipe-governance

**Enterprise data quality toolkit — PII detection & masking, schema contracts, value-level rules, volume & freshness checks, statistical profiling, audit trails, and reporting.**

This is a standalone module of the `etlpipe` engine. It provides robust data governance tools designed to ensure data quality, regulatory compliance, and schema enforcement before data enters your core pipelines.

## Installation

```bash
pip install etlpipe-governance

# With YAML schema support
pip install etlpipe-governance[yaml]
```

*(Note: If you are using the full `etlpipe` execution engine, this module is already bundled and available natively without a separate install).*

---

## 🛡️ 1. PII Detection & Masking (GDPR / HIPAA Compliance)

Automated detection of columns containing sensitive personal data (Emails, Phone numbers, SSNs, Credit Cards, IP Addresses, Aadhaar, IBAN, Passports, etc.) and robust masking strategies.

```python
from etlpipe_governance import scan_pii, mask_pii
import pandas as pd

df = pd.read_csv("raw_users.csv")

# Step 1: Scan for PII (returns a DataFrame report of detected columns)
report = scan_pii(df)
print(report[["Column", "PII_Type", "Confidence"]])

# Step 2: Mask the detected PII before sharing or saving
safe_df = mask_pii(df, report, strategy="redact")       # ***REDACTED***
hashed_df = mask_pii(df, report, strategy="hash")        # SHA-256 tokens
pseudo_df, mapping = mask_pii(df, report, strategy="pseudonymise")  # EMAIL_1, PERSON_2
```

---

## 📜 2. Schema Contracts with Value-Level Rules

Enforce strict data type, nullability, and **value-level** constraints at your pipeline boundaries. Supports `min_value`, `max_value`, `allowed_values`, `value_regex`, `min_length`, `max_length`, and `unique`.

```python
from etlpipe_governance import expect_schema, SchemaViolationError

try:
    expect_schema(df, {
        "columns": {
            "Age": {"dtype": "int", "nullable": False, "min_value": 0, "max_value": 120},
            "Status": {"dtype": "str", "allowed_values": ["active", "inactive", "pending"]},
            "Email": {"dtype": "str", "value_regex": r".+@.+\..+"},
            "OrderID": {"dtype": "int", "unique": True},
        }
    })
except SchemaViolationError as e:
    print(f"Pipeline halted! {e.violations}")
```

---

## 📂 3. YAML / JSON Schema-as-Code

Store schemas as version-controlled files alongside your pipelines instead of hard-coding them in Python.

```python
from etlpipe_governance import load_schema, save_schema, infer_schema

# Infer a schema from known-good data and save it
schema = infer_schema(reference_df)
save_schema(schema, "schemas/sales.yaml")

# Load and validate in production
schema = load_schema("schemas/sales.yaml")
expect_schema(new_df, schema)
```

---

## 📊 4. Statistical Profiling

Go beyond data types to understand the shape, distribution, and health of your data.

```python
from etlpipe_governance import profile

stats_df = profile(df)
print(stats_df[["Column", "Null_Rate_Pct", "Unique_Count", "Min", "Max", "Top_Values"]])
```

---

## 📏 5. Volume & Freshness Checks

Guard against empty tables, truncated feeds, and stale data.

```python
from etlpipe_governance import expect_row_count, expect_freshness
from datetime import timedelta

# Fail if table has fewer than 1000 rows or more than 5 million
expect_row_count(df, min_rows=1000, max_rows=5_000_000)

# Fail if the newest record in 'updated_at' is older than 6 hours
expect_freshness(df, column="updated_at", max_age=timedelta(hours=6))
```

---

## 🧪 6. Contract Suites

Compose schema contracts, volume checks, and freshness checks into a single audit run with an integrated audit trail.

```python
from etlpipe_governance import ContractSuite, AuditTrail, export_report
from datetime import timedelta

trail = AuditTrail("./governance_logs")

suite = ContractSuite("Daily Pipeline Audit")
suite.add_contract("raw_users", user_schema)
suite.add_contract("raw_transactions", txn_schema)
suite.add_volume_check("raw_users", min_rows=500)
suite.add_freshness_check("raw_transactions", column="created_at", max_age=timedelta(days=1))

results = suite.run({"raw_users": user_df, "raw_transactions": txn_df}, audit_trail=trail, run_id="daily_2026-08-01")

# Export a self-contained HTML report
export_report(results, "reports/audit_2026-08-01.html")
```

---

## 📋 7. Audit Trail

Persist every governance run to a queryable JSONL log for compliance and historical analysis.

```python
from etlpipe_governance import AuditTrail

trail = AuditTrail("./governance_logs")

# Query past runs
history = trail.load()
last_week = trail.load(days=7)
failures = history[history["Status"] == "FAIL"]
```

---

## Documentation

For full documentation, advanced usage, and engine integration, please visit the main repository:
[https://github.com/tonystark7cris/etlpipe](https://github.com/tonystark7cris/etlpipe)
