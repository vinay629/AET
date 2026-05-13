# Contributing to BAET

Welcome! This guide helps you contribute to BAET (Binance Adaptive Ensemble Trader) effectively.

## Table of Contents
1. [Quick Start](#quick-start)
2. [Development Workflow](#development-workflow)
3. [Code Quality Standards](#code-quality-standards)
4. [Testing Requirements](#testing-requirements)
5. [Pull Request Process](#pull-request-process)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/vinay629/AET.git
cd AET
```

### 2. Set Up Development Environment
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
# or on Windows
irm https://astral.sh/uv/install.ps1 | iex

# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### 3. Verify Setup
```bash
# Run tests locally
uv run pytest tests/ -v

# Check code quality
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
uv run mypy src/ --strict
```

If all pass ✅, you're ready to develop!

---

## Development Workflow

### Branch Naming Convention

| Type | Format | Example |
|---|---|---|
| Feature | `feature/short-description` | `feature/add-risk-limits` |
| Bug Fix | `fix/issue-description` | `fix/strategy-timeout` |
| Hotfix | `hotfix/urgent-fix` | `hotfix/order-execution-bug` |
| Chore | `chore/task-name` | `chore/update-dependencies` |
| Documentation | `docs/topic` | `docs/api-guide` |

### Step 1: Create Feature Branch
```bash
# Always start from main and pull latest
git checkout main
git pull origin main

# Create your feature branch
git checkout -b feature/my-feature
```

### Step 2: Make Changes

**Code Style**:
- Follow PEP 8
- Use type hints throughout
- Maximum line length: 100 characters
- Use descriptive variable/function names

**Example**:
```python
def calculate_portfolio_risk(
    positions: dict[str, float],
    confidence: float = 0.95
) -> float:
    """Calculate portfolio risk using Value at Risk.

    Args:
        positions: Symbol to quantity mapping
        confidence: Confidence level (0-1)

    Returns:
        Risk estimate in USD

    Raises:
        ValueError: If confidence not in [0, 1]
    """
    if not 0 <= confidence <= 1:
        raise ValueError(f"Confidence must be in [0, 1], got {confidence}")

    # Implementation...
    return risk_value
```

### Step 3: Test Your Changes

```bash
# Run all tests
uv run pytest tests/ -v --cov=src/baet

# Run specific test
uv run pytest tests/test_risk.py::TestRiskEngine::test_max_position_size -v

# Run only unit tests (fast)
uv run pytest tests/ -m unit -v
```

**Coverage Target**:
- Minimum: 80% overall
- Critical paths (execution, risk): 95%+

### Step 4: Code Quality Checks

Pre-commit hooks run automatically on commit, but you can run manually:

```bash
# Format code
uv run ruff format src/ tests/

# Check formatting
uv run ruff format --check src/ tests/

# Lint code
uv run ruff check src/ tests/ --fix

# Type checking
uv run mypy src/ --strict

# Security scan
uv run bandit -r src/

# All checks at once
pre-commit run --all-files
```

### Step 5: Commit Changes

```bash
git add .
git commit -m "Add feature: clear description

- Detailed explanation of changes
- List key modifications
- Reference related issues: fixes #123"
```

**Commit Message Format**:
```
[Type]: Brief description (50 chars max)

Longer explanation of the change (72 chars max per line)

- Bullet point 1
- Bullet point 2

Fixes #123
```

### Step 6: Push to Remote

```bash
git push origin feature/my-feature
```

If pre-commit hooks fail:
1. Review the error message
2. Fix the issues
3. Stage changes: `git add .`
4. Try committing again

---

## Code Quality Standards

### Python Version
- **Target**: Python 3.13+
- **Minimum**: Python 3.13

### Type Hints
All functions must have type hints:

```python
# ❌ Bad
def process_data(data):
    return data

# ✅ Good
def process_data(data: pd.DataFrame) -> dict[str, float]:
    return {}
```

### Documentation
- **Docstrings**: Google-style for all public functions/classes
- **Comments**: Explain WHY, not WHAT (code explains WHAT)
- **README**: Update if adding new features

```python
def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 0.02
) -> float:
    """Calculate Sharpe ratio of returns.

    The Sharpe ratio measures risk-adjusted returns.
    Higher values indicate better risk-adjusted performance.

    Args:
        returns: Daily returns as decimals (e.g., 0.05 for 5%)
        risk_free_rate: Annual risk-free rate

    Returns:
        Annualized Sharpe ratio

    Raises:
        ValueError: If returns list is empty

    Example:
        >>> sharpe = calculate_sharpe_ratio([0.01, -0.02, 0.03])
        >>> sharpe > 0
        True
    """
```

### Imports
- Sort using Ruff (automatic with `ruff check --fix`)
- Order: stdlib → third-party → local imports
- No wildcard imports

```python
# ✅ Good
import json
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from src.baet.config import ConfigLoader
from src.baet.risk import RiskEngine
```

---

## Testing Requirements

### Test Types

#### Unit Tests (Fast, <1 min total)
- Test individual functions/methods
- Mock external dependencies
- Located in `tests/test_*.py`
- Run with: `uv run pytest tests/ -m unit`

Example:
```python
import pytest
from src.baet.risk import RiskEngine

def test_max_position_size():
    """Test position size calculation respects limits."""
    engine = RiskEngine(max_loss=1000)
    size = engine.calculate_position_size(account_value=10000)
    assert 0 < size <= 100  # Max 100 shares per position
```

#### Integration Tests (Moderate, 5-15 min)
- Test component interactions
- Use real or stubbed external services
- Located in `tests/test_*_integration.py`
- Mark with: `@pytest.mark.integration`
- Run with: `uv run pytest tests/ -k integration`

Example:
```python
@pytest.mark.integration
def test_strategy_execution_pipeline():
    """Test full strategy execution with data and risk engine."""
    strategy = TestStrategy()
    data_loader = DataLoader(testnet=True)
    risk_engine = RiskEngine()

    signals = strategy.generate_signals(data_loader.get_data())
    positions = risk_engine.validate_and_size(signals)

    assert len(positions) > 0
```

#### E2E Tests (Slow, 30+ min)
- Test complete workflows
- Can use real testnet
- Located in `tests/test_e2e_*.py`
- Run on schedule: `0 2 * * *` (daily)
- Run manually via GitHub Actions

### Code Coverage

```bash
# View coverage report
uv run pytest tests/ --cov=src/baet --cov-report=html
open htmlcov/index.html

# View in terminal
uv run pytest tests/ --cov=src/baet --cov-report=term-missing
```

**Coverage by Component**:
| Component | Target |
|---|---|
| Core (execution, risk) | 95%+ |
| Data pipeline | 85%+ |
| Strategies | 80%+ |
| Utils/helpers | 70%+ |
| Overall | 80%+ |

---

## Pull Request Process

### 1. Create Pull Request on GitHub

Go to repository → "Compare & pull request"

**PR Title Format**:
```
[Type] Brief description

# Type can be:
# - Feature: Add new functionality
# - Fix: Bug fix
# - Refactor: Code improvements
# - Docs: Documentation updates
# - Test: Test additions/improvements
```

**PR Description Template**:
```markdown
## Description
Brief description of changes

## Changes Made
- Change 1
- Change 2
- Change 3

## Testing
- [ ] Unit tests added/updated
- [ ] All tests pass locally
- [ ] Test coverage maintained/improved

## Checklist
- [ ] Code follows style guide (ruff, mypy)
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Ready for review

## Related Issues
Fixes #123
Relates to #456
```

### 2. Wait for Automated Checks

GitHub Actions runs automatically:
- ✅ **Code Quality & Linting** (2 min)
- ✅ **Unit Tests** on Linux & Windows (3 min)
- ✅ **Integration Tests** (10 min)
- ✅ **Build & Package** (1 min)

All must pass (green ✅) before review.

### 3. Code Review

At least 1 approval required (usually a maintainer).

**Review Checklist**:
- ✓ Code is clear and well-documented
- ✓ Tests are comprehensive
- ✓ No performance regressions
- ✓ Security concerns addressed

### 4. Merge

Maintainer merges PR to `dev` or `main` (depends on branch).

Once merged to `dev`:
- Automatic deployment to test environment
- E2E tests run (15 min)
- System monitoring begins

---

## Troubleshooting

### Pre-commit Hooks Fail

**Problem**: `ruff format --check` fails
```
Error: One or more files would be reformatted
```

**Solution**:
```bash
# Auto-fix formatting
uv run ruff format src/ tests/

# Stage and commit again
git add .
git commit -m "Fix formatting"
```

**Problem**: MyPy type errors
```
src/baet/strategy.py:42: error: Missing type annotation
```

**Solution**:
```python
# Add type hint
def get_signal(self, price: float) -> Optional[str]:
    if price > self.threshold:
        return "BUY"
    return None
```

**Problem**: `bandit` security warning
```
B101: Test for use of assert detected. Use raise instead.
```

**Solution**:
- For real code: Replace `assert` with proper error handling
- For tests: Add `# nosec` comment (acceptable in test files)

### Tests Fail Locally But Pass on GitHub

**Problem**: Tests pass in CI but fail locally

**Causes**:
1. Different Python version: `python --version` should show 3.13+
2. Missing test fixtures: Ensure all test dependencies installed
3. Stale cache: Run `uv sync --all-extras` to refresh

**Solution**:
```bash
# Clean and reinstall
uv cache clean
uv sync --all-extras

# Run tests again
uv run pytest tests/ -v --tb=short
```

### Can't Commit to Main Branch

**Error**: `You are on main branch. Create a feature branch instead.`

**This is intentional!** It prevents accidental commits to main.

**Solution**:
```bash
# Create feature branch
git checkout -b feature/my-feature

# Make your changes and commit
git commit -m "Your message"
```

---

## Resources

- **Python Style Guide**: [PEP 8](https://pep8.org/)
- **Type Hints**: [PEP 484](https://www.python.org/dev/peps/pep-0484/)
- **Testing**: [Pytest Docs](https://docs.pytest.org/)
- **Git Workflow**: [GitHub Flow](https://guides.github.com/introduction/flow/)
- **Ruff**: [Ruff Documentation](https://docs.astral.sh/ruff/)
- **MyPy**: [MyPy Documentation](https://www.mypy-lang.org/)

---

## Questions?

- **Setup Issues**: See [CI_CD_QUICK_START.md](docs/CI_CD_QUICK_START.md)
- **CI/CD Questions**: See [CI-CD_PLAN.md](CI-CD_PLAN.md)
- **Code Reviews**: Open discussion in PR
- **General Questions**: Create a GitHub discussion

---

**Thank you for contributing to BAET! 🚀**

Last Updated: May 13, 2026
Version: 1.0
