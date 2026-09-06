# ADR 004 — Bank / Big 4 Production Hardening (9-Component Security Overhaul)

**Status**: Accepted  
**Date**: 2026-08-17  
**Deciders**: Nihal Tripathi (Maintainer)  
**Context**: Deployment of `etlpipe` as a trusted data pipeline framework inside major financial institutions and Big 4 consulting firms, including use cases covering Alteryx-to-Python workflow migration and secure data handling.

---

## Context & Problem Statement

Prior to v2.2.0, `etlpipe` had no controls for:
- Secure deserialization (pickle was accepted)
- Secrets management (credentials could be embedded in YAML)
- Transport security (HTTP was silently accepted)
- Access control (any caller could execute any pipeline)
- Real-time audit streaming to SIEM systems
- Encrypted storage of PII pseudonymisation mappings
- Banking-sector PII pattern coverage (routing numbers, SWIFT/BIC, PANs, etc.)
- Regulatory data lineage (BCBS 239, MiFID II)

A bank data engineering team evaluating `etlpipe` for onboarding raised a requirement for a thorough security audit before adoption. The framework needed to demonstrate trustworthiness comparable to enterprise ETL platforms before it could manage production-grade financial data pipelines.

---

## Decision

Implement a **9-component security hardening plan** across `etlpipe` and `etlpipe-governance` with the following components, each independently testable and verifiable.

---

## Component Decisions

### 1. Pickle Removal (CWE-502)

**Decision**: Permanently remove pickle support. Raise `PickleRemovedError` for `.pkl`/`.pickle` extensions.

**Rationale**: Python pickle deserialization of untrusted data allows arbitrary code execution (RCE). Financial institutions categorically prohibit deserialization of externally sourced pickled objects. Soft deprecation warnings are insufficient — a hard block ensures CI catches any regression immediately.

**Trade-off**: Breaking change for users storing DataFrames as pickle. Migration path to Parquet is documented. Parquet is strictly superior (columnar, compressed, schema-embedded, read by Java/R/Spark).

### 2. Secrets Resolution (`etlpipe._secrets`)

**Decision**: Introduce `${ENV_VAR}` token resolution at pipeline load time. Raise `SecretResolutionError` on any unresolved token.

**Rationale**: Banks require credentials to be stored in external secret managers, not in version-controlled YAML files. The token system provides a clean interface between secret managers and pipeline configuration without adding a hard dependency on any specific vault product.

**Alternative rejected**: Supporting direct KMS/Vault SDK calls from YAML — rejected because it would introduce hard dependencies on cloud provider SDKs and require credentials to authenticate to the secret manager itself (circular dependency).

### 3. Bank-Specific PII Patterns

**Decision**: Add 8 banking-sector PII patterns to `_DEFAULT_PATTERNS` in `etlpipe_governance.pii`.

**Rationale**: The existing 12 patterns covered general international PII but lacked financial-sector specifics. SWIFT/BIC codes, ABA routing numbers, masked PANs, and UK sort codes are common in banking ETL pipelines and must be flagged by `scan_pii()` before data leaves a secure environment.

**Trade-off**: The `account_number` pattern (6–17 digits) has high false-positive potential. Column name matching reduces noise. Users with specific account formats can override `_DEFAULT_PATTERNS` using the `patterns=` parameter.

### 4. HTTPS Enforcement

**Decision**: Raise `InsecureURLError` for `http://` URLs in `Developer.download()`. Enable SSL cert verification via `ssl.create_default_context()` on all connections.

**Rationale**: Plain HTTP connections expose financial data in transit. PCI-DSS Requirement 4.2.1 mandates encryption for cardholder data in transit over public networks. OWASP Top 10 A02:2021 (Cryptographic Failures) requires encrypted transport.

**Trade-off**: `allow_http=True` escape hatch provided for internal dev environments with a mandatory `SecurityWarning`. This prevents legitimate internal tooling from breaking while making the security intent explicit.

### 5. SIEM Audit Forwarding

**Decision**: Introduce `AuditForwarder` ABC and three built-in implementations (Splunk HEC, Webhook, S3).

**Rationale**: SOX Section 404 and MiFID II require tamper-evident audit trails accessible to compliance teams in real-time via SIEM platforms. Local JSONL files are insufficient — they can be deleted and are not searchable at enterprise scale. Splunk is the dominant SIEM in financial services.

