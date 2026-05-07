from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from baet.core.enums import AppMode


class AppConfig(BaseModel):
    name: str = "baet"
    mode: AppMode = AppMode.DEV
    logging_level: str = "INFO"


class MarketConfig(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    timeframes: list[str] = Field(default_factory=lambda: ["1h", "4h"])


class StorageConfig(BaseModel):
    raw_data_dir: Path = Path("data/raw")
    processed_data_dir: Path = Path("data/processed")
    results_dir: Path = Path("data/results")
    logs_dir: Path = Path("logs")
    artifacts_dir: Path = Path("artifacts")
    models_dir: Path = Path("models")


class PaperTradingConfig(BaseModel):
    """Configuration for paper trading."""
    enabled: bool = True
    initial_balance: float = 10_000.0
    loop_interval_seconds: int = 60
    stop_on_error: bool = False
    max_consecutive_errors: int = 10
    notification_webhook: str = ""
    logging: dict = Field(default_factory=lambda: {
        "enabled": True,
        "level": "INFO",
        "directory": "logs/paper",
        "rotation": "daily",
        "max_files": 30,
    })


class LiveConfig(BaseModel):
    """Configuration for live trading."""
    enabled: bool = False
    require_explicit_confirmation: bool = True
    simulation_mode: bool = True
    testnet: bool = True
    
    # Order submission
    order_submission: dict = Field(default_factory=lambda: {
        "enabled": False,
        "max_order_size": 10.0,
        "min_order_size": 1.0,
        "test_symbols": ["BTCUSDT", "ETHUSDT"],
    })
    
    # Safety limits
    safety: dict = Field(default_factory=lambda: {
        "max_daily_trades": 5,
        "max_position_value": 100.0,
        "allowed_deviation_pct": 5.0,
    })
    
    # Account touchpoints
    account_touchpoints: list[str] = Field(default_factory=lambda: [
        "account_info",
        "open_orders",
        "order_status",
    ])


class BinanceConfig(BaseModel):
    rest_base_url: str = "https://api.binance.com"
    websocket_base_url: str = "wss://stream.binance.com:9443/ws"
    historical_limit: int = 1000
    request_timeout_seconds: int = 30
    live_stream_enabled: bool = True
    market_data_touchpoints: list[str] = Field(default_factory=list)
    account_touchpoints: list[str] = Field(default_factory=list)


class RiskConfig(BaseModel):
    max_risk_per_trade: float = 0.01
    max_portfolio_exposure: float = 0.20
    policy: dict = Field(default_factory=dict)
    
    def get_policy(self):
        """Lazily load and return the RiskPolicy object."""
        if not hasattr(self, '_policy_obj'):
            from baet.risk.policy import RiskPolicy
            if isinstance(self.policy, dict) and self.policy:
                self._policy_obj = RiskPolicy(**self.policy)
            else:
                self._policy_obj = RiskPolicy()
        return self._policy_obj


class FeatureConfig(BaseModel):
    return_windows: list[int] = Field(default_factory=lambda: [1, 3, 6])
    volatility_windows: list[int] = Field(default_factory=lambda: [5, 10])
    trend_windows: list[int] = Field(default_factory=lambda: [5, 10, 20])
    volume_windows: list[int] = Field(default_factory=lambda: [5, 10])


class BacktestConfig(BaseModel):
    initial_cash: float = 10_000.0
    fee_rate: float = 0.001
    slippage_rate: float = 0.0005
    execution_price: Literal["close", "next_open"] = "next_open"
    allocation_per_signal: float = 0.5


class ReportingConfig(BaseModel):
    backtests_dir: Path = Path("data/results/backtests")
    summaries_dir: Path = Path("data/results/summaries")


class DashboardConfig(BaseModel):
    """Configuration for Streamlit dashboard."""
    enabled: bool = True
    port: int = 8501
    theme: str = "light"  # Use "light" for better contrast and visibility
    auto_refresh: bool = True
    refresh_interval_seconds: int = 30
    max_recent_trades: int = 50
    max_log_entries: int = 100


class SecretsConfig(BaseModel):
    binance_api_key: str = ""
    binance_api_secret: str = ""
    live_binance_api_key: str = ""
    live_binance_api_secret: str = ""


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    market: MarketConfig = Field(default_factory=MarketConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    paper: PaperTradingConfig = Field(default_factory=PaperTradingConfig)
    live: LiveConfig = Field(default_factory=LiveConfig)
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    secrets: SecretsConfig = Field(default_factory=SecretsConfig)

    @model_validator(mode="after")
    def validate_mode_guards(self) -> "Settings":
        # Check live.enabled first, then credentials
        if self.app.mode == AppMode.LIVE and not self.live.enabled:
            raise ValueError("live mode requires live.enabled=true")

        if self.app.mode == AppMode.LIVE and not (
            self.secrets.live_binance_api_key and self.secrets.live_binance_api_secret
        ):
            raise ValueError("live mode requires live Binance credentials")

        return self
