"""YAML / JSON schema file support for etlpipe-governance.

Allows schema contracts to be stored as version-controlled files
alongside pipeline code (schema-as-code) rather than being hard-coded
in Python.

Example::

    from etlpipe_governance import load_schema, save_schema, expect_schema

    # Load a schema from YAML
    schema = load_schema("schemas/sales.yaml")

    # Validate data against it
    expect_schema(df, schema)

    # Infer and save a schema for bootstrapping
    schema = infer_schema(df)
    save_schema(schema, "schemas/inferred_sales.yaml")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("etlpipe_governance.schema_io")

# PyYAML is optional — only needed for YAML files
try:
    import yaml

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


def load_schema(path: str | Path) -> dict[str, Any]:
    """Load a schema contract from a YAML or JSON file.

    The file format is auto-detected from the file extension:
    ``.yaml`` / ``.yml`` for YAML, ``.json`` for JSON.

    Args:
        path: Path to the schema file.

    Returns:
        A schema dict suitable for :func:`expect_schema`.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not recognised.
        ImportError: If a YAML file is requested but ``PyYAML`` is not
            installed.

    Example::

        >>> schema = load_schema("schemas/users.yaml")
        >>> schema["columns"]["email"]["dtype"]
        'str'
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        if not _HAS_YAML:
            raise ImportError("PyYAML is required to load YAML schema files. Install it with: pip install pyyaml")
        with open(path, encoding="utf-8") as f:
            schema = yaml.safe_load(f)
    elif suffix == ".json":
        with open(path, encoding="utf-8") as f:
            schema = json.load(f)
    else:
        raise ValueError(f"Unsupported schema file format: '{suffix}'. Use .yaml, .yml, or .json.")

    if not isinstance(schema, dict):
        raise ValueError(f"Schema file must contain a mapping, got {type(schema).__name__}.")

    # Normalise: if the file has a top-level "columns" key, it's already
    # in the expected format.  If not, wrap it.
    if "columns" not in schema:
        schema = {"columns": schema}

    logger.info("Loaded schema from %s (%d columns)", path, len(schema.get("columns", {})))
    return schema


def save_schema(schema: dict[str, Any], path: str | Path) -> Path:
    """Save a schema dict to a YAML or JSON file.

    Args:
        schema: A schema dict (as produced by :func:`infer_schema`).
        path: Destination file path.  Format is auto-detected from the
            extension.

    Returns:
        The resolved :class:`Path` that was written.

    Raises:
        ValueError: If the file extension is not recognised.
        ImportError: If a YAML file is requested but ``PyYAML`` is not
            installed.

    Example::

        >>> from etlpipe_governance import infer_schema, save_schema
        >>> schema = infer_schema(df)
        >>> save_schema(schema, "schemas/users.yaml")
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        if not _HAS_YAML:
            raise ImportError("PyYAML is required to save YAML schema files. Install it with: pip install pyyaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(schema, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    elif suffix == ".json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
    else:
        raise ValueError(f"Unsupported schema file format: '{suffix}'. Use .yaml, .yml, or .json.")

    logger.info("Saved schema to %s (%d columns)", path, len(schema.get("columns", {})))
    return path


def schema_to_yaml(schema: dict[str, Any]) -> str:
    """Serialise a schema dict to a YAML string.

    Useful for logging, debugging, or embedding schemas in documentation
    without writing to a file.

    Args:
        schema: A schema dict.

    Returns:
        A YAML-formatted string.

    Raises:
        ImportError: If ``PyYAML`` is not installed.
    """
    if not _HAS_YAML:
        raise ImportError("PyYAML is required for YAML serialisation. Install it with: pip install pyyaml")
    return yaml.dump(schema, default_flow_style=False, sort_keys=False, allow_unicode=True)
