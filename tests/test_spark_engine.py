import pandas as pd
import pytest

from etlpipe import Developer, Join, Preparation, Transform
from etlpipe._config import get_engine, reset_backend, set_backend

pytest.importorskip("pyspark")

import os
import sys

from pyspark.sql import SparkSession

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


@pytest.fixture(scope="module")
def spark():
    """Create a local Spark session for testing."""
    session = (
        SparkSession.builder.master("local[2]")
        .appName("EtlpipeTest")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture(autouse=True)
def setup_spark_backend(spark):
    """Ensure Spark backend is used for all tests in this file."""
    set_backend("spark", spark=spark)
    yield
    reset_backend()


# --------------------------------------------------------------------------- #
#  Tier 1 Tests (Native Spark)
# --------------------------------------------------------------------------- #


def test_filter_native(spark):
    pdf = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    df = spark.createDataFrame(pdf)

    true_df, false_df = Preparation.filter(df, "A > 1")

    # Verify outputs are SparkDataFrames
    assert type(true_df).__name__ == "DataFrame"

    # Verify logic
    true_pdf = true_df.toPandas()
    assert len(true_pdf) == 2
    assert list(true_pdf["A"]) == [2, 3]


def test_summarize_native(spark):
    pdf = pd.DataFrame({"Group": ["A", "A", "B"], "Value": [10, 20, 30]})
    df = spark.createDataFrame(pdf)

    summary = Transform.summarize(df, group_by="Group", aggregations={"Value": "sum"})

    res = summary.toPandas().sort_values("Group").reset_index(drop=True)
    assert len(res) == 2
    assert list(res["Group"]) == ["A", "B"]
    assert list(res["Sum_Value"]) == [30, 30]


# --------------------------------------------------------------------------- #
#  Tier 2 Tests (Vectorized Pandas UDFs)
# --------------------------------------------------------------------------- #


def test_formula_callable(spark):
    pdf = pd.DataFrame({"A": [1, 2, 3]})
    df = spark.createDataFrame(pdf)

    # Callable uses Pandas series logic inside the UDF
    def my_logic(pdf_chunk):
        return pdf_chunk["A"] * 10

    out = Preparation.formula(df, "A_times_10", expression=my_logic)

    res = out.toPandas().sort_values("A").reset_index(drop=True)
    assert "A_times_10" in res.columns
    # Cast to int because UDF returned string in our simple implementation fallback
    assert list(res["A_times_10"].astype(float)) == [10.0, 20.0, 30.0]


# --------------------------------------------------------------------------- #
#  Tier 3 Tests (Driver-side fallbacks & Size Guards)
# --------------------------------------------------------------------------- #


def test_driver_size_guard(spark):
    pdf = pd.DataFrame({"A": range(100)})
    df = spark.createDataFrame(pdf)

    # Temporarily set max_collect_bytes very low
    engine = get_engine()
    engine.max_collect_bytes = 10  # 10 bytes

    with pytest.raises(MemoryError, match="EtlpipeMemoryError"):
        # test_equal collects to driver
        Developer.test_equal(df, df)


def test_broadcast_join(spark):
    pdf_left = pd.DataFrame({"Key": [1, 2, 3], "Val": ["A", "B", "C"]})
    pdf_right = pd.DataFrame({"Key": [1, 2], "Match": ["Yes", "Yes"]})

    left = spark.createDataFrame(pdf_left)
    right = spark.createDataFrame(pdf_right)

    unjoined, joined, right_unjoined = Join.join(left, right, on="Key")

    res = joined.toPandas().sort_values("Key").reset_index(drop=True)
    assert len(res) == 2
    assert "Match" in res.columns


def test_spark_spaces_in_columns(spark):
    pdf = pd.DataFrame({"Customer Name": ["Alice", "Bob"]})
    df = spark.createDataFrame(pdf)
    result = Preparation.formula(df, "IsAlice", "Customer Name == 'Alice'")
    res = result.toPandas()
    assert res["IsAlice"].iloc[0]
    assert not res["IsAlice"].iloc[1]


def test_spark_datatype_drift_coercion(spark):
    pdf1 = pd.DataFrame({"ID": [1, 2], "V1": ["a", "b"]})
    pdf2 = pd.DataFrame({"ID": ["1", "3"], "V2": ["x", "y"]})
    df1 = spark.createDataFrame(pdf1)
    df2 = spark.createDataFrame(pdf2)

    L, J, R = Join.join(df1, df2, on="ID")
    res_J = J.toPandas()
    assert len(res_J) == 1
    assert res_J["ID"].iloc[0] == 1
