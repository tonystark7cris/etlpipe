"""
etlpipe Enterprise Data Pipeline Demo
========================================
Demonstrates running the SAME pipeline logic on both Pandas and PySpark
backends, with enterprise governance features (PII scanning, data contracts,
pipeline metrics, event hooks).

Usage:
    python demo_pipeline.py
"""

import logging
import sys

import etlpipe
from etlpipe import (
    InOut,
    Preparation,
    Join,
    Transform,
    Parse,
    Developer,
    Pipeline,
    expect_schema,
    infer_schema,
    scan_pii,
)

# ------------------------------------------------------------------ #
# Configure structured logging (Big 4 standard)
# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("demo")

# Fix Windows console encoding for Unicode/emoji output
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ================================================================== #
#  Step 1: Generate Sample Enterprise Data
# ================================================================== #
def generate_sample_data():
    """Create realistic enterprise sales + customer datasets."""
    logger.info("Generating sample enterprise data...")

    # --- Sales Transactions ---
    sales = InOut.text_input({
        "TransactionID": [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010,
                          1011, 1012, 1013, 1014, 1015, 1016, 1017, 1018, 1019, 1020],
        "CustomerID":    [101, 102, 103, 104, 105, 101, 102, 103, 106, 107,
                          108, 101, 104, 105, 109, 110, 103, 102, 111, 112],
        "Product":       ["Laptop", "Phone", "Tablet", "Laptop", "Monitor",
                          "Keyboard", "Phone", "Laptop", "Mouse", "Webcam",
                          "Headset", "Dock", "SSD", "RAM", "Cable",
                          "Laptop", "Phone", "Tablet", "Monitor", "Keyboard"],
        "Category":      ["Hardware", "Mobile", "Mobile", "Hardware", "Hardware",
                          "Accessories", "Mobile", "Hardware", "Accessories", "Accessories",
                          "Accessories", "Hardware", "Hardware", "Hardware", "Accessories",
                          "Hardware", "Mobile", "Mobile", "Hardware", "Accessories"],
        "Amount":        [1200, 800, 450, 1500, 350, 75, 900, 1100, 25, 60,
                          150, 200, 180, 90, -10, 1300, 850, 500, 400, 80],
        "Quantity":      [1, 2, 1, 1, 1, 3, 1, 1, 5, 2,
                          2, 1, 2, 4, 1, 1, 1, 2, 1, 3],
        "Date":          ["2025-01-15", "2025-01-20", "2025-02-10", "2025-02-14", "2025-03-01",
                          "2025-03-15", "2025-04-01", "2025-04-10", "2025-04-22", "2025-05-01",
                          "2025-05-15", "2025-06-01", "2025-06-10", "2025-06-20", "2025-07-01",
                          "2025-07-15", "2025-08-01", "2025-08-10", "2025-09-01", "2025-09-15"],
        "SalesRep":      ["alice", " Bob ", "CHARLIE", "alice", "  diana  ",
                          "alice", " Bob ", "CHARLIE", "eve  ", "frank",
                          "alice", "alice", "  diana  ", "eve  ", "frank",
                          " Bob ", "CHARLIE", " Bob ", "alice", "eve  "],
    })

    # --- Customer Master Data ---
    customers = InOut.text_input({
        "CustomerID":  [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112],
        "Name":        ["Acme Corp", "Beta Inc", "Gamma LLC", "Delta Ltd", "Epsilon SA",
                        "Zeta GmbH", "Eta Corp", "Theta Inc", "Iota LLC", "Kappa Ltd",
                        "Lambda SA", "Mu Corp"],
        "Region":      ["North", "South", "East", "West", "North",
                        "South", "East", "West", "North", "South",
                        "East", "West"],
        "Tier":        ["Enterprise", "SMB", "Enterprise", "Enterprise", "SMB",
                        "SMB", "Enterprise", "SMB", "Enterprise", "Enterprise",
                        "SMB", "SMB"],
        "Email":       ["contact@acme.com", "info@beta.io", "sales@gamma.com",
                        "admin@delta.co.uk", "hello@epsilon.fr", "support@zeta.de",
                        "team@eta.com", "ops@theta.io", "dev@iota.com", "biz@kappa.co",
                        "eng@lambda.sa", "hr@mu.com"],
        "Phone":       ["+1-555-100-1001", "+1-555-200-2002", "+1-555-300-3003",
                        "+44-20-7946-0958", "+33-1-4723-5400", "+49-30-1234-5678",
                        "+1-555-700-7007", "+1-555-800-8008", "+1-555-900-9009",
                        "+1-555-100-1010", "+34-91-123-4567", "+1-555-120-1212"],
    })

    # Save to disk for YAML pipeline execution
    InOut.output_data(sales, str(SCRIPT_DIR / "demo_sales.csv"))
    InOut.output_data(customers, str(SCRIPT_DIR / "demo_customers.csv"))

    logger.info("Sample data saved: demo_sales.csv (%d rows), demo_customers.csv (%d rows)",
                len(sales), len(customers))
    return sales, customers


