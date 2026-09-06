"""Comprehensive security test suite for etlpipe bank/Big4 production hardening.

Tests all 9 components added in the production hardening plan:
  1. Pickle removal (CWE-502)
  2. Secrets resolution
  3. Bank-specific PII patterns
  4. HTTPS enforcement
  5. SIEM audit forwarder fan-out
  6. OpenLineage lineage collector
  7. RBAC guard
  8. Secure pseudonymise mapping storage
  9. Developer.download HTTPS integration
"""

from __future__ import annotations

import json
import os
import tempfile
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ===========================================================================
# Component 1 — Pickle Removal (CWE-502)
# ===========================================================================

class TestPickleRemoval:
    """PickleRemovedError is raised for any .pkl or .pickle path."""

    def test_input_data_pkl_raises(self, tmp_path):
        from etlpipe.in_out import InOut, PickleRemovedError

        fake = tmp_path / "data.pkl"
        fake.write_bytes(b"fake pickle")
        with pytest.raises(PickleRemovedError, match="CWE-502"):
            InOut.input_data(str(fake))

    def test_input_data_pickle_ext_raises(self, tmp_path):
        from etlpipe.in_out import InOut, PickleRemovedError

        fake = tmp_path / "data.pickle"
        fake.write_bytes(b"fake pickle")
        with pytest.raises(PickleRemovedError):
            InOut.input_data(str(fake))

    def test_output_data_pkl_raises(self, tmp_path):
        from etlpipe.in_out import InOut, PickleRemovedError

        df = pd.DataFrame({"a": [1, 2]})
        dest = tmp_path / "out.pkl"
        with pytest.raises(PickleRemovedError, match="Parquet"):
            InOut.output_data(df, str(dest))

    def test_output_data_pickle_ext_raises(self, tmp_path):
        from etlpipe.in_out import InOut, PickleRemovedError

        df = pd.DataFrame({"a": [1, 2]})
        dest = tmp_path / "out.pickle"
        with pytest.raises(PickleRemovedError):
            InOut.output_data(df, str(dest))

    def test_parquet_still_works(self, tmp_path):
        """Parquet is the recommended migration target and must still work."""
        from etlpipe.in_out import InOut

        df = pd.DataFrame({"col": [10, 20, 30]})
        dest = str(tmp_path / "data.parquet")
        InOut.output_data(df, dest)
        loaded = InOut.input_data(dest)
        assert list(loaded["col"]) == [10, 20, 30]

    def test_pickle_removed_error_message_quality(self, tmp_path):
        from etlpipe.in_out import PickleRemovedError

        err = PickleRemovedError("/data/file.pkl")
        msg = str(err)
        assert "CWE-502" in msg
        assert "Parquet" in msg or "Feather" in msg
        assert "/data/file.pkl" in msg


# ===========================================================================
# Component 2 — Secrets Resolution
# ===========================================================================

class TestSecretsResolution:
    """${ENV_VAR} tokens are resolved at pipeline load time."""

    def test_resolve_simple_string(self):
        from etlpipe._secrets import resolve_secrets

        os.environ["_TEST_SECRET_FOO"] = "bar"
        result = resolve_secrets("${_TEST_SECRET_FOO}")
        assert result == "bar"

    def test_resolve_nested_dict(self):
        from etlpipe._secrets import resolve_secrets

        os.environ["_TEST_HOST"] = "db.bank.internal"
        os.environ["_TEST_PORT"] = "5432"
        config = {
            "database": {
                "host": "${_TEST_HOST}",
                "port": "${_TEST_PORT}",
                "password": "plain_no_token",
            }
        }
        result = resolve_secrets(config)
        assert result["database"]["host"] == "db.bank.internal"
        assert result["database"]["port"] == "5432"
        assert result["database"]["password"] == "plain_no_token"

    def test_resolve_list_items(self):
        from etlpipe._secrets import resolve_secrets

        os.environ["_TEST_BUCKET"] = "s3://prod-data"
        result = resolve_secrets(["static", "${_TEST_BUCKET}", 42])
        assert result == ["static", "s3://prod-data", 42]

    def test_missing_env_var_raises(self):
        from etlpipe._secrets import SecretResolutionError, resolve_secrets

        # Ensure the variable is definitely not set
        os.environ.pop("_TEST_MISSING_VAR_XYZ", None)
        with pytest.raises(SecretResolutionError) as exc_info:
            resolve_secrets("${_TEST_MISSING_VAR_XYZ}")
        assert "_TEST_MISSING_VAR_XYZ" in str(exc_info.value)

    def test_env_prefix_syntax(self):
        from etlpipe._secrets import resolve_secrets

        os.environ["_TEST_API_KEY"] = "secret123"
        result = resolve_secrets("${env:_TEST_API_KEY}")
        assert result == "secret123"

    def test_has_unresolved_tokens(self):
        from etlpipe._secrets import has_unresolved_tokens

        assert has_unresolved_tokens({"path": "${DATA_PATH}"}) is True
        assert has_unresolved_tokens({"path": "/data/file.csv"}) is False
        assert has_unresolved_tokens(["${A}", "static"]) is True
        assert has_unresolved_tokens(42) is False

    def test_non_string_scalars_pass_through(self):
        from etlpipe._secrets import resolve_secrets

        config = {"count": 100, "flag": True, "nothing": None}
        assert resolve_secrets(config) == config

    def test_secret_resolution_error_has_var_name(self):
        from etlpipe._secrets import SecretResolutionError

        os.environ.pop("_NEVER_SET_XYZ", None)
        with pytest.raises(SecretResolutionError) as exc_info:
            from etlpipe._secrets import resolve_secrets
            resolve_secrets("${_NEVER_SET_XYZ}")
        assert exc_info.value.var_name == "_NEVER_SET_XYZ"


