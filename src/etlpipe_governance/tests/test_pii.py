"""Tests for etlpipe_governance.pii â€” PII detection and masking."""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

from etlpipe_governance.pii import PIIWarning, _sha256_token, mask_pii, scan_pii

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pii_df() -> pd.DataFrame:
    """DataFrame containing various PII types."""
    return pd.DataFrame(
        {
            "email": ["alice@example.com", "bob@test.org", "charlie@corp.co"],
            "Phone": ["+1-555-123-4567", "555.987.6543", "(800) 555-0199"],
            "SSN": ["123-45-6789", "987-65-4321", "111-22-3333"],
            "CreditCard": ["4111-1111-1111-1111", "5500-0000-0000-0004", "3782 822463 10005"],
            "IP_Address": ["192.168.1.1", "10.0.0.255", "172.16.0.1"],
            "Notes": ["Regular text", "Nothing sensitive", "Just some notes"],
        }
    )


@pytest.fixture
def clean_df() -> pd.DataFrame:
    """DataFrame with no PII."""
    return pd.DataFrame(
        {
            "product_id": [101, 102, 103],
            "quantity": [5, 10, 15],
            "price": [29.99, 49.99, 9.99],
            "category": ["Electronics", "Books", "Toys"],
        }
    )


@pytest.fixture
def indian_pii_df() -> pd.DataFrame:
    """DataFrame with Indian PII (Aadhaar)."""
    return pd.DataFrame(
        {
            "aadhaar": ["1234 5678 9012", "9876-5432-1098", "1111 2222 3333"],
            "name": ["Rahul", "Priya", "Amit"],
        }
    )


@pytest.fixture
def pii_report(pii_df) -> pd.DataFrame:
    return scan_pii(pii_df, warn=False)


# ---------------------------------------------------------------------------
# scan_pii â€” detection tests (same as original)
# ---------------------------------------------------------------------------


