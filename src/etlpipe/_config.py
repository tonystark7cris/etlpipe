import threading
from contextlib import contextmanager
from typing import Any

from etlpipe.engines.pandas_engine import PandasEngine

try:
    from etlpipe.engines.spark_engine import SparkEngine
except ImportError:
    SparkEngine = None

# Thread-local storage for configuration so multiple pipelines can run safely
_local_state = threading.local()


def _init_state():
    if not hasattr(_local_state, "backend"):
        _local_state.backend = "pandas"
    if not hasattr(_local_state, "engine"):
        _local_state.engine = PandasEngine()
    if not hasattr(_local_state, "spark_config"):
        _local_state.spark_config = {}


def set_backend(backend_name: str, **kwargs: Any) -> None:
    _init_state()
    backend_name = backend_name.lower().strip()
    if backend_name == "pandas":
        _local_state.backend = "pandas"
        _local_state.engine = PandasEngine()
    elif backend_name == "spark":
        if SparkEngine is None:
            raise ImportError(
                "PySpark is required for the Spark backend. Install it with: pip install etlpipe[spark]"
            )
        _local_state.backend = "spark"
        _local_state.engine = SparkEngine(**kwargs)
        _local_state.spark_config = kwargs
    else:
        raise ValueError(f"Unknown backend: '{backend_name}'. Supported backends are: 'pandas', 'spark'.")


def get_backend() -> str:
    _init_state()
    return _local_state.backend


def get_engine() -> Any:
    _init_state()
    return _local_state.engine


def reset_backend() -> None:
    _local_state.backend = "pandas"
    _local_state.engine = PandasEngine()
    _local_state.spark_config = {}


@contextmanager
def backend(backend_name: str, **kwargs: Any):
    _init_state()
    prev_backend = _local_state.backend
    prev_engine = _local_state.engine
    prev_spark_config = getattr(_local_state, "spark_config", {})

    try:
        set_backend(backend_name, **kwargs)
        yield
    finally:
        _local_state.backend = prev_backend
        _local_state.engine = prev_engine
        _local_state.spark_config = prev_spark_config