**Decision**: Forwarder failures must never interrupt pipeline execution or local audit persistence. 

**Rationale**: A SIEM outage cannot be allowed to halt production data pipelines. Local persistence is the source of truth; SIEM forwarding is best-effort with alerting.

### 6. OpenLineage Data Lineage (BCBS 239)

**Decision**: Introduce `LineageCollector` producing OpenLineage `RunEvent` dicts, with Marquez as the reference lineage server.

**Rationale**: BCBS 239 (Basel Committee on Banking Supervision Principles 239) requires systemically important banks (SIBs) to have strong data lineage capabilities for risk data. OpenLineage is the de facto open standard supported by Apache Airflow, dbt, Spark, and Great Expectations.

**Alternative rejected**: Building a proprietary lineage format — rejected because interoperability with existing bank lineage infrastructure (Marquez, Apache Atlas) requires open standards.

### 7. RBAC Pipeline Guard

**Decision**: Introduce `PipelineGuard` interface with pluggable `role_checker` callable. Guard failures are fail-closed (`AccessDeniedError`), not fail-open.

**Rationale**: Banks have strict need-to-know access controls. A pipeline that reads customer PII should only be executable by authorized roles. Fail-closed behaviour (deny on IAM service failure) is the safe default in financial environments — fail-open would be a security incident.

**Alternative rejected**: Built-in LDAP/AD integration — rejected to avoid hard dependencies on specific IAM products. The pluggable `role_checker` allows each institution to wire in their own IAM without modifying `etlpipe` internals.

### 8. Encrypted Pseudonymise Mapping Storage

**Decision**: `save_mapping()` / `load_mapping()` with AES-256-GCM + PBKDF2-HMAC-SHA256 (480,000 iterations). Warn with `MappingSecurityWarning` if stored unencrypted.

**Rationale**: The pseudonymise mapping contains original PII values as dictionary keys. Storing it unencrypted is equivalent to storing PII in plaintext. AES-256-GCM provides authenticated encryption (detects tampering). PBKDF2 with 480,000 iterations (NIST SP 800-132) resists brute-force attacks on the encryption key.

**Dependency**: `cryptography` library required for encrypted operations. Zero-dependency fallback to plaintext with warning preserves usability for non-sensitive development data.

### 9. Security Test Suite

**Decision**: 58 dedicated security tests in `tests/test_security.py`, organized by component, using mock-based network isolation.

**Rationale**: Security properties that are not tested regress. The test suite is the executable specification of the security contract. Financial institutions require documented evidence that security controls are tested on every commit.

---

## Consequences

### Positive
- `etlpipe` is now auditable for use in regulated financial environments (GDPR, HIPAA, SOX, PCI-DSS, BCBS 239, MiFID II)
- All 496 tests pass, demonstrating zero regression to existing functionality
- All new modules are zero additional hard dependencies (secrets, RBAC, lineage use stdlib only; crypto is optional)

### Negative / Trade-offs
- **Breaking change**: Pickle is permanently removed (no opt-out)
- **Breaking change**: `Developer.download()` rejects HTTP by default
- Users with existing `.pkl` files must migrate to Parquet (migration guide in `SECURITY.md`)
- `cryptography` library must be installed for encrypted mapping storage (`pip install cryptography`)

### Risks Accepted
- The `account_number` PII regex (6–17 digits) will produce false positives in datasets containing non-account numeric IDs. This is an acceptable trade-off — false positives trigger review, which is the correct behaviour for PII scanning in a bank.

---

## References

- [NIST SP 800-132: Recommendation for Password-Based Key Derivation](https://csrc.nist.gov/publications/detail/sp/800-132/final)
- [BCBS 239: Principles for Effective Risk Data Aggregation](https://www.bis.org/publ/bcbs239.htm)
- [OpenLineage Specification](https://openlineage.io/docs/)
- [PCI-DSS v4.0 Requirement 4.2.1](https://www.pcisecuritystandards.org/)
- [CWE-502: Deserialization of Untrusted Data](https://cwe.mitre.org/data/definitions/502.html)
- [OWASP Top 10 2021: A02 Cryptographic Failures](https://owasp.org/Top10/A02_2021-Cryptographic_Failures/)
- [SOX Section 404: Management Assessment of Internal Controls](https://www.sec.gov/spotlight/sarbanes-oxley.htm)
