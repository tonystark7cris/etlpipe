"""PII (Personally Identifiable Information) scanner and masker.

Provides automated detection of columns that may contain sensitive
personal data — a critical requirement for GDPR, HIPAA, SOX, CCPA,
PCI-DSS, and other regulatory compliance frameworks used in enterprise
financial deployments.

Two-step workflow::

    from etlpipe_governance import scan_pii, mask_pii

    # Step 1: detect
    report = scan_pii(df)

    # Step 2: mask before persisting / sharing
    safe_df = mask_pii(df, report, strategy="redact")
    hashed_df = mask_pii(df, report, strategy="hash")
    pseudo_df, mapping = mask_pii(df, report, strategy="pseudonymise")

    # Step 3 (pseudonymise only): store mapping securely
    from etlpipe_governance.pii import save_mapping, load_mapping
    save_mapping(mapping, "mappings/daily.enc", encrypt_key=os.environ["MAPPING_KEY"])

Masking strategies
------------------
``"redact"``
    Replaces every value in flagged columns with ``"***REDACTED***"``.
    Safe for audit logs and debugging output.

``"hash"``
    Replaces each value with the first 12 characters of its SHA-256
    hex digest (deterministic — same input always produces the same
    token). Useful for referential integrity checks without exposing
    raw PII.

``"pseudonymise"``
    Replaces each *unique* value with a type-prefixed label such as
    ``PERSON_1``, ``EMAIL_1``, ``PHONE_2``.  The mapping is
    deterministic within a single call and returned as a second value.
    The caller is responsible for storing the mapping securely —
    use :func:`save_mapping` with ``encrypt_key`` for AES-256 storage.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
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
    # ---- General personal data ----
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
    # ---- Banking & financial sector patterns (JPMorgan / BoA / Big 4 grade) ----
    "routing_number": {
        "value_regex": r"\b0[0-9]{2}[0-9]{6}\b|\b[123678][0-9]{7}\b",  # 9-digit ABA format
        "name_regex": r"(?i)(routing[\-_\s]?num|aba[\-_\s]?routing|rtn|transit[\-_\s]?num)",
        "description": "US ABA bank routing number",
    },
    "account_number": {
        "value_regex": r"\b\d{6,17}\b",  # 6–17 digit bank account number
        "name_regex": (
            r"(?i)(acct[\-_\s]?num|account[\-_\s]?number|bank[\-_\s]?account|"
            r"deposit[\-_\s]?acct|checking[\-_\s]?acct|savings[\-_\s]?acct)"
        ),
        "description": "Bank account number",
    },
    "swift_bic": {
        "value_regex": r"\b[A-Z]{4}[A-Z]{2}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3})?\b",
        "name_regex": r"(?i)(swift|bic[\-_\s]?code|swift[\-_\s]?code|bank[\-_\s]?id[\-_\s]?code)",
        "description": "SWIFT/BIC bank identifier code",
    },
    "pan_masked": {
        "value_regex": r"\b[*Xx\d]{4}[\-\s]?[*Xx\d]{4}[\-\s]?[*Xx\d]{4}[\-\s]?\d{4}\b",
        "name_regex": r"(?i)(masked[\-_\s]?pan|pan[\-_\s]?mask|card[\-_\s]?mask|last[\-_\s]?4)",
        "description": "Masked payment card number (PCI-DSS)",
    },
    "sort_code": {
        "value_regex": r"\b\d{2}[\-]\d{2}[\-]\d{2}\b",
        "name_regex": r"(?i)(sort[\-_\s]?code|sort[\-_\s]?num|uk[\-_\s]?sort)",
        "description": "UK bank sort code",
    },
    "bsb_number": {
        "value_regex": r"\b\d{3}[\-]\d{3}\b",
        "name_regex": r"(?i)(bsb[\-_\s]?num|bsb[\-_\s]?code|au[\-_\s]?bsb)",
        "description": "Australian BSB (Bank State Branch) code",
    },
    "tax_id_ein": {
        "value_regex": r"\b\d{2}[\-]\d{7}\b",
        "name_regex": r"(?i)(ein|employer[\-_\s]?id|tax[\-_\s]?id[\-_\s]?num|tin[\-_\s]?num|federal[\-_\s]?tax)",
        "description": "US Employer Identification Number (EIN/TIN)",
    },
    "internal_cust_id": {
        "value_regex": None,  # Pattern too institution-specific for value regex
        "name_regex": (
            r"(?i)(cust[\-_\s]?id|customer[\-_\s]?id|client[\-_\s]?id|"
            r"cif[\-_\s]?num|party[\-_\s]?id|member[\-_\s]?id|account[\-_\s]?holder[\-_\s]?id)"
        ),
        "description": "Internal customer / CIF identifier",
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
    # Banking extensions
    "routing_number": "ROUTING",
    "account_number": "ACCOUNT",
    "swift_bic": "SWIFT",
    "pan_masked": "PAN",
    "sort_code": "SORT",
    "bsb_number": "BSB",
    "tax_id_ein": "EIN",
    "internal_cust_id": "CUST",
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
# mask_pii  — the competitive differentiator vs Pandera / Great Expectations
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

    This is the critical missing piece in tools like Great Expectations —
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
                and referentially consistent — the same raw value always
                maps to the same hash.  Use for joining masked datasets.

            ``"pseudonymise"``
                Assigns a type-prefixed label (e.g. ``EMAIL_1``,
                ``PERSON_2``) to each unique value. Maintains row-level
                referential integrity. Returns a ``tuple`` of
                ``(masked_df, mapping_dict)`` where *mapping_dict* maps
                column → {original_value → pseudo_label}.  The caller
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


# ---------------------------------------------------------------------------
# Secure pseudonymise mapping storage (Component 8)
# ---------------------------------------------------------------------------


class MappingSecurityWarning(UserWarning):
    """Warning emitted when a pseudonymise mapping is stored without encryption."""


def save_mapping(
    mapping: dict[str, dict[str, str]],
    path: str,
    *,
    encrypt_key: str | None = None,
) -> None:
    """Persist a pseudonymise mapping to disk, optionally with AES-256-GCM encryption.

    The mapping returned by :func:`mask_pii` with ``strategy="pseudonymise"``
    contains original PII values as dict keys and **must be stored securely**.
    Use ``encrypt_key`` to encrypt it at rest using AES-256-GCM via the
    ``cryptography`` library.

    Args:
        mapping: The mapping dict returned by ``mask_pii(..., strategy="pseudonymise")``.
        path: File path to write the mapping to. The directory is created
            automatically if it does not exist.
        encrypt_key: A secret key string used to derive an AES-256 key via
            PBKDF2-HMAC-SHA256 (480,000 iterations, NIST-recommended). Store
            this key in your bank's secret manager (AWS Secrets Manager, Azure
            Key Vault, HashiCorp Vault) -- never on disk. If ``None``, the
            mapping is written as plain JSON and a :class:`MappingSecurityWarning`
            is emitted.

    Raises:
        ImportError: If ``encrypt_key`` is provided but the ``cryptography``
            package is not installed (``pip install cryptography``).

    Example::

        >>> key = os.environ["MAPPING_ENCRYPTION_KEY"]
        >>> pseudo_df, mapping = mask_pii(df, report, strategy="pseudonymise")
        >>> save_mapping(mapping, "mappings/2026-08-17.enc", encrypt_key=key)
    """
    import pathlib

    dest = pathlib.Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(mapping, ensure_ascii=False)

    if encrypt_key is None:
        warnings.warn(
            "save_mapping: mapping is being stored as PLAIN TEXT (no encrypt_key provided). "
            "Pseudonymise mappings contain original PII values and must be encrypted at rest. "
            "Pass encrypt_key=os.environ['MAPPING_KEY'] to enable AES-256-GCM encryption.",
            MappingSecurityWarning,
            stacklevel=2,
        )
        dest.write_text(payload, encoding="utf-8")
        logger.warning("Pseudonymise mapping saved WITHOUT encryption to %s", dest)
        return

    try:
        import base64

        from cryptography.hazmat.primitives import hashes as crypto_hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError as exc:
        raise ImportError(
            "The 'cryptography' package is required for encrypted mapping storage. "
            "Install it with: pip install cryptography"
        ) from exc

    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=crypto_hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    key_bytes = kdf.derive(encrypt_key.encode("utf-8"))
    nonce = os.urandom(12)
    aesgcm = AESGCM(key_bytes)
    ciphertext = aesgcm.encrypt(nonce, payload.encode("utf-8"), None)

    blob = base64.b64encode(salt + nonce + ciphertext).decode("ascii")
    dest.write_text(blob, encoding="ascii")
    logger.info("Pseudonymise mapping saved with AES-256-GCM encryption to %s", dest)


def load_mapping(
    path: str,
    *,
    encrypt_key: str | None = None,
) -> dict[str, dict[str, str]]:
    """Load a pseudonymise mapping previously saved with :func:`save_mapping`.

    Args:
        path: Path to the mapping file.
        encrypt_key: The same key used when calling :func:`save_mapping`.
            Required if the file was encrypted; omit for plain-text files.

    Returns:
        The original mapping dict ``{column: {original_value: pseudo_label}}``.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ImportError: If ``encrypt_key`` is provided but ``cryptography`` is not installed.
        ValueError: If decryption fails (wrong key or corrupted file).

    Example::

        >>> key = os.environ["MAPPING_ENCRYPTION_KEY"]
        >>> mapping = load_mapping("mappings/2026-08-17.enc", encrypt_key=key)
    """
    import pathlib

    src = pathlib.Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Mapping file not found: {src}")

    content = src.read_text(encoding="utf-8" if encrypt_key is None else "ascii").strip()

    if encrypt_key is None:
        return json.loads(content)

    try:
        import base64

        from cryptography.hazmat.primitives import hashes as crypto_hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError as exc:
        raise ImportError(
            "The 'cryptography' package is required for encrypted mapping loading. "
            "Install it with: pip install cryptography"
        ) from exc

    raw = base64.b64decode(content)
    salt, nonce, ciphertext = raw[:16], raw[16:28], raw[28:]
    kdf = PBKDF2HMAC(
        algorithm=crypto_hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    key_bytes = kdf.derive(encrypt_key.encode("utf-8"))
    aesgcm = AESGCM(key_bytes)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ValueError(
            "Mapping decryption failed -- wrong key or corrupted file. "
            "Ensure you are using the same encrypt_key that was used to save the mapping."
        ) from exc

    logger.info("Pseudonymise mapping loaded and decrypted from %s", src)
    return json.loads(plaintext.decode("utf-8"))
