# BAET CI/CD Plan

## Overview
This document outlines the Continuous Integration and Continuous Deployment (CI/CD) strategy for BAET (Binance Adaptive Ensemble Trader). The plan is designed to ensure code quality, automate testing, and enable safe progression from development through paper trading to live deployment.

---

## 1. CI/CD Pipeline Architecture

### 1.1 Pipeline Stages
```
┌─────────────┐     ┌──────────────┐     ┌────────────┐     ┌──────────┐     ┌──────────┐
│   Commit    │ ──> │ Code Quality │ ──> │  Unit &    │ ──> │  Build   │ ──> │ Deploy   │
│   Push      │     │   Checks     │     │ Integration│     │ Package  │     │ & Test   │
└─────────────┘     └──────────────┘     └────────────┘     └──────────┘     └──────────┘
                           │                     │                 │               │
                           └─ Lint              └─ Test            └─ Artifact     └─ Dev/Test/Prod
                           └─ Type Check        └─ Coverage        └─ Publish         └─ Monitoring
                           └─ Format            └─ Integration
```

### 1.2 Environments

| Environment | Purpose | Triggers | Deployment |
|---|---|---|---|
| **Development** | Local testing and feature development | Manual / Push to feature branch | Local (developer machine) |
| **Test** | Automated testing and validation | Push to `dev` branch | GitHub Actions / Automated |
| **Staging/Paper** | Paper trading validation | Push to `staging` branch | Staging server / Paper trading mode |
| **Production** | Live trading with capital at risk | Manual release tag | Production server / Live mode |

---

## 2. Code Quality & Linting (Pre-Push)

### 2.1 Tools
- **Ruff**: Fast Python linter and formatter (replaces Black, isort, flake8)
- **Type Checking**: MyPy for static type analysis
- **Security**: Bandit for security vulnerability scanning
- **Pre-commit**: Local enforcement of all quality checks before commit

### 2.2 Workflow

#### Local (Pre-commit)
```bash
# Format code
uv run ruff format src/ tests/

# Check linting
uv run ruff check src/ tests/ --fix

# Type checking
uv run mypy src/ --strict

# Run security checks (bandit or similar)
uv run bandit -r src/
```

#### CI Gateway
Create `.pre-commit-config.yaml` for local enforcement:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
        args: [--strict]
        additional_dependencies: [types-PyYAML, pandas-stubs]
```

---

## 3. Testing Strategy

### 3.1 Test Pyramid
```
           ┌──────────────┐
           │  E2E Tests   │  (Few, slow, integration)
           ├──────────────┤
           │  Integration │  (Moderate, moderate speed)
           │    Tests     │
           ├──────────────┤
           │  Unit Tests  │  (Many, fast)
           └──────────────┘
```

### 3.2 Test Categories

#### Unit Tests (Fast - <1 min total)
- Individual functions and classes
- Data models and validation
- Configuration loading
- Feature engineering components
- Risk calculations

**Location**: `tests/test_*.py`
**Command**: `uv run pytest tests/ -v --cov=src/baet`
**Current**: 203 tests passing (as of May 2026)

#### Integration Tests (Moderate - 5-15 min)
- Data pipeline integration
- Strategy execution with sample data
- Backtesting pipeline
- Reporting generation
- Config + strategy combinations

**Location**: `tests/test_*_integration.py`
**Command**: `uv run pytest tests/ -k integration -v`

#### E2E Tests (Slow - 15+ min)
- Full backtest runs with multiple strategies
- Paper trading validation (live Binance testnet)
- Dashboard rendering
- Historical data ingestion and processing

**Location**: `tests/test_e2e_*.py` (optional, can be run on schedule)
**Command**: `uv run pytest tests/test_e2e_*.py -v`

### 3.3 Coverage Requirements
- **Minimum**: 70% coverage
- **Target**: 80%+ coverage
- **Critical paths**: 95% (execution, risk, strategy engine)

**Coverage Report**:
```bash
uv run pytest tests/ --cov=src/baet --cov-report=html --cov-report=term-missing
```

### 3.4 Test Execution Matrix
| Python Version | Environment | Status |
|---|---|---|
| 3.13 (Current) | Linux (Ubuntu) | ✓ Required |
| 3.13 | Windows | ✓ Required |
| 3.13 | macOS | ⭕ Recommended |

---

## 4. GitHub Actions Workflows

### 4.1 Main Workflow: `test.yml`
**Trigger**: Push to `main`, `dev`, `staging` + PR

```yaml
name: Test & Quality Checks

