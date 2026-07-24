"""PII (Personally Identifiable Information) scanner and masker.

Provides automated detection of columns that may contain sensitive
personal data â€” a critical requirement for GDPR, HIPAA, SOX, CCPA,
and other regulatory compliance frameworks used in enterprise deployments.

Two-step workflow::

    from etlpipe_governance import scan_pii, mask_pii

    # Step 1: detect
    report = scan_pii(df)

    # Step 2: mask before persisting / sharing
    safe_df = mask_pii(df, report, strategy="redact")
    hashed_df = mask_pii(df, report, strategy="hash")
    pseudo_df = mask_pii(df, report, strategy="pseudonymise")

Masking strategies
------------------
``"redact"``
    Replaces every value in flagged columns with ``"***REDACTED***"``.
    Safe for audit logs and debugging output.

``"hash"``
    Replaces each value with the first 12 characters of its SHA-256
    hex digest (deterministic â€” same input always produces the same
    token). Useful for referential integrity checks without exposing
    raw PII.

``"pseudonymise"``
    Replaces each *unique* value with a type-prefixed label such as
    ``PERSON_1``, ``EMAIL_1``, ``PHONE_2``.  The mapping is
    deterministic within a single call and returned as a second value.
    Suitable for synthetic data generation and ML training sets.
"""

from __future__ import annotations

import hashlib
import logging
import re
import warnings
from typing import Any

import pandas as pd

logger = logging.getLogger("etlpipe_governance.pii")


class PIIWarning(UserWarning):
    """Warning emitted when potential PII is detected in a DataFrame."""


# ---------------------------------------------------------------------------
# Default PII detection patterns (international coverage)
# ---------------------------------------------------------------------------
_DEFAULT_PATTERNS: dict[str, dict[str, Any]] = {
    "email": {
        "value_regex": r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        "name_regex": r"(?i)(e[\-_]?mail|email[\-_]?addr)",
        "description": "Email address",
    },
    "phone_us": {
        "value_regex": r"(?:\+?1[\-.\s]?)?\(?\d{3}\)?[\-.\s]?\d{3}[\-.\s]?\d{4}",
        "name_regex": r"(?i)(phone|tel|mobile|cell|fax)",
        "description": "US phone number",
    },
    "phone_intl": {
        "value_regex": r"\+\d{1,3}[\-.\s]?\d{4,14}",
        "name_regex": r"(?i)(phone|tel|mobile|cell)",
        "description": "International phone number",
    },
    "ssn": {
        "value_regex": r"\b\d{3}[\-\s]?\d{2}[\-\s]?\d{4}\b",
        "name_regex": r"(?i)(ssn|social[\-_\s]?sec|tax[\-_\s]?id)",
        "description": "US Social Security Number",
    },
    "credit_card": {
        "value_regex": r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[- ]?\d{4}[- ]?\d{4}[- ]?\d{3,4}\b",
        "name_regex": r"(?i)(credit[\-_\s]?card|cc[\-_\s]?num|card[\-_\s]?num|pan)",
        "description": "Credit card number",
    },
    "ip_address": {
        "value_regex": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "name_regex": r"(?i)(ip[\-_\s]?addr|ip[\-_\s]?address|client[\-_\s]?ip|src[\-_\s]?ip)",
        "description": "IPv4 address",
    },
    "aadhaar": {
        "value_regex": r"\b\d{4}[\-\s]?\d{4}[\-\s]?\d{4}\b",
        "name_regex": r"(?i)(aadhaar|aadhar|uid)",
        "description": "Indian Aadhaar number",
    },
    "iban": {
        "value_regex": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b",
        "name_regex": r"(?i)(iban|bank[\-_\s]?acct|account[\-_\s]?num)",
        "description": "International Bank Account Number (IBAN)",
    },
    "date_of_birth": {
        "value_regex": None,  # Dates are too ambiguous for value scanning
        "name_regex": r"(?i)(dob|date[\-_\s]?of[\-_\s]?birth|birth[\-_\s]?date|birthday)",
        "description": "Date of birth",
    },
    "passport": {
        "value_regex": r"\b[A-Z]{1,2}\d{6,9}\b",
        "name_regex": r"(?i)(passport[\-_\s]?num|passport[\-_\s]?no|passport[\-_\s]?id)",
        "description": "Passport number",
    },
    "name_field": {
        "value_regex": None,  # Names can't be reliably detected by regex
        "name_regex": (
            r"(?i)^(first[\-_\s]?name|last[\-_\s]?name|full[\-_\s]?name|"
            r"surname|given[\-_\s]?name|family[\-_\s]?name)$"
        ),
        "description": "Person name field",
    },
    "address": {
        "value_regex": None,
        "name_regex": (
            r"(?i)(street[\-_\s]?addr|address[\-_\s]?line|postal[\-_\s]?addr|"
            r"home[\-_\s]?addr|mailing[\-_\s]?addr)"
        ),
        "description": "Physical address",
    },
}

