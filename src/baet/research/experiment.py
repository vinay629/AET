"""Experiment tracking for BAET.

Every research run is tracked with:
- Config hash (what was run)
- Feature version (what data was used)
- Strategy version (what logic was used)
- Training/test period split
- Full metrics (Sharpe, max DD, turnover, etc.)
- Trade log (every decision)
- Equity curve (for visualization)
- Checkpoints (for reproducibility)

This ensures:
- No accidental overfitting to test period
- Reliable experiment comparison
- Full audit trail
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for a research experiment."""
    name: str
    description: str = ""
    strategy_name: str = ""
    strategy_version: str = "1.0.0"
    feature_version: str = ""
    symbols: list[str] = field(default_factory=lambda: ["BTCUSDT"])
    timeframes: list[str] = field(default_factory=lambda: ["1h"])
    train_start: str = ""
    train_end: str = ""
    test_start: str = ""
    test_end: str = ""
    initial_cash: float = 10000.0
    fee_rate: float = 0.001
    slippage_rate: float = 0.0005
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def config_hash(self) -> str:
        content = json.dumps(self.__dict__, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ExperimentMetrics:
    """Metrics collected during an experiment."""
    # Returns
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    volatility_annualized: float = 0.0

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Drawdown
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_days: float = 0.0
    current_drawdown_pct: float = 0.0

    # Trading
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    hit_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0

    # Costs
    total_fees: float = 0.0
    fee_adjusted_return_pct: float = 0.0
    turnover: float = 0.0

    # Exposure
    avg_exposure_pct: float = 0.0
    max_exposure_pct: float = 0.0
    time_in_market_pct: float = 0.0

    # Tail
    skewness: float = 0.0
    kurtosis: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0

    # Regime breakdown
    regime_metrics: dict[str, dict[str, float]] = field(default_factory=dict)

    # Long/short decomposition
    long_return_pct: float = 0.0
    short_return_pct: float = 0.0
    long_hit_rate: float = 0.0
    short_hit_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class Experiment:
    """A single research experiment with full lineage."""
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    config: ExperimentConfig = field(default_factory=lambda: ExperimentConfig(name=""))
    metrics: ExperimentMetrics = field(default_factory=ExperimentMetrics)
    status: str = "pending"  # pending, running, completed, failed
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    error: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if not self.completed_at:
            return 0.0
        start = datetime.fromisoformat(self.created_at)
        end = datetime.fromisoformat(self.completed_at)
        return (end - start).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "config": self.config.__dict__,
            "metrics": self.metrics.to_dict(),
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "tags": self.tags,
        }