on:
  push:
    branches: [main, dev, staging]
  pull_request:
    branches: [main, dev, staging]

jobs:
  code-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v2
      - name: Check formatting
        run: uv run ruff format --check src/ tests/
      - name: Lint
        run: uv run ruff check src/ tests/
      - name: Type checking
        run: uv run mypy src/ --strict
      - name: Security scan
        run: uv run bandit -r src/ -f json -o bandit-report.json

  unit-tests:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        python-version: ['3.13']
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v2
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: uv sync --all-extras
      - name: Run unit tests
        run: uv run pytest tests/ -v --cov=src/baet --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: unittests
          name: codecov-umbrella

  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v2
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: uv sync --all-extras
      - name: Run integration tests
        run: uv run pytest tests/ -k integration -v
        timeout-minutes: 15
```

### 4.2 E2E Testing Workflow: `e2e-tests.yml`
**Trigger**: Scheduled (daily) + Manual

```yaml
name: E2E Tests

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM daily
  workflow_dispatch:

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v2
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: uv sync --all-extras
      - name: Run E2E tests
        run: uv run pytest tests/test_e2e_*.py -v --timeout=600
        timeout-minutes: 20
      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-results
          path: test-results/
```

### 4.3 Build Workflow: `build.yml`
**Trigger**: Push to `main` + Release tags

```yaml
name: Build & Package

on:
  push:
    branches: [main]
    tags: ['v*']
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v2
        with:
          python-version: '3.13'
      - name: Build distribution
        run: |
          uv build
      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: distributions
          path: dist/
      - name: Publish to PyPI (on tag)
        if: startsWith(github.ref, 'refs/tags/v')
        run: |
          uv publish
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.PYPI_TOKEN }}
```

### 4.4 Paper Trading Validation: `paper-trading.yml`
**Trigger**: Manual deployment to staging

```yaml
name: Paper Trading Validation

on:
  workflow_dispatch:
    inputs:
      duration_hours:
        description: 'Duration of paper trading test (hours)'
        required: true
        default: '1'

