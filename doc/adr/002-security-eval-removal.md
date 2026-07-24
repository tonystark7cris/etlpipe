# ADR 002: Removal of `eval()` — Security Hardening

## Status

**ACCEPTED**

*Date: 2026-07-04*

## Context

The original `Preparation.formula()` implementation used Python's built-in `eval()` as a fallback when `pd.eval()` failed to parse a user-provided expression string. This created an **arbitrary code execution (RCE)** vulnerability — any string passed to `formula()` could execute arbitrary Python code on the host system.

Example of the vulnerability:
```python
# This would execute os.system() on the server
Preparation.formula(df, "Exploit", "__import__('os').system('rm -rf /')")
```

This is classified as **CWE-94: Improper Control of Generation of Code** and is a critical security risk, especially in enterprise environments where pipeline inputs may come from external YAML files or user-facing interfaces.

## Decision

1. **Remove `eval()` entirely** from the formula evaluation path
2. **Use `pd.eval()` exclusively** for string expressions — it only supports arithmetic/comparison operations on DataFrame columns, not arbitrary Python code
3. **Support `lambda` callables** as an alternative for complex logic that `pd.eval()` cannot handle
4. **Auto-backtick column names** containing spaces so that `pd.eval()` can handle real-world enterprise datasets with messy headers

The Spark engine uses `F.expr()` (Spark SQL expressions) which is similarly sandboxed.

## Consequences

### Positive

- Eliminates the RCE vulnerability completely
- `pd.eval()` is significantly faster than `eval()` for DataFrame operations (uses numexpr)
- Passes `bandit` static security analysis without exceptions
- Lambda callables provide full Python expressiveness when needed, but require explicit code (not string injection)

### Negative

- Some complex string expressions that worked with `eval()` will no longer work with `pd.eval()` — users must convert these to lambda callables
- `pd.eval()` has limitations (no method calls, no string operations) — this is by design for security

### Neutral

- The migration path is well-documented: any `eval()`-dependent expression can be trivially rewritten as a `lambda`
