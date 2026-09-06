# Security Policy

## Supported Versions

| Version | Supported          |
|---------|---------------------|
| 2.2.x   | ✅ Active support   |
| 2.1.x   | ✅ Active support   |
| 2.0.x   | ⚠️ Critical fixes only |
| < 2.0   | ❌ End of life      |

---

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, report them privately via email:

📧 **nihaltripathi6@gmail.com**

Please include:

1. **Description** of the vulnerability
2. **Steps to reproduce** (or a proof-of-concept)
3. **Impact assessment** — what an attacker could achieve
4. **Affected versions** — which versions are impacted
5. **Suggested fix** (optional but appreciated)

### Response Timeline

| Stage | Timeline |
|---|---|
| Acknowledgement | Within 48 hours |
| Initial assessment | Within 1 week |
| Fix development | Within 2 weeks (critical), 4 weeks (high) |
| Public disclosure | After fix is released and users have had time to upgrade |

---

## Security Track Record

### v2.2.0 — Bank / Big 4 Production Hardening (9-Component Security Overhaul)

This release implements enterprise-grade security controls required for deployment inside major financial institutions (JPMorgan, Bank of America, HSBC) and Big 4 consulting firms. All 9 components have a corresponding test class in `tests/test_security.py`.

#### 1. Pickle Permanently Removed (CWE-502 — Insecure Deserialization)
- **Risk**: Pickle deserialization of untrusted data enables arbitrary code execution (RCE).
- **Fix**: `.pkl` and `.pickle` extensions are **permanently blocked** in `InOut.input_data()` and `InOut.output_data()`. A `PickleRemovedError` is raised immediately with migration instructions.
- **Migration**: Use `InOut.output_data(df, "file.parquet")` / `InOut.input_data("file.parquet")` instead.
- **Note**: This is a **hard error**, not a deprecation warning. There is no opt-out.

#### 2. Secrets Manager Integration (`etlpipe._secrets`)
- **Risk**: Credentials hardcoded in YAML pipeline files or source code.
- **Fix**: `${ENV_VAR}` tokens in pipeline YAML are resolved at load time via `resolve_secrets()`. Any unresolved token raises `SecretResolutionError`, making credential leaks a pipeline failure rather than a silent misconfiguration.
- **Integration**: Works with AWS Secrets Manager, Azure Key Vault, HashiCorp Vault — store secrets externally and inject them via environment variables.

#### 3. Bank-Specific PII Detection
- **Added 8 new PII pattern types** to `etlpipe_governance.scan_pii()`:
  - US ABA routing numbers
  - Bank account numbers (6–17 digit)
  - SWIFT/BIC codes
  - Masked PAN numbers (PCI-DSS)
  - UK bank sort codes
  - Australian BSB codes
  - US EIN / TIN numbers
  - Internal Customer / CIF identifiers
- **Total patterns**: 20 (12 original international + 8 banking extensions)
- **Frameworks covered**: GDPR, HIPAA, SOX, CCPA, PCI-DSS

#### 4. HTTPS Enforcement (`InsecureURLError`)
- **Risk**: Plain HTTP connections expose data-in-transit to man-in-the-middle attacks.
- **Fix**: `Developer.download()` now raises `InsecureURLError` for any `http://` URL. SSL certificate verification is enabled by default via `ssl.create_default_context()`.
- **Override**: Pass `allow_http=True` for internal/dev-only endpoints. This emits a `SecurityWarning` — it must never be used in production.

#### 5. SIEM Audit Forwarding
- **Added pluggable `AuditForwarder` interface** to `AuditTrail` for real-time SIEM integration:
  - `SplunkHECForwarder` — Splunk HTTP Event Collector (zero-dependency, uses stdlib `urllib`)
  - `WebhookForwarder` — Microsoft Teams, Slack, PagerDuty (any HTTP webhook)
  - `S3Forwarder` — AWS S3 JSONL audit log upload (requires `etlpipe[cloud]`)
- **Resilience**: Forwarder failures are logged as errors but never interrupt pipeline execution or local log writes.
- **Compliance**: Satisfies SOX Section 404 (IT control audit trails) and MiFID II data lineage requirements.

#### 6. Data Lineage (BCBS 239 / OpenLineage)
- **Added `LineageCollector`** in `etlpipe._lineage` that records per-step I/O schemas, row counts, and durations as OpenLineage-compatible `RunEvent` dicts.
- **Marquez support**: `LineageCollector.emit_to_marquez(url)` pushes events to a Marquez lineage server.
- **BCBS 239**: Satisfies Risk Data Aggregation and Risk Reporting requirements for systemically important banks.

