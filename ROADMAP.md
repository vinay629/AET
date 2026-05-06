# BAET Roadmap

## TL;DR
Build BAET in 5 stages: project foundation, research engine, intelligence layer, paper trading readiness, and limited live deployment. Do not move to the next stage until the current one has clear exit criteria and working evidence.

## 1. Roadmap Goal
This roadmap turns the PRD into an execution sequence that reduces risk, avoids premature complexity, and keeps the first production scope realistic.

Primary outcomes:
- create a reliable trading research platform
- validate strategies before live capital
- centralize risk controls
- reach stable paper trading before live trading
- launch limited live trading only with strict constraints

## 2. Guiding Roadmap Rules
- finish infrastructure before adding intelligence
- validate simple strategies before advanced models
- risk controls are mandatory, not optional
- paper trading is a gate, not a checkbox
- each phase must produce reusable assets, not throwaway experiments
- avoid futures, RL, and LLM-generated production logic until the base system is stable

## 3. Stage 0 - Project Setup and Operating Baseline

### Objective
Create the minimum project structure, documentation baseline, and development workflow needed to build safely.

### Deliverables
- PRD finalized
- roadmap finalized
- folder structure defined
- environment setup documented
- dependency strategy decided
- local configuration pattern defined
- Git workflow and branching approach defined

### Work Items
- define project modules and boundaries
- define config handling for dev, paper, and live modes
- define secrets handling approach for Binance credentials
- create task tracking files
- define coding conventions and testing expectations

### Exit Criteria
- a new contributor can understand the project layout
- local development setup is documented
- configuration decisions are written down
- the project can move into implementation without ambiguity

### Risks
- unclear structure causing rework later
- mixing research and live concerns too early

## 4. Stage 1 - Research Foundation

### Objective
Build the data and backtesting foundation required for trustworthy offline research.

### Deliverables
- historical Binance data ingestion
- local storage for raw and processed data
- dataset validation checks
- feature engineering pipeline
- backtesting engine with fees and slippage
- baseline reporting outputs

### Work Items
- implement historical candle ingestion for BTCUSDT and ETHUSDT
- choose and implement local storage format
- define schema for market data, features, and backtest results
- implement feature generation for trend, momentum, and volatility
- build backtest runner supporting 1h and 4h
- add trading cost assumptions
- generate first comparable performance reports

### Milestones
- M1.1 historical data loads successfully for target symbols
- M1.2 feature pipeline runs reproducibly on stored data
- M1.3 backtester returns stable outputs with fees and slippage
- M1.4 reports can compare multiple strategies consistently

### Exit Criteria
- historical data is available locally for target symbols
- backtests can be rerun with reproducible results
- raw, feature, and result layers are separated clearly
- at least one end-to-end research run works without manual patching

### Risks
- bad data quality
- silent feature leakage
- unrealistic backtest assumptions

### Dependencies
- Stage 0 complete

## 5. Stage 2 - Strategy Base Layer

### Objective
Implement a stable strategy framework and validate a baseline strategy set before adding meta logic.

### Deliverables
- strategy interface
- strategy registry or loader
- baseline classical strategy pack
- per-strategy evaluation reports
- strategy metadata model

### Work Items
- define standard strategy input and output contract
- implement signal format with direction, confidence, and sizing hint
- build RSI mean reversion strategy
- build Bollinger mean reversion strategy
- build EMA crossover strategy
- build breakout momentum strategy
- build ADX trend filter strategy
- add at least one volatility-based strategy
- create comparison reports for individual strategies

### Milestones
- M2.1 strategy interface supports pluggable modules
- M2.2 at least 5 strategies are backtestable under one framework
- M2.3 strategy comparison report ranks results by key metrics

### Exit Criteria
- at least 5 baseline strategies run through the same pipeline
- each strategy can be enabled or disabled cleanly
- strategy outputs are standardized
- weak strategies can be rejected using measurable criteria

### Risks
- too many strategy-specific hacks
- hardcoded assumptions that break extensibility
- strategy outputs not being comparable

### Dependencies
- Stage 1 complete

## 6. Stage 3 - Intelligence and Portfolio Decision Layer

### Objective
Add market regime awareness, ensemble decision-making, and first-generation ML models.

### Deliverables
- regime detector
- ensemble decision layer
- basic ML strategy set
- dynamic or semi-dynamic weighting logic
- portfolio-level evaluation

### Work Items
- define regime labels such as trending, ranging, high-volatility, and low-volatility
- implement initial regime detection logic
- build weighted voting ensemble
- evaluate static vs adaptive strategy weights
- implement 1 to 3 ML-based strategies
- compare baseline strategies versus ensemble outputs
- record decision traces for why a combined trade was proposed

### Milestones
- M3.1 regime labels are generated consistently in backtests
- M3.2 ensemble combines multiple strategy outputs into one decision
- M3.3 at least one ML strategy is integrated into the common framework
- M3.4 ensemble performance is comparable or better than top single-strategy baseline

### Exit Criteria
- one regime detector is working end to end
- one ensemble method works with standardized strategy outputs
- at least one ML model is producing usable signals
- portfolio-level reporting exists