# ================================================================== #
#  Step 2: Enterprise Governance Checks (Pre-Pipeline)
# ================================================================== #
def run_governance_checks(sales, customers):
    """Run PII scanning and data contract validation before pipeline execution."""
    logger.info("=" * 60)
    logger.info("GOVERNANCE: Pre-Pipeline Compliance Checks")
    logger.info("=" * 60)

    # --- PII Scan ---
    logger.info("Running PII scan on customer data...")
    pii_report = scan_pii(customers, warn=False)
    if not pii_report.empty:
        print("\nðŸ“‹ PII Scan Report (Customer Data):")
        print(pii_report[["Column", "PII_Type", "Confidence", "Description"]].to_string(index=False))
        print()
    else:
        print("âœ… No PII detected.\n")

    # --- Data Contracts ---
    logger.info("Validating sales data contract...")
    sales_schema = {
        "columns": {
            "TransactionID": {"dtype": "int", "nullable": False},
            "CustomerID":    {"dtype": "int", "nullable": False},
            "Product":       {"dtype": "str", "nullable": False},
            "Amount":        {"dtype": "int", "nullable": False},
            "Quantity":      {"dtype": "int", "nullable": False},
        }
    }
    expect_schema(sales, sales_schema)
    logger.info("âœ… Sales data contract validated successfully")

    # --- Infer & Display Customer Schema ---
    customer_schema = infer_schema(customers)
    print("ðŸ“„ Inferred Customer Schema:")
    for col, spec in customer_schema["columns"].items():
        print(f"   {col:15s} â†’ dtype={spec['dtype']:10s} nullable={spec['nullable']}")
    print()


