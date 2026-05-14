"""Database models for persistent trade state.

Inspired by: https://github.com/ccxt/binance-trade-bot
Uses SQLAlchemy ORM with SQLite for local persistence.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class Interval(enum.Enum):
    """Time interval for coin value snapshots."""
    MINUTELY = "minutely"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class TradeState(enum.Enum):
    """State of a trade."""
    STARTED = "started"
    ORDERED = "ordered"
    COMPLETE = "complete"
    CANCELED = "canceled"


class Coin(Base):
    """Represents a tradable coin."""
    __tablename__ = "coins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    # Relationships
    values = relationship("CoinValue", back_populates="coin", cascade="all, delete-orphan")
    scout_histories_from = relationship("ScoutHistory", foreign_keys="ScoutHistory.from_coin_id", back_populates="from_coin")
    scout_histories_to = relationship("ScoutHistory", foreign_keys="ScoutHistory.to_coin_id", back_populates="to_coin")
    trades_from = relationship("Trade", foreign_keys="Trade.from_coin_id", back_populates="from_coin")
    trades_to = relationship("Trade", foreign_keys="Trade.to_coin_id", back_populates="to_coin")

    def __repr__(self) -> str:
        return f"<Coin(symbol='{self.symbol}', enabled={self.enabled})>"


class Pair(Base):
    """Represents a tradable coin pair (from_coin → to_coin)."""
    __tablename__ = "pairs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    to_coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    ratio = Column(Float, default=0.0)
    enabled = Column(Boolean, default=True, nullable=False)

    # Relationships
    from_coin = relationship("Coin", foreign_keys=[from_coin_id], back_populates="scout_histories_from")
    to_coin = relationship("Coin", foreign_keys=[to_coin_id], back_populates="scout_histories_to")
    scout_histories = relationship("ScoutHistory", back_populates="pair", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Pair({self.from_coin.symbol} → {self.to_coin.symbol}, ratio={self.ratio})>"


class ScoutHistory(Base):
    """Records scout ratio observations for analysis."""
    __tablename__ = "scout_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pair_id = Column(Integer, ForeignKey("pairs.id"), nullable=False)
    from_coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    to_coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    target_ratio = Column(Float, nullable=False)
    current_coin_price = Column(Float, nullable=False)
    other_coin_price = Column(Float, nullable=False)
    datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    pair = relationship("Pair", back_populates="scout_histories")
    from_coin = relationship("Coin", foreign_keys=[from_coin_id])
    to_coin = relationship("Coin", foreign_keys=[to_coin_id])

    def __repr__(self) -> str:
        return f"<ScoutHistory(pair_id={self.pair_id}, ratio={self.target_ratio}, dt={self.datetime})>"


class CoinValue(Base):
    """Tracks coin value over time for portfolio analysis."""
    __tablename__ = "coin_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    usdt_value = Column(Float, default=0.0, nullable=False)
    interval = Column(Enum(Interval), default=Interval.MINUTELY, nullable=False)
    datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    coin = relationship("Coin", back_populates="values")

    def __repr__(self) -> str:
        return f"<CoinValue(coin_id={self.coin_id}, balance={self.balance}, usdt={self.usdt_value})>"


class CurrentCoin(Base):
    """Tracks the currently held coin (single-row state table)."""
    __tablename__ = "current_coin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    coin = relationship("Coin")

    def __repr__(self) -> str:
        return f"<CurrentCoin(coin_id={self.coin_id}, dt={self.datetime})>"


class Trade(Base):
    """Records completed trades."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    to_coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    selling = Column(Boolean, nullable=False)
    alt_starting_balance = Column(Float, default=0.0)
    crypto_starting_balance = Column(Float, default=0.0)
    alt_trade_amount = Column(Float, default=0.0)
    crypto_trade_amount = Column(Float, default=0.0)
    state = Column(Enum(TradeState), default=TradeState.STARTED, nullable=False)
    datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    from_coin = relationship("Coin", foreign_keys=[from_coin_id], back_populates="trades_from")
    to_coin = relationship("Coin", foreign_keys=[to_coin_id], back_populates="trades_to")

    def __repr__(self) -> str:
        direction = "SELL" if self.selling else "BUY"
        return f"<Trade({direction} {self.from_coin.symbol} → {self.to_coin.symbol}, state={self.state.value})>"

    def info(self) -> dict:
        """Return trade info as a dictionary for API responses."""
        return {
            "id": self.id,
            "from_coin": self.from_coin.symbol if self.from_coin else None,
            "to_coin": self.to_coin.symbol if self.to_coin else None,
            "selling": self.selling,
            "state": self.state.value,
            "alt_starting_balance": self.alt_starting_balance,
            "crypto_starting_balance": self.crypto_starting_balance,
            "alt_trade_amount": self.alt_trade_amount,
            "crypto_trade_amount": self.crypto_trade_amount,
            "datetime": self.datetime.isoformat() if self.datetime else None,
        }
