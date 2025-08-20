# Standardized Testing & Development Guide

## Overview

This guide documents the **unified testing and development practices** implemented across all Petrosa services:

- **petrosa-bot-ta-analysis**: Technical Analysis bot
- **petrosa-tradeengine**: Cryptocurrency trading engine
- **petrosa-binance-data-extractor**: Data extraction system

All services now follow **identical commands, configurations, and quality standards**.

---

## 🚀 Quick Start

### 1. Initial Setup
```bash
# Complete environment setup (installs dependencies + pre-commit hooks)
make setup
```

### 2. Development Workflow
```bash
# Quick development cycle
make dev
```

### 3. Full Pipeline
```bash
# Complete CI/CD pipeline simulation
make pipeline
```

---

## 📋 Standardized Commands

### Setup & Installation
| Command | Description | All Services |
|---------|-------------|--------------|
| `make setup` | Complete environment setup with pre-commit | ✅ |
| `make install` | Install production dependencies | ✅ |
| `make install-dev` | Install development dependencies | ✅ |
| `make clean` | Clean up cache and temporary files | ✅ |

### Code Quality
| Command | Description | All Services |
|---------|-------------|--------------|
| `make format` | Format code with black and isort | ✅ |
| `make lint` | Run linting checks (flake8, ruff) | ✅ |
| `make type-check` | Run type checking with mypy | ✅ |
| `make pre-commit` | Run pre-commit hooks on all files | ✅ |
| `make pre-commit-install` | Install pre-commit hooks | ✅ |

### Testing
| Command | Description | All Services |
|---------|-------------|--------------|
| `make unit` | Run unit tests only | ✅ |
| `make integration` | Run integration tests only | ✅ |
| `make e2e` | Run end-to-end tests only | ✅ |
| `make test` | Run all tests with coverage (80% threshold) | ✅ |
| `make coverage` | Generate coverage reports | ✅ |
| `make coverage-html` | Generate HTML coverage report | ✅ |
| `make coverage-check` | Check coverage threshold | ✅ |

### Security
| Command | Description | All Services |
|---------|-------------|--------------|
| `make security` | Run security scans (bandit, safety, trivy) | ✅ |

### Docker
| Command | Description | All Services |
|---------|-------------|--------------|
| `make build` | Build Docker image | ✅ |
| `make container` | Test Docker container | ✅ |
| `make docker-clean` | Clean up Docker images | ✅ |

### Deployment
| Command | Description | All Services |
|---------|-------------|--------------|
| `make deploy` | Deploy to Kubernetes cluster | ✅ |
| `make pipeline` | Run complete CI/CD pipeline | ✅ |

### Utilities
| Command | Description | All Services |
|---------|-------------|--------------|
| `make k8s-status` | Check Kubernetes deployment status | ✅ |
| `make k8s-logs` | View Kubernetes logs | ✅ |
| `make k8s-clean` | Clean up Kubernetes resources | ✅ |

---

## 🔧 Standardized Configurations

### 1. Development Dependencies (`requirements-dev.txt`)

All services use **identical versions** of development tools:

```txt
# Testing Framework
pytest==7.4.4
pytest-cov==4.1.0
pytest-asyncio==0.23.5
pytest-mock==3.12.0
pytest-timeout==2.1.0
pytest-xdist==3.5.0
pytest-html==4.1.1

# Code Quality & Formatting
black==23.12.1
ruff==0.1.15
flake8==7.0.0
isort==5.13.2
mypy==1.8.0

# Security Scanning
bandit==1.7.5
safety==2.3.5
trivy==0.48.4

# Pre-commit & Git Hooks
pre-commit==3.6.0

# Type Checking Stubs
types-requests==2.31.0.20240125
types-python-dateutil==2.8.19.20240106
types-PyYAML==6.0.12.12

# Coverage & Reporting
coverage==7.4.1
codecov==2.1.13
```

### 2. Pytest Configuration (`pytest.ini`)

Standardized test configuration across all services:

