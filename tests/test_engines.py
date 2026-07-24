import os
import sys
import threading

import pytest

import etlpipe
from etlpipe._config import get_backend, get_engine, reset_backend, set_backend
from etlpipe.engines.pandas_engine import PandasEngine

# Windows PySpark local worker fix
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

# Fallback for stale terminals that haven't picked up the winget JAVA_HOME yet
if "JAVA_HOME" not in os.environ:
    default_java = r"C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot"
    if os.path.exists(default_java):
        os.environ["JAVA_HOME"] = default_java

import importlib.util

HAS_SPARK = importlib.util.find_spec("pyspark") is not None
if HAS_SPARK:
    from etlpipe.engines.spark_engine import SparkEngine


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_backend()
    yield
    reset_backend()


def test_default_backend():
    assert get_backend() == "pandas"
    engine = get_engine()
    assert isinstance(engine, PandasEngine)
    assert engine.name == "pandas"


@pytest.mark.skipif(not HAS_SPARK, reason="PySpark not installed")
def test_set_spark_backend():
    set_backend("spark")
    assert get_backend() == "spark"
    engine = get_engine()
    assert isinstance(engine, SparkEngine)
    assert engine.name == "spark"


def test_invalid_backend():
    with pytest.raises(ValueError, match="Unknown backend"):
        set_backend("unknown_backend")


@pytest.mark.skipif(not HAS_SPARK, reason="PySpark not installed")
def test_context_manager():
    assert get_backend() == "pandas"

    with etlpipe.backend("spark"):
        assert get_backend() == "spark"
        assert isinstance(get_engine(), SparkEngine)

    assert get_backend() == "pandas"
    assert isinstance(get_engine(), PandasEngine)


@pytest.mark.skipif(not HAS_SPARK, reason="PySpark not installed")
def test_thread_safety():
    """Ensure backend switching in one thread doesn't affect another."""

    def worker(backend_name, result_list):
        if backend_name:
            set_backend(backend_name)
        result_list.append(get_backend())

    results1 = []
    results2 = []

    t1 = threading.Thread(target=worker, args=("spark", results1))
    t2 = threading.Thread(target=worker, args=(None, results2))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results1[0] == "spark"
    assert results2[0] == "pandas"  # Should default to pandas, unaffected by t1
