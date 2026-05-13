# Deployment Runbook

This document provides step-by-step procedures for deploying BAET through different stages.

## Table of Contents
1. [Development Deployment](#development-deployment)
2. [Test Deployment](#test-deployment)
3. [Paper Trading Deployment](#paper-trading-deployment)
4. [Production (Live) Deployment](#production-live-deployment)
5. [Rollback Procedures](#rollback-procedures)
6. [Incident Response](#incident-response)

---

## Development Deployment

**Environment**: Local machine  
**Branch**: `feature/*` or `dev`  
**Trigger**: Manual  
**Risk**: Low (local only)

### Steps

1. **Create feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes and test locally**
   ```bash
   # Install dependencies
   uv sync --all-extras
   
   # Run pre-commit checks
   pre-commit run --all-files
   
   # Run tests
   uv run pytest tests/ -v --cov=src/baet
   
   # Test the application
   uv run python -m baet --mode dev --config config/dev.yaml
   ```

3. **Commit and push**
   ```bash
   git add .
   git commit -m "Add feature: description"
   git push origin feature/my-feature
   ```

4. **Verify CI checks pass**
   - Go to GitHub repository
   - Look at Pull Request "Checks" tab
   - All checks must show ✅

5. **Get code review approval**
   - Request review from team members
   - Address any feedback
   - Wait for approval

---

## Test Deployment

**Environment**: GitHub Actions (automated)  
**Branch**: `dev`  
**Trigger**: Automatic (push to dev branch)  
**Risk**: Low (isolated tests, no real trading)

### Pre-deployment checklist
- [ ] All local tests pass
- [ ] Pre-commit hooks pass
- [ ] Code review approved
- [ ] Commit message is clear

### Deployment process

1. **Merge PR to dev**
   ```bash
   # On GitHub: Click "Merge pull request"
   # OR via CLI:
   git checkout dev
   git pull origin dev
   ```

2. **GitHub Actions auto-runs**
   - **test.yml** workflow triggers automatically
   - Runs all unit tests, integration tests
   - Checks code quality (linting, type checking)
   - Publishes coverage reports

3. **Monitor workflow**
   - Go to Actions tab
   - Watch "Test & Quality Checks" workflow
   - Should complete in 5-10 minutes
   - All jobs must show ✅

4. **Review results**
   ```bash
   # Locally verify
   uv run pytest tests/ -v
   uv run ruff check src/ tests/
   uv run mypy src/ --strict
   ```

5. **If tests fail**
   - Do NOT proceed to next stage
   - Fix issues on feature branch
   - Re-push to trigger CI again

---

## Paper Trading Deployment

**Environment**: Paper trading server (staging)  
**Branch**: `staging`  
**Trigger**: Manual (with approval)  
**Risk**: Medium (using testnet, not real capital)  
**Duration**: 5-7 days minimum

### Pre-deployment checklist
- [ ] 7+ days of stable dev testing completed
- [ ] E2E tests pass
- [ ] Code review approved
- [ ] All integration tests pass
- [ ] Binance testnet secrets configured
- [ ] Paper trading config finalized
- [ ] Risk limits reviewed and approved

### Deployment process

1. **Create staging branch from dev**
   ```bash
   git checkout -b staging --track origin/dev
   git push -u origin staging
   ```

2. **Create Pull Request: dev → staging**
   - Add checklist to PR description
   - Tag appropriate team members
   - Wait for approval (requires 2+ approvals)

3. **Deploy to paper trading**
   ```bash
   # On server/CI:
   git checkout staging
   git pull origin staging
   
   # Run paper trading
   BAET_MODE=paper uv run python -m baet --config config/paper.yaml
   ```

4. **Verify deployment**
   ```bash
   # Check logs
   tail -f logs/paper/baet.log
   
   # Run validation script
   uv run python scripts/validate_paper_trading.py
   
   # Expected output:
   # ✅ Paper trading engine started
   # ✅ Connected to Binance testnet
   # ✅ Initial capital: $1000
   # ✅ Strategies loaded: 3
   ```

5. **Monitor paper trading**
   - **Daily**: Check logs for errors
   - **Daily**: Review P&L
   - **Daily**: Verify orders executed as expected
   - **Weekly**: Run comparison report
   
   ```bash
   # Generate paper trading report
   uv run python scripts/analyze_paper_logs.py --period week
   ```

6. **Paper trading acceptance criteria**
   - ✅ 7+ days without critical errors
   - ✅ P&L positive or minimal loss (<5%)
   - ✅ All orders execute properly
   - ✅ Risk limits respected
   - ✅ No unexpected strategy behavior

7. **If paper trading fails**
   - Immediately stop paper trading
   - Investigate root cause
   - Fix issues on dev branch
   - Restart from Test Deployment phase

---

## Production (Live) Deployment

**Environment**: Production server  
**Branch**: `main` (tagged release)  
**Trigger**: Manual (with multiple approvals)  
**Risk**: High (using real capital)  
**Duration**: Phased rollout (start with paper mode)

### Pre-deployment checklist

**Critical Checks**:
- [ ] 30+ days of stable paper trading (strongly recommended)
- [ ] Paper trading P&L positive over 7-day periods
- [ ] Zero critical bugs in last 30 days
- [ ] All security scans pass
- [ ] Risk limits have been stress-tested
- [ ] Manual override tested and working
- [ ] Team communication established
- [ ] Monitoring dashboards ready
- [ ] Incident response plan documented and rehearsed
- [ ] Capital allocation approved by stakeholders

**Authorization**:
- [ ] Tech lead approval
- [ ] Operations lead approval
- [ ] Risk management approval
- [ ] Business approval (if applicable)

### Deployment process

#### Phase 1: Release Tag (1 day)

1. **Create release from main**
   ```bash
   # Update version
   # - pyproject.toml
   # - src/baet/__init__.py
   # - Update CHANGELOG.md
   
   git add .
   git commit -m "Bump version to v0.2.0"
   git push origin main
   
   # Create and push tag
   git tag -a v0.2.0 -m "Release v0.2.0: Add X feature"
   git push origin v0.2.0
   ```

2. **Wait for GitHub Actions**
   - Build workflow triggers automatically
   - Creates GitHub Release with artifacts
   - Publishes to PyPI (if configured)

3. **Get team approval**
   - Post release in team channel
   - Wait for stakeholder confirmation
   - Document approval in issue

#### Phase 2: Paper Mode Live (1-2 days)

Before trading with real capital, run in paper mode on production:

1. **Deploy to production in paper mode**
   ```bash
   git checkout main
   git pull origin main
   git checkout v0.2.0  # Use release tag
   
   # Start in paper mode
   BAET_MODE=paper BAET_INITIAL_CAPITAL=10000 \
     uv run python -m baet --config config/live.yaml
   ```

2. **Run for 24-48 hours**
   - Verify all connections work
   - Verify orders execute properly
   - Monitor for any anomalies
   - Check logs for errors
   
   ```bash
   # Monitor logs
   tail -f logs/paper/baet.log
   
   # Check strategy signals
   uv run python scripts/monitor_paper_trading.py
   ```

3. **Validate results**
   ```bash
   # Generate validation report
   uv run python scripts/validate_live_execution.py --mode paper
   
   # Expected:
   # ✅ Orders placed and filled correctly
   # ✅ Risk limits enforced
   # ✅ All strategies executing
   # ✅ No connection issues
   ```

#### Phase 3: Live Trading with Limited Capital (1-2 weeks)

Start with minimal capital to test live execution:

1. **Get final approval**
   - All paper mode tests passed ✅
   - Team lead confirms ready
   - Risk management approves capital amount
   - Create issue: "Approval: Deploy to live with $500 capital"

2. **Deploy with live capital**
   ```bash
   BAET_MODE=live BAET_INITIAL_CAPITAL=500 \
     uv run python -m baet --config config/live.yaml
   ```

3. **Monitor intensively** (First 7 days)
   - Check logs every 1-2 hours
   - Review every trade manually
   - Verify P&L calculations
   - Test manual override daily
   
   ```bash
   # Monitor script
   watch -n 300 'uv run python scripts/monitor_paper_trading.py'
   ```

4. **Daily standup**
   - Report P&L to team
   - Note any issues or anomalies
   - Verify risk limits
   - Plan for next steps

5. **Acceptance criteria**
   - ✅ 7 days without critical errors
   - ✅ All trades execute properly
   - ✅ P&L stable (small positive or break-even acceptable)
   - ✅ Risk limits never exceeded
   - ✅ All monitoring working

#### Phase 4: Scale Capital (Ongoing)

After 2+ weeks of successful live trading:

1. **Review performance**
   ```bash
   # Generate 2-week performance report
   uv run python scripts/analyze_paper_logs.py --start "-14d" --end now
   ```

2. **Team decision**
   - Review P&L, Sharpe ratio, drawdown
   - Discuss strategy effectiveness
   - Decide: continue, optimize, or rollback

3. **Scale capital gradually**
   ```bash
   # Increase capital in 50% increments
   BAET_MODE=live BAET_INITIAL_CAPITAL=750 uv run python -m baet
   # Monitor for 1 week
   
   BAET_MODE=live BAET_INITIAL_CAPITAL=1000 uv run python -m baet
   # Monitor for 1 week
   
   # Continue until target capital reached
   ```

### Rollback from Live

If critical issues occur:

1. **Stop trading immediately**
   ```bash
   # Send stop command to running process
   # (implementation depends on deployment method)
   kill -TERM <process_id>
   # or in code:
   # BAET stops and closes all positions
   ```

2. **Return to paper mode**
   ```bash
   BAET_MODE=paper uv run python -m baet --config config/live.yaml
   ```

3. **Investigate root cause**
   ```bash
   # Check logs
   grep ERROR logs/live/baet.log | head -20
   
   # Check recent trades
   uv run python scripts/validate_live_execution.py --mode live
   ```

4. **Fix and re-test**
   - Create issue with root cause analysis
   - Create fix branch
   - Test in dev environment
   - Go back to Test Deployment phase

---

## Rollback Procedures

### Rollback from Staging (Paper Trading)

If issues detected during paper trading:

```bash
# 1. Stop paper trading immediately
git checkout staging && git pull origin staging
# Stop running process

# 2. Revert to previous staging version
git revert HEAD
git push origin staging

# 3. Or reset to previous known good version
git reset --hard origin/dev
git push --force origin staging

# 4. Restart paper trading with previous version
BAET_MODE=paper uv run python -m baet

# 5. Investigate issue
uv run python scripts/check_orders.py
```

### Rollback from Production (Live Trading)

If issues detected during live trading:

```bash
# 1. STOP TRADING IMMEDIATELY
# Kill the process and close all positions (automatic)

# 2. Check for open positions
uv run python scripts/check_orders.py --mode live

# 3. If critical issue, close all positions manually
# (Emergency procedure - see below)

# 4. Downgrade to previous release
git checkout main && git pull origin main
git checkout v0.1.0  # Previous stable version
# Or: use docker to restart with previous tag

# 5. Restart in paper mode
BAET_MODE=paper uv run python -m baet --config config/live.yaml

# 6. Do NOT resume live trading until root cause fixed
```

### Emergency: Force Close All Positions

Use this ONLY if system is completely broken:

```bash
# Interactive script to close all positions
uv run python scripts/close_all_positions.py --confirm

# This will:
# 1. List all open positions
# 2. Ask for confirmation
# 3. Send market orders to close everything
# 4. Wait for execution
# 5. Report final state
```

---

## Incident Response

### Critical Issue During Live Trading

**Severity 1: System Down (Stop Immediately)**
- No logs, process crashed
- Cannot connect to Binance
- Risk management system failed

**Response**:
```bash
# 1. Kill all processes immediately
pkill -f "python -m baet"

# 2. Emergency: Close positions
uv run python scripts/close_all_positions.py --emergency

# 3. Gather information
tail -1000 logs/live/baet.log > incident_dump.log
git log -1 > incident_version.txt

# 4. Alert team immediately
# (Send alert via monitoring system)

# 5. Do not restart until root cause identified
```

**Severity 2: Strategy Malfunction (Review & Fix)**
- Strategy losing money unexpectedly
- Wrong order sizes
- Strategy not stopping at risk limits

**Response**:
```bash
# 1. Reduce capital to minimum
BAET_MODE=live BAET_INITIAL_CAPITAL=100 uv run python -m baet

# 2. Disable problematic strategy
# Edit config/live.yaml, disable in strategy section
# Restart application

# 3. Investigate
uv run python scripts/analyze_paper_logs.py --strategy strategy_name

# 4. Fix and test
# Create hotfix branch, test in staging, redeploy
```

**Severity 3: Performance Degradation (Monitor & Document)**
- Slower execution
- More slippage than expected
- Unusual market conditions

**Response**:
```bash
# 1. Document observations
uv run python scripts/check_orders.py --analyze

# 2. Compare with baseline
uv run python scripts/run_strategy_comparison.py

# 3. Adjust parameters if needed (only if confident)

# 4. Continue monitoring
```

### Incident Post-Mortem

After any incident:

1. **Create incident issue**
   ```
   Title: [INCIDENT] Brief description
   Labels: incident, production
   
   Content:
   - What happened
   - When it happened
   - Impact (capital lost, downtime, etc.)
   - Root cause (if known)
   - How it was resolved
   - Prevention for future
   ```

2. **Root cause analysis**
   ```bash
   # Review logs
   grep -i error logs/live/baet.log
   
   # Check if tests would have caught it
   uv run pytest tests/ -v -k "related_test"
   
   # Document findings
   ```

3. **Prevention measures**
   - Add test to prevent regression
   - Update risk limits if needed
   - Improve monitoring
   - Update runbooks

4. **Team review**
   - Discuss in team meeting
   - Document learnings
   - Update procedures

---

## Monitoring & Health Checks

### Health Check Script
```bash
# Run daily
uv run python -c "
from src.baet.core import health_check
result = health_check()
print('System Status:', 'OK' if result else 'FAILED')
"
```

### Key Metrics to Monitor

| Metric | Healthy | Warning | Critical |
|---|---|---|---|
| Process uptime | >23 hrs/day | >20 hrs/day | <20 hrs/day |
| API response time | <1s | 1-5s | >5s |
| Strategy signals | Updated | Delayed 1-2min | No updates >10min |
| Open positions | Stable | Increasing | Unexpected |
| P&L drawdown | >-2% | -2% to -5% | <-5% |

### Weekly Checklist

```markdown
- [ ] All processes running
- [ ] No critical errors in logs
- [ ] P&L within expected range
- [ ] Binance API working normally
- [ ] Backups completed
- [ ] Performance metrics reviewed
- [ ] Risk limits verified
- [ ] Team notified of any issues
```

---

## Support

- **Emergency Issues**: Contact on-call ops engineer immediately
- **Questions**: See [CI-CD_PLAN.md](./CI-CD_PLAN.md)
- **Historical Issues**: Search GitHub issues with label `incident`
- **Procedure Updates**: Create PR to update this runbook

---

**Last Updated**: May 13, 2026  
**Version**: 1.0  
**Owner**: BAET Operations Team