```ini
[tool:pytest]
# Test execution options
addopts =
    -v
    --strict-markers
    --strict-config
    --disable-warnings
    --tb=short
    --timeout=300
    --durations=10
    --maxfail=10
    --cov=.
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
    --cov-fail-under=80

# Test markers
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (require external services)
    e2e: End-to-end tests (full workflow)
    slow: Slow running tests (>5 seconds)
    performance: Performance tests
    security: Security tests
    smoke: Smoke tests (basic functionality)
    regression: Regression tests

# Environment variables for tests
env =
    ENVIRONMENT=testing
    LOG_LEVEL=DEBUG
    OTEL_NO_AUTO_INIT=1
```

### 3. Pre-commit Configuration (`.pre-commit-config.yaml`)

Comprehensive security and quality checks:

```yaml
# Black code formatter
- repo: https://github.com/psf/black
  rev: 23.12.1
  hooks:
    - id: black
      language_version: python3.11
      args: [--line-length=88]

# Ruff linter
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.1.15
  hooks:
    - id: ruff
      args: [--fix, --exit-non-zero-on-fix]
    - id: ruff-format

# MyPy type checker
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.8.0
  hooks:
    - id: mypy
      additional_dependencies: [types-requests, types-python-dateutil, types-PyYAML]
      args: [--ignore-missing-imports, --strict]

# Security checks
- repo: https://github.com/PyCQA/bandit
  rev: 1.7.5
  hooks:
    - id: bandit
      args: [-r, ., -f, json, -o, bandit-report.json, -ll]
      exclude: ^tests/

# Credential detection
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v4.5.0
  hooks:
    - id: detect-private-key
    - id: detect-aws-credentials
    - id: detect-gcp-credentials
    - id: detect-azure-credentials
```

### 4. Ruff Configuration (`ruff.toml`)

Consistent linting rules:

```toml
# Target Python version
target-version = "py311"

# Line length
line-length = 88

# Flake8 compatibility
[lint.flake8]
max-line-length = 88
extend-ignore = [
    "E501",  # line too long, handled by black
    "B008",  # do not perform function calls in argument defaults
    "C901",  # too complex
    "B904",  # Within an `except` clause, raise exceptions with `raise ... from err`
]

# Per-file ignores
[lint.per-file-ignores]
"__init__.py" = ["F401"]
"tests/**/*" = ["S101", "PLR0913", "PLR0915"]
```

---

## 🧪 Testing Standards

### Coverage Requirements

- **Minimum Coverage**: 80% across all services
- **Enforcement**: CI/CD pipeline fails if coverage < 80%
- **Reporting**: HTML, XML, and terminal reports generated

### Test Categories

1. **Unit Tests** (`@pytest.mark.unit`)
   - Fast, isolated tests
   - No external dependencies
   - Test individual functions/classes

2. **Integration Tests** (`@pytest.mark.integration`)
   - Test component interactions
   - May require external services
   - Test database, API integrations

3. **End-to-End Tests** (`@pytest.mark.e2e`)
   - Test complete workflows
   - Full system integration
   - Production-like scenarios

4. **Performance Tests** (`@pytest.mark.performance`)
   - Load testing
   - Benchmarking
   - Resource usage monitoring

5. **Security Tests** (`@pytest.mark.security`)
   - Vulnerability scanning
   - Authentication/authorization
   - Input validation

### Test Naming Conventions

```python
# Test file naming
test_<module_name>.py
test_<component>_integration.py
test_<workflow>_e2e.py

# Test class naming
class Test<ClassName>:
    """Test cases for <ClassName>."""

# Test method naming
def test_<functionality>_<scenario>():
    """Test <functionality> when <scenario>."""
```

---

## 🔒 Security Standards

### Pre-commit Security Checks

1. **Bandit**: Python security linting
2. **Safety**: Dependency vulnerability scanning
3. **Trivy**: Container and filesystem scanning
4. **Credential Detection**: AWS, GCP, Azure credentials
5. **Private Key Detection**: SSH and other private keys

### Security Requirements

- **No hardcoded credentials** in code
- **All dependencies scanned** for vulnerabilities
- **Container images scanned** for security issues
- **Regular security audits** via CI/CD

---

## 🚀 CI/CD Pipeline

### Standard Pipeline Steps

1. **Dependencies Installation**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