class TestPIIDetection:
    def test_email_detected(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        email_hits = report[report["PII_Type"] == "email"]
        assert len(email_hits) >= 1
        assert "email" in email_hits["Column"].values

    def test_phone_detected(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        phone_hits = report[report["PII_Type"].str.startswith("phone")]
        assert len(phone_hits) >= 1

    def test_ssn_detected(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        ssn_hits = report[report["PII_Type"] == "ssn"]
        assert len(ssn_hits) >= 1

    def test_credit_card_detected(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        cc_hits = report[report["PII_Type"] == "credit_card"]
        assert len(cc_hits) >= 1

    def test_ip_address_detected(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        ip_hits = report[report["PII_Type"] == "ip_address"]
        assert len(ip_hits) >= 1

    def test_aadhaar_detected(self, indian_pii_df):
        report = scan_pii(indian_pii_df, warn=False)
        aadhaar_hits = report[report["PII_Type"] == "aadhaar"]
        assert len(aadhaar_hits) >= 1

    def test_column_name_detection(self):
        df = pd.DataFrame(
            {
                "first_name": ["Alice"],
                "last_name": ["Smith"],
                "date_of_birth": ["1990-01-01"],
            }
        )
        report = scan_pii(df, warn=False)
        detected_types = set(report["PII_Type"])
        assert "name_field" in detected_types
        assert "date_of_birth" in detected_types

    def test_report_columns_correct(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        expected = {"Column", "PII_Type", "Detection_Method", "Confidence", "Sample_Match", "Description"}
        assert set(report.columns) == expected

    def test_confidence_values_valid(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        assert set(report["Confidence"].unique()).issubset({"high", "medium", "low"})

    def test_no_pii_in_clean_data(self, clean_df):
        report = scan_pii(clean_df, warn=False)
        high_findings = report[report["Confidence"] == "high"]
        assert len(high_findings) == 0

    def test_numeric_columns_skipped(self, clean_df):
        report = scan_pii(clean_df, warn=False)
        numeric_value_hits = report[
            report["Column"].isin(["product_id", "quantity", "price"]) & (report["Detection_Method"] == "value_pattern")
        ]
        assert len(numeric_value_hits) == 0

    def test_warning_emitted(self, pii_df):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            scan_pii(pii_df, warn=True)
            pii_warnings = [x for x in w if issubclass(x.category, PIIWarning)]
            assert len(pii_warnings) >= 1

    def test_warning_suppressed(self, pii_df):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            scan_pii(pii_df, warn=False)
            pii_warnings = [x for x in w if issubclass(x.category, PIIWarning)]
            assert len(pii_warnings) == 0

    def test_custom_patterns_override_defaults(self, pii_df):
        custom = {"never_match": {"value_regex": "ZZZZZ", "name_regex": "ZZZZZ", "description": "x"}}
        report = scan_pii(pii_df, patterns=custom, warn=False)
        assert len(report) == 0

    def test_non_dataframe_raises(self):
        with pytest.raises(TypeError, match="Expected a pandas DataFrame"):
            scan_pii([1, 2, 3])

    def test_empty_df_returns_empty_report(self):
        df = pd.DataFrame({"A": pd.Series([], dtype="object")})
        report = scan_pii(df, warn=False)
        assert len(report) == 0


# ---------------------------------------------------------------------------
# mask_pii â€” redact strategy
# ---------------------------------------------------------------------------


class TestMaskPiiRedact:
    def test_redact_replaces_pii_columns(self, pii_df, pii_report):
        masked = mask_pii(pii_df, pii_report, strategy="redact")
        pii_cols = pii_report["Column"].unique()
        for col in pii_cols:
            if col in masked.columns:
                assert (masked[col] == "***REDACTED***").all(), f"Column '{col}' not fully redacted"

    def test_redact_leaves_non_pii_columns_intact(self, pii_df, pii_report):
        masked = mask_pii(pii_df, pii_report, strategy="redact")
        pii_cols = set(pii_report["Column"].unique())
        for col in pii_df.columns:
            if col not in pii_cols:
                pd.testing.assert_series_equal(masked[col], pii_df[col])

    def test_redact_returns_dataframe(self, pii_df, pii_report):
        result = mask_pii(pii_df, pii_report, strategy="redact")
        assert isinstance(result, pd.DataFrame)

    def test_redact_does_not_mutate_original(self, pii_df, pii_report):
        original_email = pii_df["email"].tolist()
        mask_pii(pii_df, pii_report, strategy="redact")
        assert pii_df["email"].tolist() == original_email

    def test_redact_custom_value(self, pii_df, pii_report):
        masked = mask_pii(pii_df, pii_report, strategy="redact", redact_value="[PII]")
        pii_cols = pii_report["Column"].unique()
        for col in pii_cols:
            if col in masked.columns:
                assert (masked[col] == "[PII]").all()

    def test_redact_empty_report_returns_copy(self, pii_df):
        empty_report = pd.DataFrame(
            columns=["Column", "PII_Type", "Detection_Method", "Confidence", "Sample_Match", "Description"]
        )
        result = mask_pii(pii_df, empty_report, strategy="redact")
        pd.testing.assert_frame_equal(result, pii_df)

    def test_redact_explicit_columns(self, pii_df, pii_report):
        masked = mask_pii(pii_df, pii_report, strategy="redact", columns=["email"])
        assert (masked["email"] == "***REDACTED***").all()
        # Other columns (including other PII) are untouched
        assert masked["SSN"].tolist() == pii_df["SSN"].tolist()

    def test_redact_invalid_strategy_raises(self, pii_df, pii_report):
        with pytest.raises(ValueError, match="strategy must be one of"):
            mask_pii(pii_df, pii_report, strategy="teleport")


# ---------------------------------------------------------------------------
# mask_pii â€” hash strategy
# ---------------------------------------------------------------------------


class TestMaskPiiHash:
    def test_hash_replaces_with_hex_string(self, pii_df, pii_report):
        masked = mask_pii(pii_df, pii_report, strategy="hash")
        email_vals = masked["email"].tolist()
        for v in email_vals:
            assert all(c in "0123456789abcdef" for c in v), f"Not hex: {v!r}"

    def test_hash_length_respected(self, pii_df, pii_report):
        masked = mask_pii(pii_df, pii_report, strategy="hash", hash_length=8)
        email_vals = masked["email"].tolist()
        for v in email_vals:
            assert len(v) == 8

    def test_hash_is_deterministic(self, pii_df, pii_report):
        m1 = mask_pii(pii_df, pii_report, strategy="hash")
        m2 = mask_pii(pii_df, pii_report, strategy="hash")
        pd.testing.assert_frame_equal(m1, m2)

    def test_hash_distinct_inputs_produce_distinct_outputs(self, pii_df, pii_report):
        masked = mask_pii(pii_df, pii_report, strategy="hash")
        email_hashes = masked["email"].tolist()
        # All three emails are different, so all hashes should differ
        assert len(set(email_hashes)) == len(set(pii_df["email"]))

    def test_hash_returns_dataframe(self, pii_df, pii_report):
        result = mask_pii(pii_df, pii_report, strategy="hash")
        assert isinstance(result, pd.DataFrame)

    def test_sha256_token_helper(self):
        token = _sha256_token("hello", length=10)
        assert len(token) == 10
        assert all(c in "0123456789abcdef" for c in token)
        # Deterministic
        assert _sha256_token("hello", 10) == _sha256_token("hello", 10)


# ---------------------------------------------------------------------------
# mask_pii â€” pseudonymise strategy
# ---------------------------------------------------------------------------


class TestMaskPiiPseudonymise:
    def test_pseudonymise_returns_tuple(self, pii_df, pii_report):
        result = mask_pii(pii_df, pii_report, strategy="pseudonymise")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_pseudonymise_df_has_labels(self, pii_df, pii_report):
        masked_df, mapping = mask_pii(pii_df, pii_report, strategy="pseudonymise")
        email_vals = masked_df["email"].tolist()
        for v in email_vals:
            assert v.startswith("EMAIL_"), f"Expected EMAIL_ prefix, got {v!r}"

    def test_pseudonymise_mapping_invertible(self, pii_df, pii_report):
        masked_df, mapping = mask_pii(pii_df, pii_report, strategy="pseudonymise")
        # mapping[col][original] = pseudo  â†’  we can rebuild the original
        for col, col_map in mapping.items():
            inv = {v: k for k, v in col_map.items()}
            for i, row_val in enumerate(masked_df[col]):
                original = inv.get(row_val)
                assert original is not None, f"No inverse for {row_val!r} in col {col!r}"
                assert original == str(pii_df[col].iloc[i])

    def test_pseudonymise_same_value_same_label(self, pii_report):
        """Duplicate values must get the same pseudo-label."""
        df = pd.DataFrame(
            {
                "email": ["a@a.com", "b@b.com", "a@a.com"]  # first and last are the same
            }
        )
        report = scan_pii(df, warn=False)
        masked_df, mapping = mask_pii(df, report, strategy="pseudonymise")
        assert masked_df["email"].iloc[0] == masked_df["email"].iloc[2]
        assert masked_df["email"].iloc[0] != masked_df["email"].iloc[1]

    def test_pseudonymise_nulls_preserved(self, pii_report):
        df = pd.DataFrame({"email": ["a@a.com", None, "b@b.com"]})
        report = scan_pii(df, warn=False)
        masked_df, _ = mask_pii(df, report, strategy="pseudonymise")
        assert pd.isna(masked_df["email"].iloc[1])

    def test_pseudonymise_does_not_mutate_original(self, pii_df, pii_report):
        original_email = pii_df["email"].tolist()
        mask_pii(pii_df, pii_report, strategy="pseudonymise")
        assert pii_df["email"].tolist() == original_email

    def test_pseudonymise_empty_report(self, pii_df):
        empty_report = pd.DataFrame(
            columns=["Column", "PII_Type", "Detection_Method", "Confidence", "Sample_Match", "Description"]
        )
        result = mask_pii(pii_df, empty_report, strategy="pseudonymise")
        assert isinstance(result, tuple)
        masked_df, mapping = result
        assert mapping == {}
        pd.testing.assert_frame_equal(masked_df, pii_df)
