"""Schema contracts, statistical profiling, and audit suites.

Provides enterprise-grade tools for data quality:

1. **Schema Contracts** — enforce declared column dtypes and nullability
   constraints at pipeline boundaries.  Raises on violations so bad data
   never silently propagates.

2. **Statistical Profiler** — go beyond dtypes with per-column cardinality,
   null-rate, min/max/mean, and top-N value distributions.

3. **ContractSuite** — compose multiple schema checks into a single audit
   run, producing a combined pass/fail report suitable for data governance
   dashboards and pipeline observability.

Example::

    from etlpipe_governance import (
        expect_schema, infer_schema, profile, ContractSuite, SchemaViolationError
    )

    # Bootstrap a schema from known-good data
    schema = infer_schema(good_df)

    # Profile new data
    stats = profile(new_df)

    # Enforce the schema
    try:
        expect_schema(new_df, schema)
    except SchemaViolationError as e:
        print(e.violations)

    # Or run multiple contracts at once
    suite = ContractSuite("Daily Pipeline Audit")
    suite.add_contract("raw_input", raw_schema)
    suite.add_contract("transformed", transform_schema)
    results = suite.run({"raw_input": raw_df, "transformed": transform_df})
    print(results)   # DataFrame with pass/fail per contract
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger("etlpipe_governance.contracts")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SchemaViolationError(Exception):
    """Raised when a DataFrame violates a declared schema contract.

    Attributes:
        violations: List of human-readable violation descriptions.
    """

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        msg = f"Schema contract violated ({len(violations)} issue(s)):\n" + "\n".join(f"  - {v}" for v in violations)
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Dtype matching
# ---------------------------------------------------------------------------

_DTYPE_ALIASES: dict[str, set[str]] = {
    "int": {
        "int8",
        "int16",
        "int32",
        "int64",
        "Int8",
        "Int16",
        "Int32",
        "Int64",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
    },
    "float": {"float16", "float32", "float64", "Float32", "Float64"},
    "str": {"object", "string", "str"},
    "bool": {"bool", "boolean"},
    "datetime": {"datetime64[ns]", "datetime64[ns, UTC]", "datetime64[us]", "datetime64[ms]"},
    "category": {"category"},
}


def _dtype_matches(actual_dtype: str, expected_dtype: str) -> bool:
    """Check if *actual_dtype* matches *expected_dtype*, supporting aliases.

    Supports exact matches (e.g. ``"int64"``), canonical groups
    (e.g. ``"int"`` matches any integer subtype), and ``"any"`` as wildcard.
    """
    if expected_dtype == "any":
        return True
    actual = str(actual_dtype).lower().strip()
    expected = expected_dtype.lower().strip()
    if actual == expected:
        return True
    if expected in _DTYPE_ALIASES:
        return actual in {a.lower() for a in _DTYPE_ALIASES[expected]}
    for aliases in _DTYPE_ALIASES.values():
        lower_aliases = {a.lower() for a in aliases}
        if expected in lower_aliases and actual in lower_aliases:
            return True
    return False


# ---------------------------------------------------------------------------
# Value-level rule checking
# ---------------------------------------------------------------------------


def _check_value_rules(series: pd.Series, col: str, spec: dict[str, Any]) -> list[str]:
    """Check value-level rules for a column against its specification.

    Evaluates ``min_value``, ``max_value``, ``allowed_values``,
    ``value_regex``, ``min_length``, ``max_length``, and ``unique``
    constraints.

    Args:
        series: The column data.
        col: Column name (for violation messages).
        spec: The column specification dict.

    Returns:
        A list of violation description strings (empty if all pass).
    """
    violations: list[str] = []
    non_null = series.dropna()

    # min_value
    min_val = spec.get("min_value")
    if min_val is not None and not non_null.empty:
        try:
            below = non_null[non_null < min_val]
            if not below.empty:
                violations.append(f"Column '{col}': {len(below)} value(s) below min_value={min_val}")
        except TypeError:
            pass  # Non-comparable dtype

    # max_value
    max_val = spec.get("max_value")
    if max_val is not None and not non_null.empty:
        try:
            above = non_null[non_null > max_val]
            if not above.empty:
                violations.append(f"Column '{col}': {len(above)} value(s) above max_value={max_val}")
        except TypeError:
            pass

    # allowed_values
    allowed = spec.get("allowed_values")
    if allowed is not None and not non_null.empty:
        allowed_set = set(allowed)
        invalid = non_null[~non_null.isin(allowed_set)]
        if not invalid.empty:
            sample_bad = invalid.head(3).tolist()
            violations.append(f"Column '{col}': {len(invalid)} value(s) not in allowed_values (e.g. {sample_bad!r})")

    # value_regex
    value_regex = spec.get("value_regex")
    if value_regex is not None and not non_null.empty:
        str_vals = non_null.astype(str)
        mismatches = str_vals[~str_vals.str.fullmatch(value_regex, na=False)]
        if not mismatches.empty:
            sample_bad = mismatches.head(3).tolist()
            violations.append(
                f"Column '{col}': {len(mismatches)} value(s) do not match "
                f"value_regex='{value_regex}' (e.g. {sample_bad!r})"
            )

    # min_length
    min_len = spec.get("min_length")
    if min_len is not None and not non_null.empty:
        str_vals = non_null.astype(str)
        too_short = str_vals[str_vals.str.len() < min_len]
        if not too_short.empty:
            violations.append(f"Column '{col}': {len(too_short)} value(s) shorter than min_length={min_len}")

    # max_length
    max_len = spec.get("max_length")
    if max_len is not None and not non_null.empty:
        str_vals = non_null.astype(str)
        too_long = str_vals[str_vals.str.len() > max_len]
        if not too_long.empty:
            violations.append(f"Column '{col}': {len(too_long)} value(s) longer than max_length={max_len}")

    # unique
    if spec.get("unique") and not non_null.empty:
        dup_count = int(non_null.duplicated().sum())
        if dup_count > 0:
            violations.append(f"Column '{col}': expected unique values but found {dup_count} duplicate(s)")

    return violations


# ---------------------------------------------------------------------------
# infer_schema
# ---------------------------------------------------------------------------


def infer_schema(df: pd.DataFrame) -> dict[str, Any]:
    """Generate a schema dict from a DataFrame for bootstrapping contracts.

    The returned schema can be serialised to JSON/YAML and used with
    :func:`expect_schema` to enforce the same structure on future data.

    Args:
        df: The DataFrame to inspect.

    Returns:
        A dict with ``"columns"`` mapping column names to their dtype
        and nullability.

    Example::

        >>> schema = infer_schema(df)
        >>> schema
        {
            "columns": {
                "ID": {"dtype": "int64", "nullable": False},
                "Name": {"dtype": "object", "nullable": True},
            }
        }
    """
    columns: dict[str, dict[str, Any]] = {}
    for col in df.columns:
        columns[col] = {
            "dtype": str(df[col].dtype),
            "nullable": bool(df[col].isna().any()),
        }
    return {"columns": columns}


# ---------------------------------------------------------------------------
# expect_schema
# ---------------------------------------------------------------------------


def expect_schema(
    df: pd.DataFrame,
    schema: dict[str, Any],
    *,
    strict: bool = True,
) -> pd.DataFrame:
    """Validate a DataFrame against a declared schema contract.

    Args:
        df: The DataFrame to validate.
        schema: A schema dict with a ``"columns"`` key mapping column
            names to ``{"dtype": ..., "nullable": ...}`` specifications.
            Dtype can be an exact pandas dtype string (``"int64"``), a
            canonical group (``"int"``, ``"float"``, ``"str"``), or
            ``"any"`` to skip type checking. Nullable defaults to
            ``True`` if omitted.
        strict: If ``True`` (default), raises :class:`SchemaViolationError`
            on any violation. If ``False``, logs warnings and returns
            the DataFrame unchanged.

    Returns:
        The input DataFrame (unchanged) if validation passes.

    Raises:
        SchemaViolationError: If *strict* is ``True`` and violations are found.
        TypeError: If *df* is not a pandas DataFrame.

    Example::

        >>> expect_schema(df, {
        ...     "columns": {
        ...         "ID": {"dtype": "int64", "nullable": False},
        ...         "Name": {"dtype": "str"},
        ...     }
        ... })
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}.")

    column_specs = schema.get("columns", {})
    if not column_specs:
        logger.warning("Schema contract has no column definitions — skipping validation.")
        return df

    violations: list[str] = []
    expected_cols = set(column_specs.keys())
    actual_cols = set(df.columns)

    for col in sorted(expected_cols - actual_cols):
        violations.append(f"Missing column: '{col}'")

    extra = actual_cols - expected_cols
    if extra:
        logger.debug("Columns not in schema contract (allowed): %s", sorted(extra))

    for col, spec in column_specs.items():
        if col not in actual_cols:
            continue

        expected_dtype = spec.get("dtype")
        if expected_dtype:
            actual_dtype = str(df[col].dtype)
            if not _dtype_matches(actual_dtype, expected_dtype):
                violations.append(f"Column '{col}': expected dtype '{expected_dtype}', got '{actual_dtype}'")

        nullable = spec.get("nullable", True)
        if not nullable and df[col].isna().any():
            null_count = int(df[col].isna().sum())
            violations.append(f"Column '{col}': schema declares non-nullable but found {null_count} null(s)")

        # Value-level rules
        violations.extend(_check_value_rules(df[col], col, spec))

    if violations:
        if strict:
            raise SchemaViolationError(violations)
        for v in violations:
            logger.warning("Schema violation (non-strict): %s", v)

    logger.debug("Schema validation passed: %d columns checked", len(column_specs))
    return df


