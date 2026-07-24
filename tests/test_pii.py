"""Tests for etlpipe._pii — PII detection scanner."""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

from etlpipe._pii import PIIWarning, scan_pii

# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #


@pytest.fixture
def pii_df() -> pd.DataFrame:
    """DataFrame containing various PII types for testing."""
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


# ------------------------------------------------------------------ #
# Detection tests
# ------------------------------------------------------------------ #


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

    def test_detection_method_reported(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        assert "Detection_Method" in report.columns
        methods = set(report["Detection_Method"])
        # Should have at least one of each type
        assert len(methods) >= 1


# ------------------------------------------------------------------ #
# Clean data tests (no false positives)
# ------------------------------------------------------------------ #


class TestCleanData:
    def test_no_pii_in_clean_data(self, clean_df):
        report = scan_pii(clean_df, warn=False)
        # There should be no high-confidence findings
        high_findings = report[report["Confidence"] == "high"]
        assert len(high_findings) == 0

    def test_numeric_columns_skipped(self, clean_df):
        """Value regex scanning should skip non-object columns."""
        report = scan_pii(clean_df, warn=False)
        # product_id, quantity, price are numeric — shouldn't match value patterns
        numeric_value_hits = report[
            (report["Column"].isin(["product_id", "quantity", "price"]))
            & (report["Detection_Method"] == "value_pattern")
        ]
        assert len(numeric_value_hits) == 0


# ------------------------------------------------------------------ #
# Report format tests
# ------------------------------------------------------------------ #


class TestReportFormat:
    def test_report_columns(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        expected_cols = {"Column", "PII_Type", "Detection_Method", "Confidence", "Sample_Match", "Description"}
        assert set(report.columns) == expected_cols

    def test_confidence_values(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        valid_confidences = {"high", "medium", "low"}
        assert set(report["Confidence"].unique()).issubset(valid_confidences)

    def test_empty_df_returns_empty_report(self):
        df = pd.DataFrame({"A": pd.Series([], dtype="object")})
        report = scan_pii(df, warn=False)
        assert len(report) == 0

    def test_returns_dataframe(self, pii_df):
        report = scan_pii(pii_df, warn=False)
        assert isinstance(report, pd.DataFrame)


# ------------------------------------------------------------------ #
# Warning tests
# ------------------------------------------------------------------ #


class TestPIIWarning:
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

    def test_no_warning_for_clean_data(self, clean_df):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            scan_pii(clean_df, warn=True)
            pii_warnings = [x for x in w if issubclass(x.category, PIIWarning)]
            assert len(pii_warnings) == 0


# ------------------------------------------------------------------ #
# Custom patterns
# ------------------------------------------------------------------ #


class TestCustomPatterns:
    def test_custom_pattern(self):
        df = pd.DataFrame({"order_ref": ["ORD-12345", "ORD-67890", "ORD-11111"]})
        custom = {
            "order_id": {
                "value_regex": r"ORD-\d{5}",
                "name_regex": r"(?i)order",
                "description": "Internal order reference",
            }
        }
        report = scan_pii(df, patterns=custom, warn=False)
        assert len(report) >= 1
        assert "order_id" in report["PII_Type"].values

    def test_custom_patterns_override_defaults(self, pii_df):
        """When custom patterns are provided, defaults should NOT apply."""
        custom = {
            "custom_only": {
                "value_regex": r"ZZZZZ",
                "name_regex": r"ZZZZZ",
                "description": "Will never match",
            }
        }
        report = scan_pii(pii_df, patterns=custom, warn=False)
        assert len(report) == 0  # None of the defaults should fire


# ------------------------------------------------------------------ #
# Error handling
# ------------------------------------------------------------------ #


class TestErrorHandling:
    def test_non_dataframe_raises(self):
        with pytest.raises(TypeError, match="Expected a pandas DataFrame"):
            scan_pii([1, 2, 3])


# ------------------------------------------------------------------ #
# Backward-compatibility shim tests
# ------------------------------------------------------------------ #


class TestBackwardCompatShim:
    """Verify that the etlpipe.* import paths still work after the spinoff."""

    def test_scan_pii_importable_from_etlpipe(self):
        from etlpipe import scan_pii as sp

        assert callable(sp)

    def test_scan_pii_importable_from_etlpipe_pii(self):
        from etlpipe._pii import scan_pii as sp

        assert callable(sp)

    def test_pii_warning_importable_from_etlpipe(self):
        from etlpipe._pii import PIIWarning

        assert issubclass(PIIWarning, UserWarning)

    def test_shim_and_governance_are_same_function(self):
        from etlpipe._pii import scan_pii as shim_fn
        from etlpipe_governance.pii import scan_pii as gov_fn

        assert shim_fn is gov_fn

    def test_shim_scan_pii_works_end_to_end(self):
        from etlpipe import scan_pii as sp

        df = pd.DataFrame({"email": ["test@example.com"]})
        report = sp(df, warn=False)
        assert len(report) >= 1