jobs:
  paper-trading-validation:
    runs-on: ubuntu-latest
    env:
      BAET_MODE: paper
      BAET_PAPER_DURATION_HOURS: ${{ github.event.inputs.duration_hours }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v2
        with:
          python-version: '3.13'
      - name: Load secrets
        env:
          BINANCE_API_KEY: ${{ secrets.BINANCE_TESTNET_KEY }}
          BINANCE_API_SECRET: ${{ secrets.BINANCE_TESTNET_SECRET }}
        run: |
          echo "BINANCE_API_KEY=$BINANCE_API_KEY" >> .env
          echo "BINANCE_API_SECRET=$BINANCE_API_SECRET" >> .env
      - name: Install dependencies
        run: uv sync --all-extras
      - name: Run paper trading
        run: uv run python -m baet --mode paper --duration ${{ github.event.inputs.duration_hours }}
      - name: Validate results
        run: uv run python scripts/validate_paper_trading.py
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: paper-trading-logs
          path: logs/paper/
```

---

## 5. Deployment Strategy

### 5.1 Branch-Based Deployment

| Branch | Environment | Conditions | Action |
|---|---|---|---|
| **feature/** | Dev | Manual | Run locally |
| **dev** | Test | Auto (all tests pass) | Deploy to test env |
| **staging** | Paper Trading | Manual approval | Deploy to paper trading server |
| **main** | Production | Tag + approval | Deploy to live trading server |
| **hotfix/** | Immediate | Urgent fixes only | Fast-track to main |

### 5.2 Release Process

1. **Feature Development**
   - Branch: `feature/feature-name`
   - PR to `dev`
   - All tests must pass
   - Minimum 1 code review approval

2. **Testing Phase**
   - Branch: `dev`
   - Deployed automatically on merge
   - Run E2E tests
   - Monitor for 24-48 hours

3. **Paper Trading Phase**
   - Branch: `staging`
   - Manual PR from `dev` to `staging`
   - Run paper trading for 5-7 days
   - Verify no regressions

4. **Production Release**
   - Create release tag: `git tag -a v0.2.0 -m "Release v0.2.0"`
   - Push tag: `git push origin v0.2.0`
   - Manual approval in GitHub
   - Deploy to production (paper trading mode initially)
   - Monitor for 24+ hours before live trading

### 5.3 Rollback Strategy

```yaml
# .github/workflows/rollback.yml
name: Rollback Deployment

on:
  workflow_dispatch:
    inputs:
      target_commit:
        description: 'Commit to rollback to (SHA)'
        required: true

jobs:
  rollback:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.inputs.target_commit }}
      - name: Verify target commit
        run: git log -1 --oneline
      - name: Deploy from rollback commit
        run: |
          echo "Rolling back to commit: ${{ github.event.inputs.target_commit }}"
          # Deployment logic here
      - name: Notify team
        run: |
          echo "Rollback completed. Monitor alerts."
```

---

## 6. Monitoring & Observability

### 6.1 Metrics to Track

#### Build Metrics
- Build success rate (target: >98%)
- Build duration (target: <5 min for unit tests)
- Test coverage trend

#### Deployment Metrics
- Deployment frequency (target: weekly)
- Deployment success rate (target: 100%)
- Lead time for changes (feature → production)
- Mean time to recovery (MTTR) on failures

#### Trading Metrics (Post-Deploy)
- Paper trading P&L (should not be negative)
- Live trading drawdown (max <5%)
- Order success rate
- Strategy signal quality
- System uptime (target: >99.9%)

### 6.2 Monitoring Stack
- **Logs**: GitHub Actions logs + application logs (logs/ directory)
- **Metrics**: Prometheus/CloudWatch (optional, for production)
- **Alerting**: GitHub Actions notifications + email/Slack
- **Dashboard**: Custom Python script to summarize paper trading results

```bash
# scripts/generate_ci_report.py
# Generate weekly CI/CD performance report
```

---

## 7. Security & Secrets Management

### 7.1 Secret Handling

**GitHub Secrets to Configure**:
- `BINANCE_API_KEY` - Testnet key for E2E tests
- `BINANCE_API_SECRET` - Testnet secret
- `BINANCE_LIVE_API_KEY` - Live trading key (production only)
- `BINANCE_LIVE_API_SECRET` - Live trading secret (production only)
- `PYPI_TOKEN` - For publishing to PyPI

**Never commit**:
- `.env` files (use `.env.example` template)
- API keys or secrets
- Personal configuration

### 7.2 Code Scanning

```yaml
# .github/workflows/security.yml
name: Security Scan

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Bandit (security scan)
        run: uv run bandit -r src/ --json -o bandit-report.json
      - name: Run CodeQL
        uses: github/codeql-action/init@v2
        with:
          languages: ['python']
      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v2