# Prefix labels used by the pseudonymise strategy, keyed by PII type
_PSEUDO_LABELS: dict[str, str] = {
    "email": "EMAIL",
    "phone_us": "PHONE",
    "phone_intl": "PHONE",
    "ssn": "SSN",
    "credit_card": "CARD",
    "ip_address": "IP",
    "aadhaar": "UID",
    "iban": "IBAN",
    "date_of_birth": "DOB",
    "passport": "PASSPORT",
    "name_field": "PERSON",
    "address": "ADDRESS",
}


# ---------------------------------------------------------------------------
# scan_pii
# ---------------------------------------------------------------------------


def scan_pii(
    df: pd.DataFrame,
    *,
    patterns: dict[str, dict[str, Any]] | None = None,
    sample_size: int = 100,
    warn: bool = True,
) -> pd.DataFrame:
    """Scan a DataFrame for columns potentially containing PII.

    Checks both **column names** (against name patterns) and
    **sample values** (against value regex patterns) to detect
    sensitive data.

    Args:
        df: The DataFrame to scan.
        patterns: Custom PII pattern definitions. If ``None``, uses
            built-in patterns covering email, phone, SSN, credit card,
            IP address, Aadhaar, IBAN, passport, DOB, name, and address.
            Each pattern dict should have keys: ``value_regex`` (str or None),
            ``name_regex`` (str or None), ``description`` (str).
        sample_size: Number of non-null values to sample per column for
            value-based scanning. Higher values increase accuracy but
            reduce performance.
        warn: If ``True``, emits a :class:`PIIWarning` for each detected
            PII column.

    Returns:
        A DataFrame with columns: ``Column``, ``PII_Type``,
        ``Detection_Method``, ``Confidence``, ``Sample_Match``,
        ``Description``.

    Example::

        >>> report = scan_pii(df)
        >>> print(report[["Column", "PII_Type", "Confidence"]])
           Column    PII_Type Confidence
        0   Email       email       high
        1  Phone    phone_us     medium
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}.")

    active_patterns = patterns if patterns is not None else _DEFAULT_PATTERNS
    findings: list[dict[str, Any]] = []

    for col in df.columns:
        for pii_type, pattern_def in active_patterns.items():
            name_regex = pattern_def.get("name_regex")
            value_regex = pattern_def.get("value_regex")
            description = pattern_def.get("description", pii_type)

            # --- Column name check ---
            if name_regex and re.search(name_regex, col):
                findings.append(
                    {
                        "Column": col,
                        "PII_Type": pii_type,
                        "Detection_Method": "column_name",
                        "Confidence": "high",
                        "Sample_Match": col,
                        "Description": description,
                    }
                )
                continue  # Don't double-flag same column for same PII type

            # --- Value check (string columns only) ---
            if value_regex and df[col].dtype == "object":
                sample = df[col].dropna().head(sample_size).astype(str)
                if sample.empty:
                    continue
                matches = sample[sample.str.contains(value_regex, regex=True, na=False)]
                if not matches.empty:
                    match_pct = len(matches) / len(sample)
                    confidence = "high" if match_pct > 0.5 else "medium" if match_pct > 0.1 else "low"
                    findings.append(
                        {
                            "Column": col,
                            "PII_Type": pii_type,
                            "Detection_Method": "value_pattern",
                            "Confidence": confidence,
                            "Sample_Match": str(matches.iloc[0]),
                            "Description": description,
                        }
                    )

    report = pd.DataFrame(
        findings,
        columns=["Column", "PII_Type", "Detection_Method", "Confidence", "Sample_Match", "Description"],
    )

    if warn and not report.empty:
        high_confidence = report[report["Confidence"].isin(["high", "medium"])]
        if not high_confidence.empty:
            pii_summary = ", ".join(f"{row['Column']} ({row['PII_Type']})" for _, row in high_confidence.iterrows())
            warnings.warn(
                f"Potential PII detected in {len(high_confidence)} column(s): {pii_summary}. "
                f"Review with scan_pii() and apply masking before production use.",
                PIIWarning,
                stacklevel=2,
            )

    logger.info(
        "PII scan complete: %d column(s) scanned, %d finding(s)",
        len(df.columns),
        len(report),
    )
    return report


# ---------------------------------------------------------------------------
# mask_pii  â€” the competitive differentiator vs Pandera / Great Expectations
# ---------------------------------------------------------------------------


def mask_pii(
    df: pd.DataFrame,
    report: pd.DataFrame,
    strategy: str = "redact",
    *,
    redact_value: str = "***REDACTED***",
    hash_length: int = 12,
    min_confidence: str = "low",
    columns: list[str] | None = None,
) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    """Mask PII columns in a DataFrame using the specified strategy.

    This is the critical missing piece in tools like Great Expectations â€”
    it not only detects PII but makes it safe to use downstream.

    Args:
        df: The original DataFrame (unchanged).
        report: The PII scan report produced by :func:`scan_pii`.
        strategy: Masking strategy. One of:

            ``"redact"``
                Replaces all values with *redact_value* (default
                ``"***REDACTED***"``). Irreversible. Best for audit logs.

            ``"hash"``
                Replaces each value with the first *hash_length*
                characters of its SHA-256 hex digest.  Deterministic
                and referentially consistent â€” the same raw value always
                maps to the same hash.  Use for joining masked datasets.

            ``"pseudonymise"``
                Assigns a type-prefixed label (e.g. ``EMAIL_1``,
                ``PERSON_2``) to each unique value. Maintains row-level
                referential integrity. Returns a ``tuple`` of
                ``(masked_df, mapping_dict)`` where *mapping_dict* maps
                column â†’ {original_value â†’ pseudo_label}.  The caller
                is responsible for storing the mapping securely.

        redact_value: Replacement string for the ``"redact"`` strategy.
        hash_length: Number of hex characters to keep for ``"hash"``.
        min_confidence: Minimum confidence level (``"low"``, ``"medium"``,
            ``"high"``) of findings to include in masking.
        columns: If provided, only mask these specific columns (overrides
            the report-driven column list).

    Returns:
        For ``"pseudonymise"``: a ``tuple`` of ``(masked_df, mapping)``.
        For all other strategies: just the masked ``DataFrame``.

    Raises:
        TypeError: If *df* is not a pandas DataFrame.
        ValueError: If *strategy* is not a supported value.

    Example::

        >>> report = scan_pii(df)
        >>> safe_df = mask_pii(df, report, strategy="redact")
        >>> hashed_df = mask_pii(df, report, strategy="hash")
        >>> pseudo_df, mapping = mask_pii(df, report, strategy="pseudonymise")
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}.")

    valid_strategies = {"redact", "hash", "pseudonymise"}
    if strategy not in valid_strategies:
        raise ValueError(f"strategy must be one of {sorted(valid_strategies)!r}, got {strategy!r}.")

    confidence_order = {"low": 0, "medium": 1, "high": 2}
    min_level = confidence_order.get(min_confidence, 0)

    # Determine which columns to mask
    if columns is not None:
        cols_to_mask = [c for c in columns if c in df.columns]
    else:
        if report.empty:
            return (df.copy(), {}) if strategy == "pseudonymise" else df.copy()
        filtered = report[report["Confidence"].map(lambda c: confidence_order.get(c, 0) >= min_level)]
        cols_to_mask = filtered["Column"].unique().tolist()

    result = df.copy()
    pii_type_map: dict[str, str] = {}
    if not report.empty:
        for _, row in report.iterrows():
            if row["Column"] not in pii_type_map:
                pii_type_map[row["Column"]] = row["PII_Type"]

    # --- Apply masking strategy ---
    if strategy == "redact":
        for col in cols_to_mask:
            if col in result.columns:
                result[col] = redact_value
        logger.info("Redacted %d column(s)", len(cols_to_mask))
        return result

    elif strategy == "hash":
        for col in cols_to_mask:
            if col in result.columns:
                result[col] = result[col].apply(lambda v: _sha256_token(str(v), hash_length) if pd.notna(v) else v)
        logger.info("Hashed %d column(s) (length=%d)", len(cols_to_mask), hash_length)
        return result

    else:  # pseudonymise
        mapping: dict[str, dict[str, str]] = {}
        for col in cols_to_mask:
            if col not in result.columns:
                continue
            pii_type = pii_type_map.get(col, "VALUE")
            label_prefix = _PSEUDO_LABELS.get(pii_type, "VALUE")
            col_mapping: dict[str, str] = {}
            counter = 1

            def _pseudo(v, _col_mapping=col_mapping, _label_prefix=label_prefix):
                if pd.isna(v):
                    return v
                sv = str(v)
                if sv not in _col_mapping:
                    nonlocal counter
                    _col_mapping[sv] = f"{_label_prefix}_{counter}"
                    counter += 1
                return _col_mapping[sv]

            result[col] = result[col].apply(_pseudo)
            mapping[col] = col_mapping

        logger.info("Pseudonymised %d column(s)", len(cols_to_mask))
        return result, mapping


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_token(value: str, length: int = 12) -> str:
    """Return the first *length* hex chars of the SHA-256 digest of *value*."""
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:length]
