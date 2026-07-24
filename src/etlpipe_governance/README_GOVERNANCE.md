# etlpipe-governance

**Enterprise data quality toolkit — PII detection & masking, schema contracts, statistical profiling, and audit suites.**

This is a standalone module of the `etlpipe` engine. It provides robust data governance tools designed to ensure data quality, regulatory compliance, and schema enforcement before data enters your core pipelines.

## Installation

```bash
pip install etlpipe-governance
```

*(Note: If you are using the full `etlpipe` execution engine, this module is already bundled and available natively without a separate install).*

---

## 🛡️ 1. PII Detection & Masking (GDPR / HIPAA Compliance)

Automated detection of columns containing sensitive personal data (Emails, Phone numbers, SSNs, Credit Cards, IP Addresses, etc.) and robust masking strategies.

```python
from etlpipe_governance import scan_pii, mask_pii
import pandas as pd

df = pd.read_csv("raw_users.csv")

# Step 1: Scan for PII (returns a DataFrame report of detected columns)
report = scan_pii(df)
print(report[["Column", "PII_Type", "Confidence"]])

# Step 2: Mask the detected PII before sharing or saving
# Strategy: "redact" (***REDACTED***)
safe_df = mask_pii(df, report, strategy="redact")

# Strategy: "hash" (SHA-256 for referential integrity)
hashed_df = mask_pii(df, report, strategy="hash")

# Strategy: "pseudonymise" (EMAIL_1, EMAIL_2, etc.)
pseudo_df, mapping_dict = mask_pii(df, report, strategy="pseudonymise", return_mapping=True)
```

---

## 📜 2. Schema Contracts

Enforce strict data type and nullability constraints at your pipeline boundaries. If bad data arrives, it fails loudly rather than silently propagating.

```python
from etlpipe_governance import infer_schema, expect_schema, SchemaViolationError

# Bootstrap a schema from a known-good DataFrame
schema = infer_schema(good_df)

try:
    # Enforce the schema on new incoming data
    expect_schema(new_df, schema, strict=True)
except SchemaViolationError as e:
    print(f"Pipeline halted! Violations: {e.violations}")
```

---

## 📊 3. Statistical Profiling

Go beyond data types to understand the shape, distribution, and health of your data.

```python
from etlpipe_governance import profile

# Generate stats: null-rates, cardinality, min/max/mean, top-N values
stats_df = profile(df)
print(stats_df[["Column", "Null_Rate", "Unique_Count", "Top_Values"]])
```

---

## 🧪 4. Contract Suites

Compose multiple schema checks into a single audit run. This produces a combined pass/fail report suitable for Data Governance dashboards and Data Observability platforms.

```python
from etlpipe_governance import ContractSuite

suite = ContractSuite("Daily Pipeline Audit")
suite.add_contract("raw_users", user_schema)
suite.add_contract("raw_transactions", txn_schema)

# Run the suite against a dictionary of DataFrames
results = suite.run({
    "raw_users": user_df,
    "raw_transactions": txn_df
})

print(results)  # Returns a DataFrame with pass/fail metrics per contract
```

---

## Documentation

For full documentation, advanced usage, and engine integration, please visit the main repository:
[https://github.com/tonystark7cris/etlpipe](https://github.com/tonystark7cris/etlpipe)