# ===========================================================================
# Component 3 — Bank-Specific PII Patterns
# ===========================================================================

class TestBankPIIPatterns:
    """Banking PII types are detected by scan_pii()."""

    def _scan(self, df, col_name=None):
        from etlpipe_governance import scan_pii
        report = scan_pii(df)
        if col_name:
            return report[report["Column"] == col_name]
        return report

    def test_routing_number_by_column_name(self):
        df = pd.DataFrame({"routing_num": ["021000021", "026009593"]})
        report = self._scan(df, "routing_num")
        assert not report.empty
        assert (report["PII_Type"] == "routing_number").any()

    def test_account_number_by_column_name(self):
        df = pd.DataFrame({"acct_num": ["123456789012", "987654321098"]})
        report = self._scan(df, "acct_num")
        assert not report.empty
        assert (report["PII_Type"] == "account_number").any()

    def test_swift_bic_by_column_name(self):
        df = pd.DataFrame({"swift_code": ["CHASUS33", "BOFAUS3N"]})
        report = self._scan(df, "swift_code")
        assert not report.empty
        assert (report["PII_Type"] == "swift_bic").any()

    def test_swift_bic_by_value(self):
        df = pd.DataFrame({"bank_id": ["CHASUS33XXX", "BOFAUS3NXXX"]})
        report = self._scan(df, "bank_id")
        assert not report.empty

    def test_sort_code_by_column_name(self):
        df = pd.DataFrame({"sort_code": ["20-00-00", "60-16-13"]})
        report = self._scan(df, "sort_code")
        assert not report.empty
        assert (report["PII_Type"] == "sort_code").any()

    def test_tax_id_ein_by_column_name(self):
        df = pd.DataFrame({"employer_id": ["12-3456789", "98-7654321"]})
        report = self._scan(df, "employer_id")
        assert not report.empty
        assert (report["PII_Type"] == "tax_id_ein").any()

    def test_internal_cust_id_by_column_name(self):
        df = pd.DataFrame({"customer_id": ["CUS-001", "CUS-002"]})
        report = self._scan(df, "customer_id")
        assert not report.empty
        assert (report["PII_Type"] == "internal_cust_id").any()

    def test_cif_num_by_column_name(self):
        df = pd.DataFrame({"cif_num": ["00012345", "00067890"]})
        report = self._scan(df, "cif_num")
        assert not report.empty

    def test_existing_patterns_still_work(self):
        """Original 12 patterns remain functional after adding bank extensions."""
        df = pd.DataFrame({
            "email": ["alice@bank.com", "bob@corp.org"],
            "ssn": ["123-45-6789", "987-65-4321"],
        })
        report = self._scan(df)
        pii_types = set(report["PII_Type"].tolist())
        assert "email" in pii_types
        assert "ssn" in pii_types

    def test_total_pattern_count_expanded(self):
        """_DEFAULT_PATTERNS must contain at least 20 entries (12 original + 8 banking)."""
        from etlpipe_governance.pii import _DEFAULT_PATTERNS
        assert len(_DEFAULT_PATTERNS) >= 20


