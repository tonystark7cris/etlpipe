# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | ✅ Active support  |
| 0.2.x   | ⚠️ Critical fixes only |
| < 0.2   | ❌ End of life     |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them privately via email:

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

## Security Track Record

Etlpipe takes security seriously. Past security fixes include:

### v1.0.0 — Critical RCE Fix

- **Issue**: `Preparation.formula()` had an `eval()` fallback that allowed arbitrary code execution via crafted expression strings.
- **Fix**: Removed `eval()` entirely. Engine now uses sandboxed `pd.eval()` (Pandas) and `F.expr()` (Spark SQL) exclusively. Complex logic requires explicit `lambda` callables.
- **CVE**: N/A (caught during internal audit before any known exploitation)
- **ADR**: See [ADR 002](doc/adr/002-security-eval-removal.md) for full context.

## Security Measures in CI/CD

Etlpipe's CI pipeline includes automated security scanning on every push and PR:

- **[Bandit](https://bandit.readthedocs.io/)** — Static security analysis of Python source code
- **[pip-audit](https://pypi.org/project/pip-audit/)** — Dependency vulnerability scanning against the OSV database
- **OIDC Trusted Publishing** — PyPI releases use GitHub OIDC tokens (no stored secrets)
- **`yaml.safe_load()`** — YAML parsing uses safe loader to prevent code injection
- **`defusedxml`** — XML parsing uses defusedxml to prevent XXE attacks
- **Pickle deprecation** — Pickle format support is deprecated (CWE-502) and will be removed in v2.0

## Best Practices for Users

- **Never hardcode credentials** in pipeline code or YAML files. Use environment variables or a secret manager (AWS Secrets Manager, HashiCorp Vault, Azure Key Vault).
- **Use `scan_pii()`** to detect PII in DataFrames before writing to non-secure storage.
- **Use `expect_schema()`** to enforce data contracts and prevent schema drift.
- **Use `Developer.test()`** to validate data assertions before outputting results.