```

---

## 8. Configuration Management

### 8.1 Environment Variables by Stage

**Development** (`.env`)
```env
BAET_MODE=dev
BINANCE_TESTNET=true
LOG_LEVEL=debug
PAPER_TRADING_ENABLED=false
```

**Testing** (GitHub Actions)
```env
BAET_MODE=test
BINANCE_TESTNET=true
LOG_LEVEL=info
SKIP_LIVE_CALLS=true
```

**Paper Trading** (Staging)
```env
BAET_MODE=paper
BINANCE_TESTNET=true
LOG_LEVEL=info
INITIAL_CAPITAL=1000
```

**Production** (Live)
```env
BAET_MODE=live
BINANCE_TESTNET=false
LOG_LEVEL=warning
INITIAL_CAPITAL=<actual_capital>
```

### 8.2 Config Management Best Practice
- Use `config/base.yaml` for defaults
- Use environment-specific configs: `config/{dev,test,paper,live}.yaml`
- Load via `ConfigLoader` with validation
- Never hardcode secrets - use environment variables

---

## 9. Documentation & Runbooks

### 9.1 Runbooks

Create in `docs/`:
- `DEPLOYMENT_RUNBOOK.md` - How to deploy manually
- `INCIDENT_RESPONSE.md` - What to do if trading fails
- `ROLLBACK_PROCEDURE.md` - Steps to rollback
- `PAPER_TRADING_CHECKLIST.md` - Pre-paper-trading validation

### 9.2 Change Log

Maintain `CHANGELOG.md`:
```markdown
## [0.2.0] - 2025-02-10
### Added
- Paper trading support
- Binance testnet integration

### Fixed
- Risk calculation bug in portfolio sizing

### Security
- Updated dependencies to patch CVE-2025-xxxx
```

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Set up GitHub Actions workflows (test.yml, build.yml)
- [ ] Add pre-commit hooks locally
- [ ] Configure pytest with coverage
- [ ] Set up codecov integration

### Phase 2: Quality Gates (Weeks 3-4)
- [ ] Add ruff linting to CI
- [ ] Add mypy type checking
- [ ] Implement code review requirements
- [ ] Add security scanning (bandit)

### Phase 3: Deployment Automation (Weeks 5-6)
- [ ] Create paper trading validation workflow
- [ ] Set up environment-based configs
- [ ] Document deployment procedure
- [ ] Test rollback strategy

### Phase 4: Monitoring & Observability (Weeks 7-8)
- [ ] Add performance metrics collection
- [ ] Create monitoring dashboard
- [ ] Set up alerting for paper trading
- [ ] Document troubleshooting procedures

### Phase 5: Production Ready (Weeks 9+)
- [ ] Achieve >98% test coverage
- [ ] Zero security issues in code scan
- [ ] Complete runbooks and documentation
- [ ] Dry-run full deployment pipeline
- [ ] Get stakeholder approval for live trading

---

## 11. Success Criteria

### For CI/CD Pipeline
- ✅ All new PRs must pass automated tests
- ✅ Code coverage maintained at >80%
- ✅ Zero critical security issues
- ✅ Build time <5 minutes
- ✅ Deployment to any environment <15 minutes

### For Trading System
- ✅ Paper trading runs stable for 7+ days
- ✅ No unexpected strategy failures
- ✅ Risk limits respected in all scenarios
- ✅ Logs are clean and debuggable
- ✅ Manual override works in all conditions

---

## 12. Tools & Resources

### Recommended Tools
- **GitHub Actions**: CI/CD orchestration (free, built-in)
- **Ruff**: Fast Python linting
- **MyPy**: Static type checking
- **Pytest**: Testing framework
- **Codecov**: Coverage tracking
- **Bandit**: Security scanning
- **uv**: Package management (already in use)

### Documentation
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Pytest Documentation](https://docs.pytest.org/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [MyPy Documentation](https://www.mypy-lang.org/)

---

## 13. Appendix: Command Reference

```bash
# Local testing
uv run pytest tests/ -v --cov=src/baet

# Linting & formatting
uv run ruff format src/ tests/
uv run ruff check src/ tests/ --fix
uv run mypy src/ --strict

# Building
uv build

# Running application
uv run python -m baet --mode paper
uv run python -m baet --mode live

# Git commands for releases
git flow release start 0.2.0
git flow release finish 0.2.0
# Or simply
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0
```

---

**Document Version**: 1.0
**Last Updated**: May 13, 2026
**Owner**: BAET Team
**Status**: Draft - Ready for Implementation