# ---------------------------------------------------------------------------
# expect_row_count — volume gate
# ---------------------------------------------------------------------------


def expect_row_count(
    df: pd.DataFrame,
    *,
    min_rows: int | None = None,
    max_rows: int | None = None,
    strict: bool = True,
) -> pd.DataFrame:
    """Assert that a DataFrame has an expected number of rows.

    Use this to guard against empty tables, truncated feeds, or
    unexpected data explosions.

    Args:
        df: The DataFrame to check.
        min_rows: Minimum number of rows required (inclusive).
        max_rows: Maximum number of rows allowed (inclusive).
        strict: If ``True`` (default), raises :class:`SchemaViolationError`
            on failure.  If ``False``, logs a warning.

    Returns:
        The input DataFrame (unchanged) if validation passes.

    Raises:
        SchemaViolationError: If *strict* is ``True`` and the row count
            is outside the expected range.

    Example::

        >>> expect_row_count(df, min_rows=1000, max_rows=5_000_000)
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}.")

    violations: list[str] = []
    actual = len(df)

    if min_rows is not None and actual < min_rows:
        violations.append(f"Row count {actual} is below minimum of {min_rows}")
    if max_rows is not None and actual > max_rows:
        violations.append(f"Row count {actual} exceeds maximum of {max_rows}")

    if violations:
        if strict:
            raise SchemaViolationError(violations)
        for v in violations:
            logger.warning("Volume check (non-strict): %s", v)

    return df


# ---------------------------------------------------------------------------
# expect_freshness — staleness gate
# ---------------------------------------------------------------------------


class FreshnessError(Exception):
    """Raised when a datetime column contains data that is too old.

    Attributes:
        column: The column that failed the freshness check.
        max_age: The maximum allowed age.
        actual_age: The actual age of the newest record.
    """

    def __init__(self, column: str, max_age: timedelta, actual_age: timedelta) -> None:
        self.column = column
        self.max_age = max_age
        self.actual_age = actual_age
        super().__init__(
            f"Freshness check failed for column '{column}': newest record is {actual_age} old, max allowed is {max_age}"
        )


def expect_freshness(
    df: pd.DataFrame,
    column: str,
    max_age: timedelta,
    *,
    reference_time: datetime | None = None,
    strict: bool = True,
) -> pd.DataFrame:
    """Assert that a datetime column contains sufficiently recent data.

    Useful for detecting stale feeds, failed ingestion jobs, or timezone
    conversion bugs.

    Args:
        df: The DataFrame to check.
        column: Name of the datetime column to inspect.
        max_age: Maximum allowed age of the newest record.
        reference_time: The reference time to compare against.  Defaults
            to ``datetime.now(timezone.utc)``.
        strict: If ``True`` (default), raises :class:`FreshnessError`
            on failure.  If ``False``, logs a warning.

    Returns:
        The input DataFrame (unchanged) if the check passes.

    Raises:
        FreshnessError: If *strict* is ``True`` and the newest value is
            older than *max_age*.
        KeyError: If *column* is not in the DataFrame.
        TypeError: If *df* is not a pandas DataFrame.

    Example::

        >>> from datetime import timedelta
        >>> expect_freshness(df, column="updated_at", max_age=timedelta(hours=6))
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}.")
    if column not in df.columns:
        raise KeyError(f"Column '{column}' not found in DataFrame.")

    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    series = pd.to_datetime(df[column], errors="coerce").dropna()
    if series.empty:
        logger.warning("Freshness check: column '%s' has no valid datetime values.", column)
        return df

    # Make timezone-aware if needed for comparison
    newest = series.max()
    if newest.tzinfo is None and reference_time.tzinfo is not None:
        newest = newest.tz_localize("UTC")
    elif newest.tzinfo is not None and reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    actual_age = reference_time - newest

    if actual_age > max_age:
        if strict:
            raise FreshnessError(column, max_age, actual_age)
        logger.warning(
            "Freshness check (non-strict): column '%s' newest is %s old (max %s)",
            column,
            actual_age,
            max_age,
        )

    return df