# ===========================================================================
# Component 4 — HTTPS Enforcement
# ===========================================================================

class TestHTTPSEnforcement:
    """Developer.download() rejects plain HTTP URLs by default."""

    def test_http_url_raises_insecure_url_error(self):
        from etlpipe.engines.pandas_engine import InsecureURLError, PandasEngine

        engine = PandasEngine()
        with pytest.raises(InsecureURLError, match="HTTP"):
            engine.download("http://api.example.com/data")

    def test_https_url_accepted(self):
        """HTTPS URLs should not be rejected at the validation stage."""
        from etlpipe.engines.pandas_engine import PandasEngine

        engine = PandasEngine()
        # We mock urlopen so no real network call is made
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'[{"key": "value"}]'
        mock_response.status = 200

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = engine.download("https://api.example.com/data")

        assert isinstance(result, pd.DataFrame)
        assert "key" in result.columns

    def test_allow_http_emits_security_warning(self):
        """allow_http=True must emit a SecurityWarning, not silently allow."""
        from etlpipe.engines.pandas_engine import PandasEngine, SecurityWarning

        engine = PandasEngine()
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'{"ok": true}'
        mock_response.status = 200

        with patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.warns(SecurityWarning, match="insecure HTTP"):
                engine.download("http://internal.example.com/data", allow_http=True)

    def test_insecure_url_error_message(self):
        from etlpipe.engines.pandas_engine import InsecureURLError

        err = InsecureURLError("http://bad.example.com")
        assert "HTTP" in str(err)
        assert "HTTPS" in str(err)


# ===========================================================================
# Component 5 — SIEM Audit Forwarder Fan-out
# ===========================================================================

class TestAuditForwarders:
    """AuditTrail fans out to registered forwarders on every log() call."""

    def _make_results(self):
        return pd.DataFrame({
            "Suite": ["Daily"],
            "Contract": ["schema:customers"],
            "Description": ["Customer schema check"],
            "Status": ["PASS"],
            "Violation_Count": [0],
            "Violations": [""],
        })

    def test_forwarder_is_called_on_log(self, tmp_path):
        from etlpipe_governance.audit import AuditForwarder, AuditTrail

        class MockForwarder(AuditForwarder):
            def __init__(self):
                self.received = []

            def forward(self, records):
                self.received.extend(records)

        fwd = MockForwarder()
        trail = AuditTrail(path=str(tmp_path), forwarders=[fwd])
        trail.log(self._make_results(), run_id="test-001")

        assert len(fwd.received) == 1
        assert fwd.received[0]["run_id"] == "test-001"
        assert fwd.received[0]["Suite"] == "Daily"

    def test_multiple_forwarders_all_called(self, tmp_path):
        from etlpipe_governance.audit import AuditForwarder, AuditTrail

        class CountForwarder(AuditForwarder):
            def __init__(self, name):
                self.name = name
                self.calls = 0

            def forward(self, records):
                self.calls += 1

        f1, f2, f3 = CountForwarder("a"), CountForwarder("b"), CountForwarder("c")
        trail = AuditTrail(path=str(tmp_path), forwarders=[f1, f2, f3])
        trail.log(self._make_results(), run_id="multi-001")

        assert f1.calls == 1
        assert f2.calls == 1
        assert f3.calls == 1

    def test_forwarder_failure_does_not_lose_local_record(self, tmp_path):
        """A crashing forwarder must not cause local JSONL write to be lost."""
        from etlpipe_governance.audit import AuditForwarder, AuditTrail

        class CrashForwarder(AuditForwarder):
            def forward(self, records):
                raise RuntimeError("SIEM is down!")

        trail = AuditTrail(path=str(tmp_path), forwarders=[CrashForwarder()])
        # Should not raise even though forwarder crashes
        trail.log(self._make_results(), run_id="crash-001")

        # Local file must still have the record
        history = trail.load()
        assert len(history) == 1
        assert history.iloc[0]["run_id"] == "crash-001"

    def test_no_forwarders_works_as_before(self, tmp_path):
        from etlpipe_governance.audit import AuditTrail

        trail = AuditTrail(path=str(tmp_path))
        trail.log(self._make_results(), run_id="plain-001")
        history = trail.load()
        assert len(history) == 1

    def test_splunk_forwarder_sends_correct_payload(self, tmp_path):
        from etlpipe_governance.audit import AuditTrail, SplunkHECForwarder

        sent_payloads = []

        def mock_urlopen(req, timeout=None):
            body = json.loads(req.data.decode())
            sent_payloads.append(body)
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.status = 200
            return resp

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            fwd = SplunkHECForwarder(
                url="https://splunk.test:8088/services/collector/event",
                token="test-token",
                sourcetype="etlpipe:test",
            )
            trail = AuditTrail(path=str(tmp_path), forwarders=[fwd])
            trail.log(self._make_results(), run_id="splunk-001")

        assert len(sent_payloads) == 1
        event = sent_payloads[0]
        assert event["sourcetype"] == "etlpipe:test"
        assert event["event"]["run_id"] == "splunk-001"

    def test_webhook_forwarder_sends_batch(self, tmp_path):
        from etlpipe_governance.audit import AuditTrail, WebhookForwarder

        captured = []

        def mock_urlopen(req, timeout=None):
            body = json.loads(req.data.decode())
            captured.append(body)
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.status = 200
            return resp

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            fwd = WebhookForwarder(url="https://hooks.test/webhook")
            trail = AuditTrail(path=str(tmp_path), forwarders=[fwd])
            trail.log(self._make_results(), run_id="hook-001")

        assert len(captured) == 1
        assert "audit_records" in captured[0]
        assert captured[0]["audit_records"][0]["run_id"] == "hook-001"