#### 7. RBAC Pipeline Guard
- **Added `PipelineGuard` interface** in `etlpipe._rbac` for pre-execution access control:
  - `PipelineGuard(role_checker=...)` — plug in any IAM/LDAP callable
  - `EnvRoleGuard` — env-var based role matching (works with Kubernetes service accounts)
  - `AllowAllGuard` — backward-compatible default (no access control)
- **Fail-safe**: IAM service failures raise `AccessDeniedError` by default (fail-closed, not fail-open).

#### 8. Encrypted Pseudonymise Mapping Storage
- **`save_mapping()` / `load_mapping()`** in `etlpipe_governance.pii` for secure storage of the reverse-mapping table produced by `mask_pii(..., strategy="pseudonymise")`.
- **Encryption**: AES-256-GCM with PBKDF2-HMAC-SHA256 key derivation (480,000 iterations, NIST SP 800-132 compliant) via the `cryptography` library.
- **Warning**: Storing without `encrypt_key` emits `MappingSecurityWarning`.

#### 9. Comprehensive Security Test Suite
- **58 security-specific tests** in `tests/test_security.py` covering all 8 components above.
- **Integrated into CI** — all 496 tests must pass on every PR.

---

### v1.0.0 — Critical RCE Fix

- **Issue**: `Preparation.formula()` had an `eval()` fallback that allowed arbitrary code execution via crafted expression strings.
- **Fix**: Removed `eval()` entirely. Engine now uses sandboxed `pd.eval()` (Pandas) and `F.expr()` (Spark SQL) exclusively. Complex logic requires explicit `lambda` callables.
- **CVE**: N/A (caught during internal audit before any known exploitation)
- **ADR**: See [ADR 002](doc/adr/002-security-eval-removal.md) for full context.

---

## Security Measures in CI/CD

Etlpipe's CI pipeline includes automated security scanning on every push and PR:

- **[Bandit](https://bandit.readthedocs.io/)** — Static security analysis of Python source code
- **[pip-audit](https://pypi.org/project/pip-audit/)** — Dependency vulnerability scanning against the OSV database
- **OIDC Trusted Publishing** — PyPI releases use GitHub OIDC tokens (no stored secrets)
- **`yaml.safe_load()`** — YAML parsing uses safe loader to prevent code injection
- **`defusedxml`** — XML parsing uses defusedxml to prevent XXE attacks
- **Pickle blocked** — `.pkl`/`.pickle` raise `PickleRemovedError` (CWE-502 closed permanently)
- **HTTPS enforced** — `Developer.download()` rejects plain HTTP URLs by default
- **SSL cert verification** — `ssl.create_default_context()` used on all outbound connections

---

## Best Practices for Deployment in Banks / Big 4 Firms

### Credentials & Secrets
- **Never hardcode credentials** in pipeline YAML or Python files.
- Use `${ENV_VAR}` tokens in YAML, resolved automatically by `etlpipe._secrets`.
- Inject secrets via your bank's secret manager: AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, CyberArk.

### PII & Data Privacy
- **Always run `scan_pii()`** before writing DataFrames to any storage that is not pre-classified as a PII-permitted store.
- **Mask before sharing**: use `mask_pii(df, report, strategy="redact")` for logs and `strategy="hash"` for referential integrity checks.
- **Encrypt pseudonymise mappings**: use `save_mapping(..., encrypt_key=os.environ["MAPPING_KEY"])`.

### Access Control
- **Wire up an RBAC guard** using `PipelineGuard` connected to your bank's IAM or LDAP service.
- Never use `AllowAllGuard` in production — it is provided for backward compatibility and local development only.

### Audit & Lineage
- **Register a `SplunkHECForwarder`** (or equivalent) with `AuditTrail` to stream governance results to your SIEM.
- **Use `LineageCollector`** with Marquez or Apache Atlas to satisfy BCBS 239 data lineage mandates.

### Network Security
- All calls to `Developer.download()` must use HTTPS endpoints.
- If internal endpoints use self-signed certificates, configure trust anchors via `ssl.create_default_context(cafile="internal-ca.pem")` and pass the context manually.

### Schema Contracts
- **Use `expect_schema()`** to enforce data contracts and prevent schema drift at every pipeline checkpoint.
- **Use `expect_row_count()` and `expect_freshness()`** to detect feed truncation and stale data before it propagates downstream.