class ExperimentTracker:
    """
    Manages experiment lifecycle and persistence.

    Directory structure:
        experiments/
        ├── experiment_id/
        │   ├── config.yaml
        │   ├── metrics.json
        │   ├── trades.parquet
        │   ├── equity_curve.parquet
        │   └── checkpoints/
    """

    def __init__(self, experiments_dir: Path) -> None:
        self.experiments_dir = experiments_dir
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        self._current: Experiment | None = None

    def create(
        self,
        config: ExperimentConfig,
        tags: list[str] | None = None,
    ) -> Experiment:
        """Create a new experiment."""
        experiment = Experiment(
            config=config,
            status="pending",
            tags=tags or [],
        )
        self._current = experiment

        # Create directory
        exp_dir = self._dir(experiment.experiment_id)
        exp_dir.mkdir(parents=True, exist_ok=True)

        # Save config
        self._save_config(experiment)

        logger.info(
            f"Experiment created: {experiment.experiment_id} "
            f"({config.name}, hash={config.config_hash})"
        )
        return experiment

    def start(self, experiment_id: str | None = None) -> None:
        """Mark an experiment as running."""
        exp = self._current if experiment_id is None else self._load(experiment_id)
        if exp:
            exp.status = "running"
            self._save_config(exp)

    def complete(
        self,
        metrics: ExperimentMetrics,
        trades: pd.DataFrame | None = None,
        equity_curve: pd.DataFrame | None = None,
        experiment_id: str | None = None,
    ) -> Experiment:
        """Complete an experiment with results."""
        exp = self._current if experiment_id is None else self._load(experiment_id)
        if exp is None:
            raise ValueError(f"Experiment not found: {experiment_id}")

        exp.metrics = metrics
        exp.status = "completed"
        exp.completed_at = datetime.now(timezone.utc).isoformat()

        # Save artifacts
        exp_dir = self._dir(exp.experiment_id)
        self._save_config(exp)  # Save updated status
        self._save_metrics(exp)
        if trades is not None:
            trades.to_parquet(exp_dir / "trades.parquet", index=False)
        if equity_curve is not None:
            equity_curve.to_parquet(exp_dir / "equity_curve.parquet", index=False)

        logger.info(
            f"Experiment completed: {exp.experiment_id} "
            f"(Sharpe={metrics.sharpe_ratio:.2f}, "
            f"MaxDD={metrics.max_drawdown_pct:.2f}%, "
            f"Trades={metrics.total_trades})"
        )
        return exp

    def fail(self, error: str, experiment_id: str | None = None) -> None:
        """Mark an experiment as failed."""
        exp = self._current if experiment_id is None else self._load(experiment_id)
        if exp:
            exp.status = "failed"
            exp.error = error
            exp.completed_at = datetime.now(timezone.utc).isoformat()
            self._save_config(exp)

    def list_experiments(
        self,
        status: str | None = None,
        tag: str | None = None,
        sort_by: str = "created_at",
        reverse: bool = True,
    ) -> list[Experiment]:
        """List all experiments, optionally filtered."""
        experiments = []
        for exp_dir in sorted(self.experiments_dir.iterdir()):
            if not exp_dir.is_dir():
                continue
            try:
                exp = self._load(exp_dir.name)
                if exp is None:
                    continue
                if status and exp.status != status:
                    continue
                if tag and tag not in exp.tags:
                    continue
                experiments.append(exp)
            except Exception:
                continue

        experiments.sort(
            key=lambda e: getattr(e, sort_by, e.created_at),
            reverse=reverse,
        )
        return experiments

    def compare(
        self,
        experiment_ids: list[str],
    ) -> pd.DataFrame:
        """Compare metrics across experiments."""
        rows = []
        for eid in experiment_ids:
            exp = self._load(eid)
            if exp is None:
                continue
            row = {
                "experiment_id": eid,
                "name": exp.config.name,
                "status": exp.status,
                "config_hash": exp.config.config_hash,
            }
            row.update(exp.metrics.to_dict())
            rows.append(row)

        return pd.DataFrame(rows)

    def get_best(
        self,
        metric: str = "sharpe_ratio",
        min_trades: int = 10,
    ) -> Experiment | None:
        """Get the best experiment by a given metric."""
        completed = self.list_experiments(status="completed")
        valid = [e for e in completed if e.metrics.total_trades >= min_trades]
        if not valid:
            return None
        return max(valid, key=lambda e: getattr(e.metrics, metric, 0.0))

    def _dir(self, experiment_id: str) -> Path:
        return self.experiments_dir / experiment_id

    def _save_config(self, experiment: Experiment) -> None:
        path = self._dir(experiment.experiment_id) / "config.yaml"
        import yaml
        with path.open("w") as f:
            yaml.dump(experiment.to_dict(), f, default_flow_style=False)

    def _save_metrics(self, experiment: Experiment) -> None:
        path = self._dir(experiment.experiment_id) / "metrics.json"
        with path.open("w") as f:
            json.dump(experiment.metrics.to_dict(), f, indent=2, default=str)

    def _load(self, experiment_id: str) -> Experiment | None:
        exp_dir = self._dir(experiment_id)
        if not exp_dir.exists():
            return None

        config_path = exp_dir / "config.yaml"
        metrics_path = exp_dir / "metrics.json"

        if not config_path.exists():
            return None

        import yaml
        with config_path.open("r") as f:
            data = yaml.safe_load(f)

        if data is None:
            return None

        config = ExperimentConfig(**data.get("config", {}))
        metrics_data = {}
        if metrics_path.exists():
            with metrics_path.open("r") as f:
                metrics_data = json.load(f)

        return Experiment(
            experiment_id=data.get("experiment_id", experiment_id),
            config=config,
            metrics=ExperimentMetrics(**metrics_data),
            status=data.get("status", "unknown"),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
            error=data.get("error", ""),
            tags=data.get("tags", []),
        )
