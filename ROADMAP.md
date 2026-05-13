# BAET Roadmap

## TL;DR
Build BAET in 5 stages: project foundation, research engine, intelligence layer, paper trading readiness, and limited live deployment. Do not move to the next stage until the current one has clear exit criteria and working evidence.

## Current Status (May 2026)
- **Stage 0** ✅ Complete — Project setup and operating baseline
- **Stage 1** ✅ Complete — Research foundation
- **Stage 2** ✅ Complete — Strategy base layer (7 strategies)
- **Stage 3** ✅ Complete — Intelligence and portfolio decision layer
- **Stage 4** ✅ Complete — Risk engine and paper trading
- **Stage 5.1** ✅ Complete — Live readiness and execution validation
- **Stage 5.2** ⏳ Pending — Tiny-capital live pilot

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

### Stage 3 Breakdown

#### Stage 3.1 - Regime Definitions and Labeling
Objective:
- define the exact regime taxonomy used across research and decision-making

Deliverables:
- regime label set
- labeling rules
- stored regime column aligned to market bars

Work Items:
- define trend, range, high-volatility, and low-volatility rules
- define threshold and lookback settings in config
- add reproducible regime labeling to research datasets
- add regime summary reporting

Milestones:
- `M3.1a` regime labels are formally defined
- `M3.1b` regime labels are generated reproducibly on stored datasets

Exit Criteria:
- regime labels are deterministic for the same input data
- regime outputs are aligned to candles without lookahead

#### Stage 3.2 - Regime Engine
Objective:
- convert regime labels into a reusable detector component

Deliverables:
- regime detector module
- detector configuration surface
- detector tests and edge-case coverage

Work Items:
- implement detector logic as a reusable service
- store detector outputs by symbol and timeframe
- test transitions, warmup periods, and no-lookahead behavior

Milestones:
- `M3.1c` regime detector runs end to end for target symbols

Exit Criteria:
- detector can be called from backtests and later live flows
- regime transitions are logged or reportable

#### Stage 3.3 - Signal Standardization
Objective:
- make all strategies emit one shared signal contract before ensemble logic is added

Deliverables:
- common signal schema
- adapters for baseline strategies
- signal validation helpers

Work Items:
- define signal fields for timestamp, symbol, timeframe, direction, confidence, and size hint
- adapt Stage 2 strategy outputs to the shared schema
- add validation tests for consistent signal formatting

Milestones:
- `M3.2a` all Stage 2 strategies emit one standardized signal shape

Exit Criteria:
- strategies can be compared and combined without custom adapters per backtest

#### Stage 3.4 - Static Ensemble Baseline
Objective:
- create simple, transparent ensemble methods before adaptive logic

Deliverables:
- majority-vote ensemble
- weighted-vote ensemble
- contribution logging per strategy

Work Items:
- implement majority vote
- implement static weighted vote
- record which strategies contributed to each combined decision
- compare ensemble outputs to best single-strategy baselines

Milestones:
- `M3.2b` static ensemble produces one consistent portfolio decision stream

Exit Criteria:
- one baseline ensemble works end to end in backtests
- ensemble decisions are inspectable and reproducible

#### Stage 3.5 - Adaptive Weighting
Objective:
- add simple performance-aware weighting without making the system opaque

Deliverables:
- rolling performance tracker
- weight update logic
- adaptive ensemble backtest comparison

Work Items:
- define rolling metrics for weight updates
- implement deterministic reweighting rules
- compare static and adaptive ensemble behavior

Milestones:
- `M3.3a` adaptive weights update deterministically from rolling performance inputs

Exit Criteria:
- adaptive weights can be explained from stored metrics
- adaptive logic improves or clearly justifies itself over static weighting

#### Stage 3.6 - ML Strategy Integration
Objective:
- bring 1 to 3 ML models into the same signal and backtest framework

Deliverables:
- ML strategy wrappers
- training and inference hooks
- ensemble-ready ML signals