# ===========================================================================
# Component 6 — OpenLineage Lineage Collector
# ===========================================================================

class TestLineageCollector:
    """LineageCollector records steps and produces valid OpenLineage events."""

    def _make_collector(self):
        from etlpipe._lineage import LineageCollector
        c = LineageCollector(namespace="test.prod", job_prefix="bank")
        c.set_pipeline("daily_reconciliation", run_id="run-2026-08-17")
        return c

    def test_record_step(self):
        c = self._make_collector()
        c.record_step(
            step_id="filter_active",
            tool="Preparation.filter",
            inputs=["load_customers"],
            output_schema={"CustomerID": "int64", "Status": "object"},
            row_count=5423,
            duration_s=0.045,
        )
        assert len(c) == 1

    def test_to_openlineage_events_structure(self):
        c = self._make_collector()
        c.record_step(
            step_id="step_a",
            tool="Preparation.filter",
            inputs=["load_data"],
            output_schema={"col1": "int64"},
            row_count=100,
        )
        events = c.to_openlineage_events()
        assert len(events) == 1

        ev = events[0]
        assert ev["eventType"] == "COMPLETE"
        assert ev["job"]["namespace"] == "test.prod"
        assert "bank.daily_reconciliation.step_a" in ev["job"]["name"]
        assert ev["schemaURL"].startswith("https://openlineage.io")
        assert len(ev["outputs"]) == 1
        assert ev["outputs"][0]["facets"]["schema"]["fields"][0]["name"] == "col1"

    def test_input_datasets_populated(self):
        c = self._make_collector()
        c.record_step("step_b", "Join.join", inputs=["step_a", "step_ref"])
        events = c.to_openlineage_events()
        assert len(events[0]["inputs"]) == 2

    def test_to_dict(self):
        c = self._make_collector()
        c.record_step("s1", "InOut.input_data", inputs=[])
        d = c.to_dict()
        assert d["pipeline"] == "daily_reconciliation"
        assert d["namespace"] == "test.prod"
        assert len(d["steps"]) == 1

    def test_repr(self):
        c = self._make_collector()
        r = repr(c)
        assert "LineageCollector" in r
        assert "daily_reconciliation" in r

    def test_emit_to_marquez_sends_post(self):
        from etlpipe._lineage import LineageCollector

        c = LineageCollector(namespace="prod")
        c.set_pipeline("test_pipe", run_id="r1")
        c.record_step("s1", "InOut.input_data", inputs=[], row_count=10)

        sent = []

        def mock_urlopen(req, timeout=None):
            sent.append(json.loads(req.data.decode()))
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.status = 201
            return resp

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            count = c.emit_to_marquez("http://marquez.internal:5000")

        assert count == 1
        assert sent[0]["eventType"] == "COMPLETE"


# ===========================================================================
# Component 7 — RBAC Guard
# ===========================================================================