# ================================================================== #
#  Step 3: Execute Pipeline with Python API
# ================================================================== #
def run_pipeline_python_api(backend_name: str):
    """Run the full ETL pipeline using the Python API on the given backend."""
    logger.info("=" * 60)
    logger.info("PIPELINE: Running on '%s' backend (Python API)", backend_name)
    logger.info("=" * 60)

    etlpipe.set_backend(backend_name)

    # 1. Load
    sales = InOut.input_data(str(SCRIPT_DIR / "demo_sales.csv"))
    customers = InOut.input_data(str(SCRIPT_DIR / "demo_customers.csv"))

    # 2. Cleanse â€” normalize whitespace, case in SalesRep
    sales_clean = Preparation.data_cleansing(
        sales,
        columns=["SalesRep"],
        strip_whitespace=True,
        modify_case="title",
    )

    # 3. Filter â€” remove negative/zero amounts (returns & errors)
    valid_sales, rejected = Preparation.filter(sales_clean, "Amount > 0")
    logger.info("Filter: %s valid, %s rejected",
                len(valid_sales) if backend_name == "pandas" else "N/A",
                len(rejected) if backend_name == "pandas" else "N/A")

    # 4. Formula â€” calculate profit margin and tax
    with_profit = Preparation.formula(valid_sales, "Profit", "Amount * 0.25")
    with_tax = Preparation.formula(with_profit, "Tax", "Amount * 0.18")
    with_net = Preparation.formula(with_tax, "NetRevenue", "Amount - Tax")

    # 5. Join â€” enrich with customer master data
    left_only, enriched, right_only = Join.join(with_net, customers, on="CustomerID")
    logger.info("Join: enriched sales with customer regions and tiers")

    # 6. Summarize â€” aggregate by Region and Tier
    region_summary = Transform.summarize(
        enriched,
        group_by=["Region", "Tier"],
        aggregations={
            "Amount": ["sum", "mean", "count"],
            "Profit": ["sum"],
            "NetRevenue": ["sum"],
        }
    )

    # 7. Sort â€” by total profit descending
    sorted_summary = Preparation.sort(region_summary, ["Sum_Profit"], ascending=False)

    # 8. Running total
    with_running = Transform.running_total(sorted_summary, "Sum_Profit")

    # 9. Output
    output_file = str(SCRIPT_DIR / f"pipeline_output_{backend_name}.csv")
    InOut.output_data(with_running, output_file)
    logger.info("Output saved to: %s", output_file)

    # 10. Validate output schema
    if backend_name == "pandas":
        Developer.test(
            with_running,
            lambda df: df["Sum_Profit"].sum() > 0,
            "Total profit must be positive!"
        )
        logger.info("âœ… Output validation passed")

    # 11. Browse â€” display final result
    print(f"\nðŸ“Š Pipeline Results ({backend_name.upper()} backend):")
    InOut.browse(with_running, n=10)

    # Reset backend
    etlpipe.set_backend("pandas")

    return with_running