Work Items:
- add first directional classifier
- add first return-probability model
- make ML outputs emit the same signal schema as rule-based strategies
- compare ML-only and mixed-ensemble performance

Milestones:
- `M3.3b` at least one ML strategy is integrated into ensemble backtests

Exit Criteria:
- ML signals can be backtested, logged, and ensembled without special-case paths

#### Stage 3.7 - Portfolio-Level Evaluation
Objective:
- prove whether Stage 3 intelligence actually improves results

Deliverables:
- portfolio comparison report pack
- regime-by-regime performance view
- single-strategy vs ensemble comparison

Work Items:
- compare best single strategy, static ensemble, adaptive ensemble, and mixed ML ensemble
- report return, drawdown, trade count, and regime performance
- identify whether ensemble logic earns its added complexity

Milestones:
- `M3.4` portfolio comparison reports validate the Stage 3 approach

Exit Criteria:
- Stage 3 has measurable evidence for or against the ensemble stack

### Recommended Stage 3 Order
1. Stage 3.1 regime definitions and labeling
2. Stage 3.2 regime engine
3. Stage 3.3 signal standardization
4. Stage 3.4 static ensemble baseline
5. Stage 3.5 adaptive weighting
6. Stage 3.6 ML strategy integration
7. Stage 3.7 portfolio-level evaluation

## 7. Stage 4 - Risk Engine and Paper Trading

### Objective
Make the system operationally safe and validate behavior under live market flow without real money.

### Deliverables
- centralized risk engine
- live data update loop
- paper trading engine
- decision and execution logs
- Streamlit paper trading dashboard and summary reports

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

### Stage 4 Breakdown

#### Stage 4.1 - Risk Policy Definition
Objective:
- lock the hard and soft rules before wiring them into runtime logic

Deliverables:
- explicit hard limits
- explicit soft controls
- kill-switch conditions

Work Items:
- define per-trade, per-symbol, and portfolio-wide limits
- define degradation rules for unstable strategies or regimes
- define what constitutes a circuit-breaker event

Milestones:
- `M4.1a` risk policy is documented and decision-complete

Exit Criteria:
- implementation no longer needs to guess risk behavior

#### Stage 4.2 - Central Risk Engine
Objective:
- implement one pre-trade risk layer that all future execution paths must use

Deliverables:
- centralized risk validator
- allow/deny/resize decision flow
- audit-friendly decision logging

Work Items:
- implement exposure checks
- implement drawdown and stop-trading checks
- implement correlation and crowding checks where practical
- make the risk engine callable from backtests and paper trading

Milestones:
- `M4.1b` no trade path can bypass centralized risk checks

Exit Criteria:
- risk decisions are deterministic and logged

#### Stage 4.3 - Market Loop and Paper Execution Core
Objective:
- build the runtime loop that consumes live market data and simulates execution

Deliverables:
- live market update loop
- paper portfolio state manager
- simulated order and fill handling

Work Items:
- wire real-time market data updates into strategy evaluation cadence
- simulate balances, positions, fills, and fees
- preserve runtime state for restart-safe monitoring

Milestones:
- `M4.2a` paper trading loop runs continuously without crashing

Exit Criteria:
- market loop and paper execution share one coherent state model

#### Stage 4.4 - Monitoring, Logs, and Daily Summaries
Objective:
- make paper trading behavior inspectable rather than opaque

Deliverables:
- decision logs
- execution logs
- daily and rolling summary outputs
- Streamlit dashboard for runtime monitoring

Work Items:
- log why trades were allowed, resized, or blocked
- summarize PnL, drawdown, exposure, and blocked trades
- add paper-vs-backtest comparison outputs
- build Streamlit views for portfolio state, strategy health, and blocked-trade visibility

Milestones:
- `M4.3a` paper trading logs explain trade decisions end to end
- `M4.3b` Streamlit dashboard shows current paper trading state and daily summaries

Exit Criteria:
- operator can diagnose both model and risk behavior from stored outputs
- dashboard is useful enough to replace ad hoc manual inspection for normal monitoring

