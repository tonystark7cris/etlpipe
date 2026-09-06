"""Secrets resolution for etlpipe pipelines.

Replaces ``${ENV_VAR}`` and ``${env:VAR}`` token placeholders in any
nested configuration structure with live environment variable values.

This module is the only sanctioned way to inject credentials into etlpipe
pipelines. Credentials **must never** be stored in plain-text YAML files.

Usage in YAML pipelines::

    steps:
      - id: load_db
        tool: InOut.input_data
        args:
          path: ${DATA_PATH}
          connection: ${env:DB_CONNECTION_STRING}

Usage in Python::

    from etlpipe._secrets import resolve_secrets

    raw_config = {\"path\": \"${DATA_PATH}\", \"token\": \"${API_TOKEN}\"}
    safe_config = resolve_secrets(raw_config)

Security notes
--------------
- Environment variables are resolved at *runtime*, never persisted to disk.
- Any referenced variable that is absent raises :class:`SecretResolutionError`
  immediately — there are no silent defaults or empty string fallbacks.
- Values are never logged; only the variable *name* appears in log output.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger("etlpipe.secrets")

# Matches ${VAR_NAME} and ${env:VAR_NAME}
_TOKEN_RE = re.compile(r"\$\{(?:env:)?([A-Za-z_][A-Za-z0-9_]*)\}")


class SecretResolutionError(KeyError):
    """Raised when a referenced environment variable is not set.

    Attributes:
        var_name: The missing environment variable name.
    """

    def __init__(self, var_name: str, context: str = "") -> None:
        self.var_name = var_name
        context_msg = f" (in: {context})" if context else ""
        super().__init__(
            f"Secret resolution failed: environment variable '{var_name}' is not set{context_msg}. "
            "Set it in your shell, .env file, or secret manager before running the pipeline."
        )


def _resolve_string(value: str, context: str = "") -> str:
    """Replace all ``${VAR}`` tokens in *value* with their env-var values.

    Args:
        value: The string potentially containing ``${VAR}`` tokens.
        context: Optional context string used in error messages.

    Returns:
        The string with all tokens replaced.

    Raises:
        SecretResolutionError: If any referenced variable is absent.
    """

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            raise SecretResolutionError(var_name, context)
        logger.debug("Resolved secret token: ${%s} (context: %s)", var_name, context or "unknown")
        return env_value

    return _TOKEN_RE.sub(_replacer, value)


def resolve_secrets(config: Any, _path: str = "root") -> Any:
    """Recursively resolve ``${ENV_VAR}`` tokens in a config structure.

    Walks the entire config tree (dicts, lists, strings) and replaces
    every ``${VAR_NAME}`` or ``${env:VAR_NAME}`` placeholder with the
    corresponding environment variable value.

    Args:
        config: The configuration object to process. May be a ``dict``,
            ``list``, ``str``, or any scalar. Non-string scalars are
            returned unchanged.
        _path: Internal path string used for error context (do not set).

    Returns:
        A deep copy of *config* with all tokens resolved.

    Raises:
        SecretResolutionError: If any referenced environment variable
            is not set. Fails fast on the first missing variable.

    Example::

        >>> import os
        >>> os.environ["DB_PASS"] = "hunter2"
        >>> resolve_secrets({"password": "${DB_PASS}", "port": 5432})
        {'password': 'hunter2', 'port': 5432}
    """
    if isinstance(config, dict):
        return {k: resolve_secrets(v, _path=f"{_path}.{k}") for k, v in config.items()}
    if isinstance(config, list):
        return [resolve_secrets(item, _path=f"{_path}[{i}]") for i, item in enumerate(config)]
    if isinstance(config, str) and _TOKEN_RE.search(config):
        return _resolve_string(config, context=_path)
    return config


def has_unresolved_tokens(config: Any) -> bool:
    """Return ``True`` if any string value in *config* contains unresolved tokens.

    Useful for pre-flight validation of pipeline configs before execution.

    Args:
        config: Any config object (dict, list, str, scalar).

    Returns:
        ``True`` if at least one ``${VAR}`` token is found.

    Example::

        >>> has_unresolved_tokens({"path": "${DATA_PATH}"})
        True
        >>> has_unresolved_tokens({"path": "/data/file.csv"})
        False
    """
    if isinstance(config, dict):
        return any(has_unresolved_tokens(v) for v in config.values())
    if isinstance(config, list):
        return any(has_unresolved_tokens(item) for item in config)
    if isinstance(config, str):
        return bool(_TOKEN_RE.search(config))
    return False