# ---------------------------------------------------------------------------
# profile  — richer than infer_schema, competitive with ydata-profiling
# ---------------------------------------------------------------------------


def profile(
    df: pd.DataFrame,
    *,
    top_n: int = 5,
    sample_size: int | None = None,
) -> pd.DataFrame:
    """Generate a rich statistical profile of a DataFrame.

    Goes beyond :func:`infer_schema` to include per-column cardinality,
    null rate, min/max/mean/std for numerics, and top-N value frequencies
    for categorical columns.

    Args:
        df: The DataFrame to profile.
        top_n: Number of top values to include in the ``Top_Values``
            column. Set to 0 to skip.
        sample_size: If set, sample this many rows before profiling
            (useful for very large DataFrames).

    Returns:
        A DataFrame where each row describes one column.  Columns:

        - ``Column`` — column name
        - ``Dtype`` — pandas dtype string
        - ``Row_Count`` — total rows
        - ``Null_Count`` — number of nulls
        - ``Null_Rate_Pct`` — null percentage (0–100)
        - ``Unique_Count`` — distinct non-null values
        - ``Cardinality_Pct`` — unique / non-null as a percentage
        - ``Min`` — minimum value (numeric only, else ``None``)
        - ``Max`` — maximum value (numeric only, else ``None``)
        - ``Mean`` — mean value (numeric only, else ``None``)
        - ``Std`` — std deviation (numeric only, else ``None``)
        - ``Top_Values`` — top *top_n* values as ``"val (N)"`` strings

    Raises:
        TypeError: If *df* is not a pandas DataFrame.

    Example::

        >>> stats = profile(df)
        >>> print(stats[["Column", "Null_Rate_Pct", "Cardinality_Pct"]])
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}.")

    source = df
    if sample_size is not None and len(df) > sample_size:
        source = df.sample(n=sample_size, random_state=42)
        logger.debug("profile: using %d-row sample (full size: %d)", sample_size, len(df))

    total_rows = len(source)
    rows: list[dict[str, Any]] = []

    for col in source.columns:
        series = source[col]
        null_count = int(series.isna().sum())
        non_null = series.dropna()
        null_rate = round(null_count / total_rows * 100, 2) if total_rows > 0 else 0.0
        unique_count = int(non_null.nunique())
        non_null_count = len(non_null)
        cardinality_pct = round(unique_count / non_null_count * 100, 2) if non_null_count > 0 else 0.0

        # Numeric stats
        col_min = col_max = col_mean = col_std = None
        if pd.api.types.is_numeric_dtype(series) and non_null_count > 0:
            col_min = round(float(non_null.min()), 6)
            col_max = round(float(non_null.max()), 6)
            col_mean = round(float(non_null.mean()), 6)
            col_std = round(float(non_null.std()), 6) if non_null_count > 1 else 0.0

        # Top-N values
        top_values_str = ""
        if top_n > 0 and non_null_count > 0:
            vc = non_null.value_counts().head(top_n)
            top_values_str = ", ".join(f"{v} ({c})" for v, c in vc.items())

        rows.append(
            {
                "Column": col,
                "Dtype": str(series.dtype),
                "Row_Count": total_rows,
                "Null_Count": null_count,
                "Null_Rate_Pct": null_rate,
                "Unique_Count": unique_count,
                "Cardinality_Pct": cardinality_pct,
                "Min": col_min,
                "Max": col_max,
                "Mean": col_mean,
                "Std": col_std,
                "Top_Values": top_values_str,
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# ContractSuite — batch contract runner for pipeline audit checkpoints
# ---------------------------------------------------------------------------


class ContractSuite:
    """Run multiple schema contracts in a single audit pass.

    Produces a combined pass/fail report suitable for data governance
    dashboards, CI/CD pipeline gates, and observability tooling.

    Example::

        suite = ContractSuite("Daily Pipeline Audit")
        suite.add_contract("raw_sales", raw_schema)
        suite.add_contract("cleaned_sales", cleaned_schema)

        results = suite.run({
            "raw_sales": raw_df,
            "cleaned_sales": cleaned_df,
        })

        # results is a DataFrame with one row per contract
        print(results[["Contract", "Status", "Violation_Count"]])
    """

    def __init__(self, name: str = "Unnamed Suite") -> None:
        """Initialise a new ContractSuite.

        Args:
            name: Human-readable name for this audit suite (used in reports).
        """
        self.name = name
        self._contracts: dict[str, dict[str, Any]] = {}
        self._volume_checks: dict[str, dict[str, Any]] = {}
        self._freshness_checks: dict[str, dict[str, Any]] = {}

    def add_contract(
        self,
        contract_id: str,
        schema: dict[str, Any],
        *,
        strict: bool = True,
        description: str = "",
    ) -> ContractSuite:
        """Register a schema contract with the suite.

        Args:
            contract_id: Unique identifier for this contract within the suite.
                Must match a key in the dict passed to :meth:`run`.
            schema: Schema dict as produced by :func:`infer_schema` or
                manually constructed (see :func:`expect_schema`).
            strict: If ``True`` (default), a violation causes the suite to
                mark this contract as ``"FAIL"``. If ``False``, violations
                are recorded but do not block downstream steps.
            description: Optional human-readable description of what this
                contract guards.

        Returns:
            *self*, enabling method chaining.

        Example::

            suite.add_contract("input", schema_a).add_contract("output", schema_b)
        """
        if contract_id in self._contracts:
            logger.warning("Contract '%s' is being overwritten in suite '%s'.", contract_id, self.name)
        self._contracts[contract_id] = {
            "schema": schema,
            "strict": strict,
            "description": description,
        }
        return self

    def add_volume_check(
        self,
        contract_id: str,
        *,
        min_rows: int | None = None,
        max_rows: int | None = None,
        description: str = "",
    ) -> ContractSuite:
        """Register a row-count volume check for a dataset.

        Args:
            contract_id: Identifier matching a key in the dict passed to :meth:`run`.
            min_rows: Minimum number of rows required (inclusive).
            max_rows: Maximum number of rows allowed (inclusive).
            description: Optional description.

        Returns:
            *self*, enabling method chaining.
        """
        self._volume_checks[contract_id] = {
            "min_rows": min_rows,
            "max_rows": max_rows,
            "description": description or f"Volume check: {min_rows}–{max_rows} rows",
        }
        return self

    def add_freshness_check(
        self,
        contract_id: str,
        column: str,
        max_age: timedelta,
        *,
        description: str = "",
    ) -> ContractSuite:
        """Register a freshness check for a datetime column.

        Args:
            contract_id: Identifier matching a key in the dict passed to :meth:`run`.
            column: Datetime column to inspect.
            max_age: Maximum allowed age of the newest record.
            description: Optional description.

        Returns:
            *self*, enabling method chaining.
        """
        self._freshness_checks[contract_id] = {
            "column": column,
            "max_age": max_age,
            "description": description or f"Freshness check: {column} within {max_age}",
        }
        return self

    def run(
        self,
        dataframes: dict[str, pd.DataFrame],
        *,
        raise_on_failure: bool = False,
        audit_trail: Any = None,
        run_id: str | None = None,
    ) -> pd.DataFrame:
        """Execute all registered contracts against the provided DataFrames.

        Args:
            dataframes: A mapping of ``{contract_id: DataFrame}`` to validate.
                Contract IDs must match those registered via :meth:`add_contract`.
                Extra keys in *dataframes* that have no registered contract are
                silently ignored.
            raise_on_failure: If ``True``, raises :class:`SchemaViolationError`
                after running all contracts if any ``"FAIL"`` result exists.
                If ``False`` (default), all results are collected and returned
                regardless of outcome.
            audit_trail: Optional :class:`AuditTrail` instance.  If provided,
                the results DataFrame is automatically logged.
            run_id: Optional run identifier for audit trail logging.

        Returns:
            A DataFrame with one row per contract containing:

            - ``Suite`` — the suite name
            - ``Contract`` — the contract ID
            - ``Description`` — the human-readable description
            - ``Status`` — ``"PASS"`` or ``"FAIL"`` or ``"SKIPPED"``
                (if the DataFrame was not provided)
            - ``Violation_Count`` — number of violations found (0 on pass)
            - ``Violations`` — newline-joined list of violation messages

        Raises:
            SchemaViolationError: If *raise_on_failure* is ``True`` and any
                contract fails.

        Example::

            results = suite.run({"raw": df1, "cleaned": df2})
            failed = results[results["Status"] == "FAIL"]
        """
        report_rows: list[dict[str, Any]] = []

        for contract_id, config in self._contracts.items():
            schema = config["schema"]
            strict = config["strict"]
            description = config["description"]

            if contract_id not in dataframes:
                report_rows.append(
                    {
                        "Suite": self.name,
                        "Contract": contract_id,
                        "Description": description,
                        "Status": "SKIPPED",
                        "Violation_Count": 0,
                        "Violations": "",
                    }
                )
                logger.warning(
                    "Suite '%s': contract '%s' skipped — no DataFrame provided.",
                    self.name,
                    contract_id,
                )
                continue

            df = dataframes[contract_id]
            try:
                expect_schema(df, schema, strict=True)
                report_rows.append(
                    {
                        "Suite": self.name,
                        "Contract": contract_id,
                        "Description": description,
                        "Status": "PASS",
                        "Violation_Count": 0,
                        "Violations": "",
                    }
                )
                logger.info("Suite '%s': contract '%s' PASSED.", self.name, contract_id)
            except SchemaViolationError as exc:
                status = "FAIL" if strict else "WARN"
                report_rows.append(
                    {
                        "Suite": self.name,
                        "Contract": contract_id,
                        "Description": description,
                        "Status": status,
                        "Violation_Count": len(exc.violations),
                        "Violations": "\n".join(exc.violations),
                    }
                )
                logger.warning(
                    "Suite '%s': contract '%s' %s (%d violation(s)).",
                    self.name,
                    contract_id,
                    status,
                    len(exc.violations),
                )
            except TypeError as exc:
                report_rows.append(
                    {
                        "Suite": self.name,
                        "Contract": contract_id,
                        "Description": description,
                        "Status": "ERROR",
                        "Violation_Count": 0,
                        "Violations": str(exc),
                    }
                )

        # --- Volume checks ---
        for contract_id, config in self._volume_checks.items():
            description = config["description"]
            if contract_id not in dataframes:
                report_rows.append(
                    {
                        "Suite": self.name,
                        "Contract": f"{contract_id}:volume",
                        "Description": description,
                        "Status": "SKIPPED",
                        "Violation_Count": 0,
                        "Violations": "",
                    }
                )
                continue
            df = dataframes[contract_id]
            try:
                expect_row_count(
                    df,
                    min_rows=config["min_rows"],
                    max_rows=config["max_rows"],
                    strict=True,
                )
                report_rows.append(
                    {
                        "Suite": self.name,
                        "Contract": f"{contract_id}:volume",
                        "Description": description,
                        "Status": "PASS",
                        "Violation_Count": 0,
                        "Violations": "",
                    }
                )
            except SchemaViolationError as exc:
                report_rows.append(
                    {
                        "Suite": self.name,
                        "Contract": f"{contract_id}:volume",
                        "Description": description,
                        "Status": "FAIL",
                        "Violation_Count": len(exc.violations),
                        "Violations": "\n".join(exc.violations),
                    }
                )

        # --- Freshness checks ---
        for contract_id, config in self._freshness_checks.items():
            description = config["description"]
            if contract_id not in dataframes:
                report_rows.append(
                    {
                        "Suite": self.name,
                        "Contract": f"{contract_id}:freshness",
                        "Description": description,
                        "Status": "SKIPPED",
                        "Violation_Count": 0,
                        "Violations": "",
                    }
                )
                continue
            df = dataframes[contract_id]
            try:
                expect_freshness(
                    df,
                    column=config["column"],
                    max_age=config["max_age"],
                    strict=True,
                )
                report_rows.append(
                    {
                        "Suite": self.name,
                        "Contract": f"{contract_id}:freshness",
                        "Description": description,
                        "Status": "PASS",
                        "Violation_Count": 0,
                        "Violations": "",
                    }
                )
            except FreshnessError as exc:
                report_rows.append(
                    {
                        "Suite": self.name,
                        "Contract": f"{contract_id}:freshness",
                        "Description": description,
                        "Status": "FAIL",
                        "Violation_Count": 1,
                        "Violations": str(exc),
                    }
                )

        result_df = pd.DataFrame(
            report_rows,
            columns=["Suite", "Contract", "Description", "Status", "Violation_Count", "Violations"],
        )

        # --- Audit trail ---
        if audit_trail is not None:
            audit_trail.log(result_df, run_id=run_id, suite_name=self.name)

        if raise_on_failure:
            failed = result_df[result_df["Status"] == "FAIL"]
            if not failed.empty:
                all_violations = []
                for _, row in failed.iterrows():
                    for v in row["Violations"].split("\n"):
                        if v:
                            all_violations.append(f"[{row['Contract']}] {v}")
                raise SchemaViolationError(all_violations)

        return result_df

    def __len__(self) -> int:
        """Return the number of registered contracts."""
        return len(self._contracts) + len(self._volume_checks) + len(self._freshness_checks)

    def __repr__(self) -> str:
        return f"ContractSuite(name={self.name!r}, contracts={list(self._contracts.keys())})"