#### Stage 4.5 - Stability and Behavioral Validation
Objective:
- validate paper trading over time before any live execution exists

Deliverables:
- observation-run checklist
- discrepancy analysis between paper and backtest behavior
- paper trading readiness report

Work Items:
- run the loop over a meaningful observation window
- compare fill assumptions and behavior to backtests
- document failures, restarts, and observed drift

Milestones:
- `M4.4` paper trading is stable and explainable over the target observation window

Exit Criteria:
- Stage 4 can prove operational stability, not just local correctness

### Recommended Stage 4 Order
1. Stage 4.1 risk policy definition
2. Stage 4.2 central risk engine
3. Stage 4.3 market loop and paper execution core
4. Stage 4.4 monitoring, logs, and daily summaries
5. Stage 4.5 stability and behavioral validation

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

### Stage 5 Breakdown

#### Stage 5.1 - Live Readiness Controls
Objective:
- ensure live trading can only be enabled intentionally and safely

Deliverables:
- live mode checklist
- live config isolation
- manual pause and kill-switch controls

Work Items:
- separate paper and live credentials cleanly
- require explicit live enable flags and confirmations
- define operator runbook for starting and stopping live mode

Milestones:
- `M5.1a` live readiness controls are implemented and documented

Exit Criteria:
- live mode cannot be entered accidentally

#### Stage 5.2 - Authenticated Binance Execution
Objective:
- add the smallest safe live execution path for spot trading

Deliverables:
- authenticated Binance execution adapter
- order submission and reconciliation hooks
- order error handling flow

Work Items:
- implement order placement for approved spot instruments
- fetch order status and reconcile fills
- preserve a full audit trail of submitted and confirmed actions

Milestones:
- `M5.1b` live execution path works in controlled validation conditions

Exit Criteria:
- live order flow is testable, logged, and reversible by operator action

#### Stage 5.3 - Small-Capital Pilot
Objective:
- validate the system under real exchange behavior using minimal risk

Deliverables:
- tiny-capital live pilot
- pilot metrics and incident log
- live-vs-paper comparison report

Work Items:
- define capital cap for first live run
- run limited live trading with strict thresholds
- compare fills, slippage, and risk behavior against paper expectations

Milestones:
- `M5.2` first tiny-capital live pilot completes with full audit trail

Exit Criteria:
- live behavior is close enough to paper behavior to justify continuation

#### Stage 5.4 - Operational Hardening
Objective:
- stabilize the live system before broadening scope

Deliverables:
- post-trade reconciliation flow
- incident response checklist
- live health review cadence

Work Items:
- add restart, retry, and failure handling where live conditions expose weakness
- confirm kill-switch behavior under realistic operator scenarios
- document remaining operational gaps

Milestones:
- `M5.3` no hard risk rule breaches occur during initial live observation

Exit Criteria:
- the live system is controlled, inspectable, and boring enough to expand slowly

### Recommended Stage 5 Order
1. Stage 5.1 live readiness controls
2. Stage 5.2 authenticated Binance execution
3. Stage 5.3 small-capital pilot
4. Stage 5.4 operational hardening

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

### Deferred Stage Breakdown

#### Stage 6.1 - Futures and Leverage Controls
- add futures support only after spot live execution is stable
- implement leverage, liquidation, and margin-specific safeguards first

#### Stage 6.2 - Broader Portfolio Expansion
- expand symbol universe gradually
- add more portfolio-aware exposure and correlation controls

#### Stage 6.3 - Advanced ML and Retraining
- add more sophisticated ML models
- add retraining and promotion/demotion workflows

#### Stage 6.4 - RL and LLM-Assisted Research
- keep RL agents and Ollama-assisted strategy ideation research-only at first
- require strict offline validation before any production path

#### Stage 6.5 - Cloud and Operational Scaling
- add cloud deployment, scheduling, remote storage, or multi-machine workflows only after the local system is mature

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
- lightweight Streamlit dashboard

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
