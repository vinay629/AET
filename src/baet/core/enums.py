from enum import StrEnum


class AppMode(StrEnum):
    DEV = "dev"
    PAPER = "paper"
    LIVE = "live"


class RegimeLabel(StrEnum):
    """Market regime classification labels."""
    TRENDING = "trending"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
