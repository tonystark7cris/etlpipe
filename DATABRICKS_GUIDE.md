# End-to-End Etlpipe Implementation on Databricks

This guide provides a step-by-step walkthrough for implementing a full, production-ready Etlpipe project on **Databricks**. 

Because Etlpipe features a dynamic dual-engine architecture, you can write familiar Etlpipe-like logic in Python, and Etlpipe will translate it natively into distributed Spark execution under the hood.

---

## Architecture Overview

1. **Ingestion**: Read raw data from Databricks Delta Tables (or DBFS/S3).
2. **Transformation**: Execute Etlpipe logic utilizing the `spark` backend engine.
3. **Validation**: Assert data quality before loading.
4. **Load**: Write the transformed data back to a curated Delta Table.
5. **Orchestration**: Schedule the notebook/script via Databricks Workflows (Jobs).

---

## Step 1: Cluster Setup

To run Etlpipe on Databricks, you just need to install the core package. Databricks already provides the Spark backend natively.

1. Navigate to your Databricks Workspace -> **Compute**.
2. Select your target cluster (e.g., Databricks Runtime 13.3 LTS).
3. Click the **Libraries** tab -> **Install New**.
4. Select **PyPI** and enter: `etlpipe`
5. Click **Install**. 

Alternatively, if you are using Databricks Repos, add `etlpipe` to your `requirements.txt`.

---

## Step 2: Project Structure

When using Databricks Repos (Git integration), we recommend structuring your Etlpipe project like a standard software engineering repository:

```text
/my-databricks-project
├── notebooks/
│   └── 01_run_pipeline.py     # Main entry point for Databricks Jobs
├── src/
│   ├── config.yaml            # Pipeline configuration
│   └── pipeline.py            # Core Etlpipe logic
├── tests/
│   └── test_pipeline.py       # Unit tests (run locally via Pytest)
└── requirements.txt           # Etlpipe[spark], etc.
```

---

## Step 3: Core Pipeline Implementation (`src/pipeline.py`)

Here is the core business logic. We explicitly configure Etlpipe to use the `spark` backend so that operations execute on the cluster rather than the driver node.

```python
import etlpipe
from etlpipe import InOut, Preparation, Join, Transform, Developer

def run_customer_360_pipeline():
    # ==========================================
    # 0. Set Backend to Spark
    # ==========================================
    etlpipe.set_backend("spark")
    print("Executing Etlpipe Pipeline on Apache Spark Backend...")

    # ==========================================
    # 1. Ingest Data from Delta Tables
    # ==========================================
    # In Databricks, you can query Delta tables directly via Spark SQL syntax
    # Etlpipe's spark backend treats SQL queries natively.
    df_customers = InOut.input_data("dbfs:/mnt/lakehouse/raw/customers")
    df_orders = InOut.input_data("dbfs:/mnt/lakehouse/raw/orders")
    
    # ==========================================
    # 2. Data Cleansing & Preparation
    # ==========================================
    # Cleanse Customer data: upper case names, strip whitespace, handle nulls
    df_customers_clean = Preparation.data_cleansing(
        df_customers,
        replace_nulls_with="",
        strip_whitespace=True,
        modify_case="upper"
    )
    
    # Filter for completed orders
    df_orders_valid, df_orders_invalid = Preparation.filter(
        df_orders, 
        "OrderStatus = 'COMPLETED'"
    )
    
    # ==========================================
    # 3. Join Datasets
    # ==========================================
    # Join (L: Unjoined Customers, J: Joined Data, R: Unjoined Orders)
    left_unjoined, joined_data, right_unjoined = Join.join(
        df_customers_clean, 
        df_orders_valid, 
        on="CustomerID"
    )
    
    # ==========================================
    # 4. Transform & Aggregate
    # ==========================================
    # Summarize Total Lifetime Value (LTV) and Order Count by Customer
    summary_data = Transform.summarize(
        joined_data,
        group_by=["CustomerID", "CustomerName", "Region"],
        aggregations={
            "OrderAmount": ["sum", "mean"],
            "OrderID": "count distinct"
        }
    )
    
    # Apply business logic using Formula
    final_data = Preparation.formula(
        summary_data,
        column="CustomerTier",
        expression="IF Sum_OrderAmount > 10000 THEN 'Platinum' ELSE 'Standard' ENDIF"
    )
    
    # ==========================================
    # 5. Data Quality Testing
    # ==========================================
    # Developer.test evaluates natively on the Spark DataFrame
    Developer.test(
        final_data,
        condition_func=lambda df: df["Sum_OrderAmount"].min() >= 0,
        error_msg="Data Quality Failure: Negative LTV detected."
    )
    
    # ==========================================
    # 6. Load Output to Delta Lake
    # ==========================================
    # Write the output back to the Databricks Lakehouse as a Delta table
    InOut.output_data(
        final_data, 
        "dbfs:/mnt/lakehouse/curated/customer_360",
        format="delta",
        mode="overwrite"
    )
    
    print("Pipeline executed successfully. Output written to Curated layer.")

if __name__ == "__main__":
    run_customer_360_pipeline()
```

---

## Step 4: The Databricks Entrypoint (`notebooks/01_run_pipeline.py`)

In Databricks, you typically create a notebook to serve as the entry point for your Workflows/Jobs. Because we defined our code in a `src` module, the notebook is extremely clean:

```python
# COMMAND ----------
# MAGIC %pip install -r ../requirements.txt
# COMMAND ----------

import sys
import os

# Ensure the src directory is in the Python path
sys.path.append(os.path.abspath("../src"))

from pipeline import run_customer_360_pipeline

# COMMAND ----------
# Run the pipeline
run_customer_360_pipeline()
```

---

## Step 5: Scheduling via Databricks Workflows

To run this pipeline automatically:

1. Navigate to **Workflows** in the Databricks sidebar and click **Create Job**.
2. Name the Job: `Etlpipe_Customer360_ETL`.
3. In the task configuration:
   - **Type**: Notebook
   - **Source**: Workspace (or Git if using Repos).
   - **Path**: Select `notebooks/01_run_pipeline.py`.
   - **Compute**: Select the cluster you configured in Step 1 (or define a Job Cluster for cheaper, ephemeral execution).
4. **Schedule**: Set a trigger (e.g., Daily at 2:00 AM) and configure Failure Alerts to notify your team via Email/Slack.

---

## Databricks Specific Best Practices

- **Leverage Delta Lake**: When using `InOut.input_data` and `InOut.output_data`, specify paths starting with `dbfs:/` and utilize the `format="delta"` argument to leverage Databricks' optimized storage layer.
- **Job Clusters vs. All-Purpose Clusters**: For scheduled Etlpipe pipelines, use **Job Clusters**. They are significantly cheaper and automatically terminate when the Etlpipe workflow completes.
- **Avoid `.browse()` in Production**: While `InOut.browse()` is fantastic for debugging interactively in a Notebook, remove it from production scripts, as it forces Spark to collect data to the driver node, which can cause Out-Of-Memory (OOM) errors on massive datasets.
