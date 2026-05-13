# CI/CD Implementation Quick Start Guide

**Last Updated: May 2026**

This guide helps you set up the CI/CD pipeline for BAET quickly.

## Prerequisites

- Python 3.13+
- `uv` package manager (already in project)
- GitHub repository access
- Git configured locally

---

## Phase 1: Local Setup (30 minutes)

### 1.1 Install Pre-commit Hooks

Pre-commit hooks run quality checks **before** code is committed, catching issues early.

```bash
# Install pre-commit tool
pip install pre-commit

# Set up hooks in this repository
pre-commit install

# (Optional) Test hooks on all files
pre-commit run --all-files
```

**What it does**:
- Checks code formatting with Ruff
- Runs MyPy type checking
- Scans for security issues with Bandit
- Validates YAML/JSON syntax
- Prevents accidental commits to `main`

### 1.2 Configure Local Test Environment

```bash
# Install all development dependencies
uv sync --all-extras

# Run local tests to ensure setup works
uv run pytest tests/ -v --cov=src/baet

# Check formatting locally
uv run ruff format src/ tests/
uv run ruff check src/ tests/

# Run type checking
uv run mypy src/ --strict
```

### 1.3 Git Workflow Setup

```bash
# Create a feature branch (always do this, never commit to main)
git checkout -b feature/your-feature-name

# Make changes, then commit
git add .
git commit -m "Add your feature description"
# Pre-commit hooks will run automatically

# If pre-commit hook fails
# Fix the issues and commit again
```

---

## Phase 2: GitHub Configuration (20 minutes)

### 2.1 Add GitHub Secrets

These secrets are needed for automated testing and deployment.

**Steps**:
1. Go to: **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add each:

| Secret Name | Value | Notes |
|---|---|---|
| `BINANCE_TESTNET_KEY` | Your testnet API key | Get from Binance testnet account |
| `BINANCE_TESTNET_SECRET` | Your testnet API secret | Get from Binance testnet account |
| `PYPI_TOKEN` | (Optional) PyPI token | Only needed if publishing to PyPI |

**Where to get Binance testnet credentials**:
1. Go to: https://testnet.binance.vision
2. Login with your account
3. Go to **Account** → **API Management**
4. Create new API key
5. Copy key and secret to GitHub secrets

### 2.2 Enable Branch Protection

Enforce quality checks before code is merged:

**Steps**:
1. Go to: **Settings** → **Branches**
2. Click **Add rule** under "Branch protection rules"
3. Configure for `main` branch:
   - **Pattern**: `main`
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Require code reviews
   - ✅ Require review from Code Owners (optional)

### 2.3 Configure Codecov (Optional but Recommended)

Codecov tracks code coverage over time:

1. Go to: https://codecov.io
2. Sign up with GitHub
3. Grant permissions
4. Your repository will auto-connect
5. Codecov badge will appear on pull requests

---

## Phase 3: Workflow Testing (15 minutes)

### 3.1 Test the CI Pipeline

Create a test branch to verify workflows run:

```bash
# Create a new branch
git checkout -b test/ci-setup

# Make a trivial change
echo "# CI Test" >> README.md

# Commit
git add .
git commit -m "Test: verify CI pipeline"

# Push to GitHub
git push origin test/ci-setup

# Go to GitHub and create a Pull Request
# Watch the automated checks run in the "Checks" tab
```

**Expected workflow runs**:
- ✅ Code Quality & Linting
- ✅ Unit Tests (ubuntu-latest)
- ✅ Unit Tests (windows-latest)
- ✅ Integration Tests
- ✅ Build Package

All should pass within 5-10 minutes.

### 3.2 Verify Branch Protection

Try to merge without an approval (should fail):
```bash
# Clean up test branch after verification
git checkout main
git branch -D test/ci-setup
git push origin --delete test/ci-setup
```

---

## Phase 4: Deployment Workflows (Optional, 30 minutes)

### 4.1 Paper Trading Validation

**Setup**:
1. Go to `.github/workflows/e2e-tests.yml`
2. This runs automated E2E tests daily at 2 AM UTC
3. Requires Binance testnet secrets (already configured)

**Manual run**:
```
In GitHub:
→ Actions tab
→ "E2E & Performance Tests" workflow
→ "Run workflow" button
→ Select branch and run
```

### 4.2 Release & Deployment

When you're ready to release:

```bash
# Create a release tag
git tag -a v0.1.1 -m "Release v0.1.1: add feature X"

# Push the tag
git push origin v0.1.1

# GitHub Actions will automatically:
# 1. Build the package
# 2. Create a GitHub Release
# 3. Publish to PyPI (if PYPI_TOKEN is set)
```

---

## Troubleshooting

### Issue: Pre-commit hooks fail locally

**Solution**:
```bash
# See what failed
pre-commit run --all-files --verbose

# Auto-fix formatting issues
uv run ruff format src/ tests/
uv run ruff check src/ tests/ --fix

# Fix type errors
uv run mypy src/ --strict
# Edit code to fix issues, then commit again
```

### Issue: GitHub Actions workflow fails

**Check**:
1. Go to **Actions** tab in GitHub
2. Click the failed workflow
3. Expand the failed job
4. Read the error message
5. Common issues:
   - Missing secrets → Add to repo settings
   - Type errors → Run `mypy` locally to debug
   - Test failures → Run `pytest` locally

### Issue: Pre-commit hook prevents commit to main

**This is intentional!** It protects the main branch.

**Solution**: Create a feature branch first
```bash
git checkout -b feature/your-change
# Make changes and commit
```

---

## Daily Development Workflow

Once setup is complete, your daily workflow is simple:

```bash
# 1. Create a feature branch
git checkout -b feature/my-feature

# 2. Make changes (pre-commit runs on commit)
git add .
git commit -m "Describe your changes"

# 3. Push to GitHub
git push origin feature/my-feature

# 4. Create a Pull Request on GitHub
# → Go to repository → "Compare & pull request"
# → Fill in description → Create PR

# 5. Wait for CI checks to pass (~5 min)
# → All green ✅ = ready to merge

# 6. Get code review approval
# → At least one approval required

# 7. Merge PR
# → GitHub will merge automatically when all checks pass and approved

# 8. Delete local branch
git checkout main
git pull origin main
git branch -D feature/my-feature
git push origin --delete feature/my-feature
```

---

## Performance Expectations

| Task | Expected Time |
|---|---|
| Pre-commit hooks (local) | <30 seconds |
| Unit tests (local) | <2 minutes |
| Full CI pipeline (GitHub) | 5-10 minutes |
| Integration tests | 15-20 minutes |
| E2E tests (daily) | 30+ minutes |

---

## Monitoring & Dashboards

### GitHub Actions Dashboard
- **URL**: Repository → **Actions** tab
- **View**: All workflow runs, status, and logs
- **Set up notifications**: Settings → Notifications → Check "Notify"

### Codecov Coverage
- **URL**: https://codecov.io/gh/[owner]/[repo]
- **View**: Coverage trends and per-file breakdown
- **Coverage badge**: Add to README:
  ```markdown
  [![codecov](https://codecov.io/gh/[owner]/[repo]/branch/main/graph/badge.svg)](https://codecov.io/gh/[owner]/[repo])
  ```

### Custom Metrics Script
Create `scripts/ci_report.py` to generate weekly summaries:
```bash
uv run python scripts/ci_report.py --week latest
```

---

## Next Steps

After Phase 1-3 setup:

1. ✅ Set up pre-commit hooks locally
2. ✅ Verify GitHub Actions workflows run
3. ✅ Enable branch protection
4. ✅ Document team workflow in CONTRIBUTING.md
5. ⭕ Set up paper trading validation workflow
6. ⭕ Add monitoring and alerting
7. ⭕ Create incident response runbooks

---

## Quick Reference: Commands

```bash
# Testing
uv run pytest tests/ -v
uv run pytest tests/test_*.py::TestClass::test_method -v

# Code quality
uv run ruff format src/
uv run ruff check src/ --fix
uv run mypy src/ --strict
uv run bandit -r src/

# Pre-commit
pre-commit run --all-files
pre-commit install

# Building
uv build
uv run python -m baet --mode dev

# Git workflow
git checkout -b feature/name
git push origin feature/name
# Create PR on GitHub...
git checkout main && git pull origin main
git branch -D feature/name && git push origin --delete feature/name
```

---

## Support & Questions

- **Troubleshooting**: See [CI-CD_PLAN.md](../CI-CD_PLAN.md)
- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Pre-commit Docs**: https://pre-commit.com
- **Pytest Docs**: https://docs.pytest.org
- **Ruff Docs**: https://docs.astral.sh/ruff/

---

**Last Updated**: May 13, 2026
**Version**: 1.0