# ================================================================== #
#  Step 4: Execute Pipeline with YAML + Event Hooks
# ================================================================== #
def run_pipeline_yaml():
    """Run the YAML pipeline with event hooks and metrics tracking."""
    logger.info("=" * 60)
    logger.info("PIPELINE: Running YAML pipeline with event hooks")
    logger.info("=" * 60)

    # Create a YAML pipeline that uses the demo data
    import yaml
    pipeline_config = {
        "name": "Enterprise Sales Analytics (YAML)",
        "backend": "pandas",
        "steps": [
            {"id": "load_sales", "tool": "InOut.input_data",
             "args": {"path": str(SCRIPT_DIR / "demo_sales.csv")}},

            {"id": "load_customers", "tool": "InOut.input_data",
             "args": {"path": str(SCRIPT_DIR / "demo_customers.csv")}},

            {"id": "cleanse", "tool": "Preparation.data_cleansing",
             "inputs": {"df": "load_sales"},
             "args": {"strip_whitespace": True, "modify_case": "upper"}},

            {"id": "filter_valid", "tool": "Preparation.filter",
             "inputs": {"df": "cleanse"},
             "args": {"condition": "Amount > 0"}},

            {"id": "add_profit", "tool": "Preparation.formula",
             "inputs": {"df": "filter_valid.0"},
             "args": {"column": "Profit", "expression": "Amount * 0.25"}},

            {"id": "join_data", "tool": "Join.join",
             "inputs": {"left": "add_profit", "right": "load_customers"},
             "args": {"on": "CustomerID"}},

            {"id": "summarize", "tool": "Transform.summarize",
             "inputs": {"df": "join_data.1"},
             "args": {"group_by": ["Region"],
                      "aggregations": {"Amount": ["sum", "mean"],
                                       "Profit": ["sum"]}}},

            {"id": "sort_result", "tool": "Preparation.sort",
             "inputs": {"df": "summarize"},
             "args": {"columns": ["Sum_Profit"], "ascending": False}},

            {"id": "save", "tool": "InOut.output_data",
             "inputs": {"df": "sort_result"},
             "args": {"path": str(SCRIPT_DIR / "demo_yaml_output.csv")}},
        ]
    }

    yaml_path = str(SCRIPT_DIR / "demo_pipeline.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump(pipeline_config, f, default_flow_style=False, sort_keys=False)

    # --- Event Hooks (Alerting Foundation) ---
    step_log = []

    def on_start(step_id, tool_name):
        step_log.append(f"â–¶ {step_id}")

    def on_complete(step_id, tool_name, metrics):
        rows = metrics.get("output_rows", metrics.get("output_0_rows", "â€”"))
        step_log.append(f"  âœ… {step_id}: {metrics['duration_s']}s, {rows} rows")

    def on_error(step_id, tool_name, error):
        step_log.append(f"  âŒ {step_id}: FAILED â€” {error}")

    def on_pipeline_done(name, all_metrics):
        total = sum(m["duration_s"] for m in all_metrics)
        step_log.append(f"\nðŸ Pipeline '{name}' completed: {len(all_metrics)} steps in {total:.3f}s")

    # Execute with hooks
    pipeline = Pipeline.run(
        yaml_path,
        on_step_start=on_start,
        on_step_complete=on_complete,
        on_step_error=on_error,
        on_pipeline_complete=on_pipeline_done,
    )

    # Display execution trace
    print("\nðŸ“‹ Pipeline Execution Trace:")
    for line in step_log:
        print(f"   {line}")

    # Display metrics summary
    print("\nðŸ“Š Pipeline Metrics:")
    print(f"   {'Step':<20s} {'Tool':<30s} {'Duration':>10s} {'Rows':>8s} {'Status':>8s}")
    print(f"   {'â”€'*20} {'â”€'*30} {'â”€'*10} {'â”€'*8} {'â”€'*8}")
    for m in pipeline.metrics:
        rows = str(m.get("output_rows", m.get("output_0_rows", "â€”")))
        print(f"   {m['step_id']:<20s} {m['tool']:<30s} {m['duration_s']:>9.4f}s {rows:>8s} {m['status']:>8s}")

    total_time = sum(m["duration_s"] for m in pipeline.metrics)
    print(f"\n   Total pipeline time: {total_time:.4f}s")

    return pipeline


# ================================================================== #
#  Main Entry Point
# ================================================================== #
def main():
    print("=" * 60)
    print("  ðŸ¦ etlpipe Enterprise Pipeline Demo")
    print(f"  Version: {etlpipe.__version__}")
    print("=" * 60)
    print()

    # 1. Generate data
    sales, customers = generate_sample_data()

    # 2. Governance checks
    run_governance_checks(sales, customers)

    # 3. Run on Pandas backend
    pandas_result = run_pipeline_python_api("pandas")

    # 4. Run on PySpark backend
    try:
        spark_result = run_pipeline_python_api("spark")
        print("\nâœ… Both backends produced results successfully!")
    except ImportError:
        logger.warning("PySpark not installed â€” skipping Spark backend. Install with: pip install etlpipe[spark]")
        spark_result = None

    # 5. Run YAML pipeline with hooks
    pipeline = run_pipeline_yaml()

    # 6. Final summary
    print("\n" + "=" * 60)
    print("  ðŸ“ Output Files Generated:")
    print("  â”€" * 30)
    print("  â€¢ demo_sales.csv           (sample sales data)")
    print("  â€¢ demo_customers.csv       (sample customer data)")
    print("  â€¢ pipeline_output_pandas.csv (Python API â€” Pandas)")
    if spark_result is not None:
        print("  â€¢ pipeline_output_spark.csv  (Python API â€” Spark)")
    print("  â€¢ demo_yaml_output.csv     (YAML pipeline)")
    print("  â€¢ demo_pipeline.yaml       (generated YAML config)")
    print("=" * 60)


if __name__ == "__main__":
    main()