class TestRBACGuard:
    """PipelineGuard blocks or allows pipeline execution correctly."""

    def test_allow_all_guard_never_raises(self):
        from etlpipe._rbac import AllowAllGuard

        guard = AllowAllGuard()
        guard.check("daily_reconciliation")  # Must not raise

    def test_custom_guard_allows_when_true(self):
        from etlpipe._rbac import PipelineGuard

        guard = PipelineGuard(role_checker=lambda p, a: True)
        guard.check("any_pipeline")  # Should not raise

    def test_custom_guard_denies_when_false(self):
        from etlpipe._rbac import AccessDeniedError, PipelineGuard

        guard = PipelineGuard(role_checker=lambda p, a: False)
        with pytest.raises(AccessDeniedError, match="(?i)access denied") as exc_info:
            guard.check("restricted_pipeline")
        assert exc_info.value.pipeline_name == "restricted_pipeline"

    def test_access_denied_error_attributes(self):
        from etlpipe._rbac import AccessDeniedError

        err = AccessDeniedError("my_pipe", "execute", "user not in group")
        assert err.pipeline_name == "my_pipe"
        assert err.action == "execute"
        assert "user not in group" in str(err)

    def test_env_role_guard_allows_matching_role(self):
        from etlpipe._rbac import EnvRoleGuard

        os.environ["_TEST_ALLOWED_ROLES"] = "data_engineer,data_analyst"
        os.environ["_TEST_USER_ROLE"] = "data_engineer"
        guard = EnvRoleGuard(
            allowed_roles_env="_TEST_ALLOWED_ROLES",
            user_role_env="_TEST_USER_ROLE",
        )
        guard.check("daily_pipeline")  # Must not raise

    def test_env_role_guard_denies_missing_role(self):
        from etlpipe._rbac import AccessDeniedError, EnvRoleGuard

        os.environ["_TEST_ALLOWED_ROLES"] = "data_engineer"
        os.environ["_TEST_USER_ROLE"] = "data_consumer"
        guard = EnvRoleGuard(
            allowed_roles_env="_TEST_ALLOWED_ROLES",
            user_role_env="_TEST_USER_ROLE",
        )
        with pytest.raises(AccessDeniedError):
            guard.check("secure_pipeline")

    def test_env_role_guard_denies_when_roles_env_not_set(self):
        from etlpipe._rbac import AccessDeniedError, EnvRoleGuard

        os.environ.pop("_TEST_UNSET_ROLES", None)
        os.environ["_TEST_USER_ROLE"] = "data_engineer"
        guard = EnvRoleGuard(
            allowed_roles_env="_TEST_UNSET_ROLES",
            user_role_env="_TEST_USER_ROLE",
        )
        with pytest.raises(AccessDeniedError):
            guard.check("any_pipeline")

    def test_guard_exception_in_checker_raises_access_denied(self):
        from etlpipe._rbac import AccessDeniedError, PipelineGuard

        def bad_checker(p, a):
            raise ConnectionError("IAM service unreachable")

        guard = PipelineGuard(role_checker=bad_checker)
        with pytest.raises(AccessDeniedError, match="guard raised"):
            guard.check("any_pipeline")


# ===========================================================================
# Component 8 — Secure Pseudonymise Mapping Storage
# ===========================================================================

