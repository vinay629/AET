from pathlib import Path

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


class PaperConfig(BaseModel):
    enabled: bool = True
    initial_balance: float = 10_000.0


class LiveConfig(BaseModel):
    enabled: bool = False
    require_explicit_confirmation: bool = True
    account_touchpoints: list[str] = Field(default_factory=list)


class BinanceConfig(BaseModel):
    market_data_touchpoints: list[str] = Field(default_factory=list)
    account_touchpoints: list[str] = Field(default_factory=list)


class RiskConfig(BaseModel):
    max_risk_per_trade: float = 0.01
    max_portfolio_exposure: float = 0.20


class SecretsConfig(BaseModel):
    binance_api_key: str = ""
    binance_api_secret: str = ""
    live_binance_api_key: str = ""
    live_binance_api_secret: str = ""


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    market: MarketConfig = Field(default_factory=MarketConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    paper: PaperConfig = Field(default_factory=PaperConfig)
    live: LiveConfig = Field(default_factory=LiveConfig)
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    secrets: SecretsConfig = Field(default_factory=SecretsConfig)

    @model_validator(mode="after")
    def validate_mode_guards(self) -> "Settings":
        if self.app.mode == AppMode.LIVE and not self.live.enabled:
            raise ValueError("live mode requires live.enabled=true")

        if self.app.mode == AppMode.LIVE and not (
            self.secrets.live_binance_api_key and self.secrets.live_binance_api_secret
        ):
            raise ValueError("live mode requires live Binance credentials")

        return self
