# Contributing to etlpipe

Thank you for your interest in contributing to etlpipe! This guide will help you get started.

---

## Development Setup

### Prerequisites

- Python 3.10+
- Git

### Getting Started

```bash
# Clone the repository
git clone https://github.com/tonystark7cris/etlpipe.git
cd etlpipe

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install with development dependencies
pip install -e ".[dev]"

# Verify installation
pytest tests/ -v
```

---

## Code Standards

### Style & Formatting

etlpipe uses **[Ruff](https://docs.astral.sh/ruff/)** for both linting and formatting. Configuration is in [pyproject.toml](pyproject.toml):

- **Target**: Python 3.10
- **Line length**: 120 characters
- **Lint rules**: E, F, I, W, UP, B, SIM

```bash
# Check formatting
ruff format --check src/ tests/

# Auto-format
ruff format src/ tests/

# Run linter
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/
```

### Type Hints

All public methods **must** have full type annotations. Use `from __future__ import annotations` at the top of every module.

### Docstrings

All public methods **must** have Google-style docstrings including:
- One-line summary
- `Args:` section with parameter descriptions
- `Returns:` section
- `Raises:` section (if applicable)
- `Example:` section with a short usage snippet

### Immutability

All etlpipe tool functions **must** be pure â€” they return new DataFrames and never mutate inputs. This is a core architectural invariant.

---

## Testing

### Running Tests

```bash
# Full test suite with coverage
pytest tests/ -v --cov=etlpipe --cov-report=term-missing

# Run specific test file
pytest tests/test_preparation.py -v

# Run a single test
pytest tests/test_contracts.py::TestExpectSchemaPass::test_round_trip -v
```

### Writing Tests

- Place test files in `tests/` with the naming convention `test_<module>.py`
- Use shared fixtures from `tests/conftest.py` where possible
- Test both happy paths and error cases
- For dual-engine features, ensure Pandas tests exist (Spark tests are optional but encouraged)

### Coverage Requirements

New code should maintain or improve overall test coverage. Critical paths (security, data contracts, PII scanning) require >90% coverage.

---

## Architecture

### Engine Pattern

etlpipe uses an abstract **BackendEngine** pattern:

1. **Public API** classes (`Preparation`, `Join`, etc.) are thin dispatchers
2. They call `get_engine()` to obtain the active backend
3. The backend (`PandasEngine` or `SparkEngine`) contains the actual implementation
4. Both backends inherit from `BackendEngine` (ABC)

When adding a new tool:
1. Add the abstract method signature to `engines/base.py`
2. Implement in `engines/pandas_engine.py`
3. Implement in `engines/spark_engine.py`
4. Add the public static method to the appropriate palette class
5. Add tests for both backends

### Architecture Decision Records

Significant design decisions are documented as ADRs in `doc/adr/`. When proposing a major change, create a new ADR using the template at `doc/adr/000-template.md`.

---

## Pull Request Process

1. **Branch**: Create a feature branch from `main` (e.g., `feature/add-pivot-tool`)
2. **Implement**: Make your changes following the code standards above
3. **Test**: Ensure all tests pass and add new tests for your changes
4. **Lint**: Run `ruff format` and `ruff check` before pushing
5. **PR**: Open a pull request with:
   - Clear description of what changed and why
   - Link to any related issues
   - Screenshots/examples if applicable
6. **Review**: Address review feedback promptly
7. **Merge**: Squash-merge after approval

---

## Release Process

etlpipe follows [Semantic Versioning](https://semver.org/):

- **PATCH** (1.0.x): Bug fixes, no API changes
- **MINOR** (1.x.0): New features, backward-compatible
- **MAJOR** (x.0.0): Breaking API changes

### Release Checklist

1. Update `src/etlpipe/_version.py` with the new version
2. Update `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/) format
3. Create a GitHub Release with a tag matching the version (e.g., `v1.1.0`)
4. The CI/CD pipeline will automatically publish to PyPI via OIDC Trusted Publishing

---

## Security

If you discover a security vulnerability, please report it privately. See [SECURITY.md](SECURITY.md) for details.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