2. **Pre-commit Checks**
   ```bash
   pre-commit run --all-files
   ```

3. **Code Quality Checks**
   ```bash
   make format
   make lint
   make type-check
   ```

4. **Testing**
   ```bash
   make test  # Includes coverage threshold check
   ```

5. **Security Scanning**
   ```bash
   make security
   ```

6. **Docker Build & Test**
   ```bash
   make build
   make container
   ```

7. **Deployment**
   ```bash
   make deploy
   ```

### Pipeline Commands

```bash
# Run complete pipeline locally
make pipeline

# Run individual pipeline stages
make format lint type-check test security build container
```

---

## 📊 Quality Metrics

### Coverage Targets

| Service | Current Coverage | Target | Status |
|---------|------------------|--------|--------|
| petrosa-binance-data-extractor | 58% | 80% | ⚠️ Below threshold |
| petrosa-bot-ta-analysis | 47% | 80% | ⚠️ Below threshold |
| petrosa-tradeengine | Unknown | 80% | ❓ Not measured |

### Quality Gates

1. **Code Coverage**: ≥80% (enforced)
2. **Type Coverage**: 100% (enforced)
3. **Security Scan**: 0 critical vulnerabilities
4. **Linting**: 0 critical errors
5. **Pre-commit**: All hooks pass

---

## 🛠️ Development Workflows

### Daily Development

```bash
# 1. Setup (first time only)
make setup

# 2. Development cycle
make dev  # Runs: setup format lint type-check test

# 3. Before committing
make pre-commit

# 4. Before pushing
make pipeline
```

### Feature Development

```bash
# 1. Create feature branch
git checkout -b feature/new-feature

# 2. Development
make dev

# 3. Add tests
make unit
make integration

# 4. Quality checks
make format lint type-check

# 5. Full testing
make test

# 6. Security check
make security

# 7. Commit and push
git add .
make pre-commit
git commit -m "feat: add new feature"
git push
```

### Bug Fixes

```bash
# 1. Create bug fix branch
git checkout -b fix/bug-description

# 2. Reproduce and fix
make test  # Verify bug exists

# 3. Fix the issue
# ... code changes ...

# 4. Add regression test
# ... test code ...

# 5. Verify fix
make test

# 6. Quality checks
make format lint type-check security

# 7. Commit and push
git add .
make pre-commit
git commit -m "fix: resolve bug description"
git push
```

---

## 📚 Best Practices

### Code Quality

1. **Write tests first** (TDD approach)
2. **Use type hints** consistently
3. **Follow PEP 8** and project style guides
4. **Document functions** and classes
5. **Keep functions small** and focused

### Testing

1. **Test both success and failure** scenarios
2. **Use realistic test data**
3. **Mock external dependencies**
4. **Test edge cases** and boundary conditions
5. **Keep tests fast** and isolated

### Security

1. **Never commit credentials**
2. **Use environment variables** for secrets
3. **Validate all inputs**
4. **Use parameterized queries** (SQL injection prevention)
5. **Keep dependencies updated**

### Git Workflow

1. **Use conventional commits**
2. **Write descriptive commit messages**
3. **Run pre-commit hooks** before committing
4. **Create feature branches** for new work
5. **Review code** before merging

---

## 🎯 Next Steps

### Immediate Actions

1. **Install pre-commit hooks** on all development machines
2. **Run full pipeline** on all services
3. **Address coverage gaps** to reach 80% threshold
4. **Fix any security issues** identified by scans

### Ongoing Improvements

1. **Add integration tests** for external service interactions
2. **Implement performance tests** for critical paths
3. **Add end-to-end tests** for complete workflows
4. **Monitor and improve** test execution times

### Long-term Goals

1. **Achieve 90%+ coverage** across all services
2. **Implement mutation testing** for test quality
3. **Add chaos engineering** tests for resilience
4. **Automate performance regression** detection

---

## 📞 Support

For questions or issues with the standardized testing setup:

1. **Check this guide** for common solutions
2. **Review service-specific documentation** in each project
3. **Run `make help`** for available commands
4. **Check CI/CD logs** for detailed error information

---

**Last Updated**: January 2025
**Version**: 1.0
**Status**: Active Implementation