class TestSecureMappingStorage:
    """save_mapping and load_mapping work correctly, with and without encryption."""

    def _sample_mapping(self):
        return {
            "email": {"alice@bank.com": "EMAIL_1", "bob@corp.org": "EMAIL_2"},
            "ssn": {"123-45-6789": "SSN_1"},
        }

    def test_save_load_plaintext(self, tmp_path):
        from etlpipe_governance.pii import MappingSecurityWarning, load_mapping, save_mapping

        mapping = self._sample_mapping()
        path = str(tmp_path / "mapping.json")

        with pytest.warns(MappingSecurityWarning):
            save_mapping(mapping, path)

        loaded = load_mapping(path)
        assert loaded == mapping

    def test_save_plaintext_warns(self, tmp_path):
        from etlpipe_governance.pii import MappingSecurityWarning, save_mapping

        path = str(tmp_path / "mapping.json")
        with pytest.warns(MappingSecurityWarning, match="PLAIN TEXT"):
            save_mapping(self._sample_mapping(), path)

    def test_save_load_encrypted(self, tmp_path):
        pytest.importorskip("cryptography")
        from etlpipe_governance.pii import load_mapping, save_mapping

        mapping = self._sample_mapping()
        path = str(tmp_path / "mapping.enc")
        key = "super-secret-bank-key-2026"

        save_mapping(mapping, path, encrypt_key=key)
        loaded = load_mapping(path, encrypt_key=key)
        assert loaded == mapping

    def test_encrypted_file_is_not_readable_as_json(self, tmp_path):
        """Encrypted file should not be parseable as plain JSON."""
        pytest.importorskip("cryptography")
        from etlpipe_governance.pii import save_mapping

        path = str(tmp_path / "mapping.enc")
        save_mapping(self._sample_mapping(), path, encrypt_key="mykey")

        content = Path(path).read_text()
        with pytest.raises((json.JSONDecodeError, ValueError)):
            json.loads(content)

    def test_wrong_key_raises_value_error(self, tmp_path):
        pytest.importorskip("cryptography")
        from etlpipe_governance.pii import load_mapping, save_mapping

        path = str(tmp_path / "mapping.enc")
        save_mapping(self._sample_mapping(), path, encrypt_key="correct-key")

        with pytest.raises(ValueError, match="decryption failed"):
            load_mapping(path, encrypt_key="wrong-key")

    def test_load_nonexistent_file_raises(self, tmp_path):
        from etlpipe_governance.pii import load_mapping

        with pytest.raises(FileNotFoundError):
            load_mapping(str(tmp_path / "does_not_exist.json"))

    def test_save_creates_parent_directories(self, tmp_path):
        from etlpipe_governance.pii import MappingSecurityWarning, save_mapping

        deep_path = str(tmp_path / "a" / "b" / "c" / "mapping.json")
        with pytest.warns(MappingSecurityWarning):
            save_mapping(self._sample_mapping(), deep_path)
        assert Path(deep_path).exists()


# ===========================================================================
# Integration smoke test — all components together
# ===========================================================================

class TestSecurityIntegration:
    """Verify that all 9 components can be imported and instantiated together."""

    def test_all_new_modules_importable(self):
        from etlpipe._lineage import LineageCollector  # noqa: F401
        from etlpipe._rbac import AllowAllGuard, EnvRoleGuard, PipelineGuard  # noqa: F401
        from etlpipe._secrets import resolve_secrets  # noqa: F401
        from etlpipe.engines.pandas_engine import InsecureURLError, SecurityWarning  # noqa: F401
        from etlpipe.in_out import PickleRemovedError  # noqa: F401
        from etlpipe_governance.audit import (  # noqa: F401
            AuditForwarder,
            S3Forwarder,
            SplunkHECForwarder,
            WebhookForwarder,
        )
        from etlpipe_governance.pii import (  # noqa: F401
            MappingSecurityWarning,
            load_mapping,
            save_mapping,
        )

    def test_pipeline_with_rbac_and_lineage(self, tmp_path):
        """Pipeline.run accepts guard= and lineage_collector= without errors."""
        from etlpipe._lineage import LineageCollector
        from etlpipe._rbac import AllowAllGuard
        from etlpipe.in_out import InOut
        from etlpipe.pipeline import Pipeline

        # Write a minimal CSV for the pipeline to consume
        csv_path = tmp_path / "data.csv"
        pd.DataFrame({"x": [1, 2, 3]}).to_csv(csv_path, index=False)

        yaml_content = f"""
name: smoke_test_pipeline
backend: pandas
steps:
  - id: load
    tool: InOut.input_data
    args:
      path: "{str(csv_path).replace(chr(92), '/')}"
"""
        yaml_path = tmp_path / "pipeline.yaml"
        yaml_path.write_text(yaml_content)

        collector = LineageCollector(namespace="test")
        guard = AllowAllGuard()

        p = Pipeline.run(
            str(yaml_path),
            guard=guard,
            lineage_collector=collector,
        )

        assert len(p.metrics) == 1
        assert p.metrics[0]["status"] == "success"
        assert len(collector) == 1

    def test_bank_pii_patterns_count(self):
        from etlpipe_governance.pii import _DEFAULT_PATTERNS

        banking_patterns = {
            "routing_number", "account_number", "swift_bic",
            "pan_masked", "sort_code", "bsb_number", "tax_id_ein", "internal_cust_id",
        }
        assert banking_patterns.issubset(set(_DEFAULT_PATTERNS.keys()))