### Risks
- overfitting from adaptive weighting
- regime detector that adds complexity without value
- ML signals that look strong in-sample only

### Dependencies
- Stage 2 complete

## 7. Stage 4 - Risk Engine and Paper Trading

### Objective
Make the system operationally safe and validate behavior under live market flow without real money.

### Deliverables
- centralized risk engine
- live data update loop
- paper trading engine
- decision and execution logs
- paper trading dashboard or summary reports

### Work Items
- define hard risk limits
- define soft controls and degradation rules
- implement exposure caps, drawdown caps, and trade blocking rules
- implement live market polling or streaming
- connect strategy and ensemble logic to live evaluation loop
- simulate orders, balances, positions, and fills
- create daily and rolling paper trading summaries
- validate system stability over several days

### Milestones
- M4.1 no trade can bypass centralized risk checks
- M4.2 paper trading loop runs continuously without logic failure
- M4.3 paper trading logs explain why trades were allowed or blocked
- M4.4 paper trading performance can be compared with backtest expectations

### Exit Criteria
- paper trading runs on live data for a meaningful observation period
- risk limits block invalid actions reliably
- logs are sufficient for post-mortem review
- differences between backtest and paper results are understood

### Risks
- live loop instability
- hidden state bugs
- order simulation too optimistic
- risk controls implemented too late

### Dependencies
- Stage 3 complete

## 8. Stage 5 - Limited Live Deployment

### Objective
Enable tightly constrained live trading only after research and paper trading prove stable.

### Deliverables
- live execution mode for Binance spot
- secure credential handling
- operator controls and kill-switch
- live trade audit trail
- live readiness checklist

### Work Items
- integrate Binance authenticated execution
- isolate paper and live configs
- require explicit live enable flag
- implement manual pause and kill-switch
- implement post-trade reconciliation
- deploy tiny-capital live run
- review live behavior against paper expectations

### Milestones
- M5.1 live execution path is tested in safe conditions
- M5.2 manual safety controls are verified
- M5.3 first tiny-capital live trades complete with full audit trail
- M5.4 no breach of hard risk rules during initial live observation window

### Exit Criteria
- live trading is opt-in and protected
- first live run uses very small capital
- live logs, fills, and reconciliation are working
- operator can pause or stop trading immediately

### Risks
- authentication mistakes
- configuration mix-up between paper and live
- slippage or fill behavior worse than expected
- psychological pressure causing scope creep

### Dependencies
- Stage 4 complete

## 9. Deferred Stage - Advanced Expansion

### Objective
Expand only after the v0.1 system is stable and understandable.

### Candidate Additions
- Binance futures
- leverage controls
- RL agents
- Ollama-assisted strategy ideation
- adaptive retraining workflows
- larger symbol universe
- cloud deployment
- advanced portfolio optimization

### Entry Rule
Do not start this stage until:
- paper trading has been stable
- live trading has respected risk limits
- the baseline system is operationally boring

## 10. v0.1 Release Path

### Definition
The first meaningful release is not “feature complete.” It is “safe enough to research and paper trade with confidence.”

### Must-Have for v0.1
- historical data ingestion
- feature engineering pipeline
- backtester with fees and slippage
- 5 baseline strategies
- 1 ensemble method
- 1 centralized risk layer
- paper trading mode
- reporting and logs

### Nice-to-Have for v0.1
- 1 to 3 ML strategies
- basic regime detector
- lightweight dashboard

### Not Required for v0.1
- futures
- RL
- autonomous strategy generation
- cloud orchestration

## 11. Recommended Execution Order
Build in this order:
1. project structure and config model
2. historical data ingestion
3. local storage and schemas
4. feature pipeline
5. backtesting engine
6. baseline strategies
7. reporting and comparison
8. regime detector
9. ensemble logic
10. risk engine
11. paper trading loop
12. live execution

This order avoids the common mistake of implementing live trading before having trustworthy research infrastructure.

## 12. Progress Tracking Model

### Phase-Level Tracking
Track each stage by:
- not started
- in progress
- at risk
- complete

### Milestone Tracking
Each milestone should be marked:
- pending
- active
- blocked
- validated

### Validation Rule
A stage is not complete because code exists. A stage is complete when:
- the intended workflow runs
- outputs are reviewable
- known risks are documented
- next-stage dependencies are satisfied

## 13. Roadmap Gates

### Gate A - Research Ready
Required before expanding strategy count:
- clean historical ingestion
- reproducible backtests
- baseline reports

### Gate B - Strategy Ready
Required before ML or adaptive weighting:
- stable strategy interface
- at least 5 comparable baseline strategies

### Gate C - Intelligence Ready
Required before paper trading:
- ensemble produces standardized trade decisions
- regime logic and reporting exist

### Gate D - Operational Ready
Required before live trading:
- paper trading stable
- risk layer proven
- kill-switch verified

## 14. Likely Blockers
- poor data schema decisions
- weak validation discipline
- backtests not matching live behavior
- too many symbols too early
- adding advanced AI features before the base system is trustworthy

## 15. Recommended Next Files
- `FOLDER_STRUCTURE.md`
- `MILESTONES.md`
- `TASKS.md`
- `RISK_POLICY.md`
- `SYSTEM_ARCHITECTURE.md`
