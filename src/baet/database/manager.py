"""Database manager for persistent trade state.

Inspired by: https://github.com/ccxt/binance-trade-bot
Provides session management, CRUD operations, and data migration.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Union

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from baet.database.models import (
    Base,
    Coin,
    CoinValue,
    CurrentCoin,
    Interval,
    Pair,
    ScoutHistory,
    Trade,
    TradeState,
)


class DatabaseManager:
    """Manages database connections and provides CRUD operations."""

    def __init__(self, db_path: Union[str, Path] = "data/crypto_trading.db"):
        self.db_path = str(db_path)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.SessionMaker = sessionmaker(bind=self.engine)

    @contextmanager
    def session(self):
        """Create a database session context manager."""
        session: Session = scoped_session(self.SessionMaker)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_database(self) -> None:
        """Create all database tables if they don't exist."""
        Base.metadata.create_all(self.engine)

    # === Coin Operations ===

    def set_coins(self, symbols: List[str]) -> None:
        """Add coins to the database and enable/disable based on the provided list."""
        with self.session() as session:
            # Disable coins not in the new list
            existing_coins: List[Coin] = session.query(Coin).all()
            for coin in existing_coins:
                coin.enabled = coin.symbol in symbols

            # Add new coins
            for symbol in symbols:
                coin = next((c for c in existing_coins if c.symbol == symbol), None)
                if coin is None:
                    session.add(Coin(symbol=symbol, enabled=True))
                else:
                    coin.enabled = True

        # Create pairs for all coin combinations
        self._create_pairs()

    def _create_pairs(self) -> None:
        """Create trading pairs for all enabled coin combinations."""
        with self.session() as session:
            coins: List[Coin] = session.query(Coin).filter(Coin.enabled).all()
            for from_coin in coins:
                for to_coin in coins:
                    if from_coin != to_coin:
                        pair = session.query(Pair).filter(
                            Pair.from_coin == from_coin,
                            Pair.to_coin == to_coin,
                        ).first()
                        if pair is None:
                            session.add(Pair(from_coin=from_coin, to_coin=to_coin))

    def get_coins(self, only_enabled: bool = True) -> List[Coin]:
        """Get all coins, optionally filtering to only enabled ones."""
        with self.session() as session:
            query = session.query(Coin)
            if only_enabled:
                query = query.filter(Coin.enabled)
            coins = query.all()
            session.expunge_all()
            return coins

    def get_coin(self, coin: Union[Coin, str]) -> Optional[Coin]:
        """Get a coin by symbol or return the coin object."""
        if isinstance(coin, Coin):
            return coin
        with self.session() as session:
            result = session.query(Coin).filter(Coin.symbol == coin).first()
            if result:
                session.expunge(result)
            return result

    # === Current Coin Operations ===

    def set_current_coin(self, coin: Union[Coin, str]) -> None:
        """Set the currently held coin."""
        coin_obj = self.get_coin(coin)
        if coin_obj is None:
            return
        with self.session() as session:
            coin_obj = session.merge(coin_obj)
            session.add(CurrentCoin(coin=coin_obj))

    def get_current_coin(self) -> Optional[Coin]:
        """Get the most recently held coin."""
        with self.session() as session:
            current = (
                session.query(CurrentCoin)
                .order_by(CurrentCoin.datetime.desc())
                .first()
            )
            if current is None:
                return None
            session.expunge(current.coin)
            return current.coin

    # === Pair Operations ===

    def get_pair(
        self, from_coin: Union[Coin, str], to_coin: Union[Coin, str]
    ) -> Optional[Pair]:
        """Get a trading pair by from/to coins."""
        from_obj = self.get_coin(from_coin)
        to_obj = self.get_coin(to_coin)
        if from_obj is None or to_obj is None:
            return None
        with self.session() as session:
            from_obj = session.merge(from_obj)
            to_obj = session.merge(to_obj)
            pair = session.query(Pair).filter(
                Pair.from_coin == from_obj,
                Pair.to_coin == to_obj,
            ).first()
            if pair:
                session.expunge(pair)
            return pair

    def get_pairs_from(
        self, from_coin: Union[Coin, str], only_enabled: bool = True
    ) -> List[Pair]:
        """Get all pairs originating from a specific coin."""
        coin_obj = self.get_coin(from_coin)
        if coin_obj is None:
            return []
        with self.session() as session:
            coin_obj = session.merge(coin_obj)
            query = session.query(Pair).filter(Pair.from_coin == coin_obj)
            if only_enabled:
                query = query.filter(Pair.enabled.is_(True))
            pairs = query.all()
            session.expunge_all()
            return pairs

    def get_pairs(self, only_enabled: bool = True) -> List[Pair]:
        """Get all trading pairs."""
        with self.session() as session:
            query = session.query(Pair)
            if only_enabled:
                query = query.filter(Pair.enabled.is_(True))
            pairs = query.all()
            session.expunge_all()
            return pairs

    # === Scout Operations ===

    def log_scout(
        self,
        pair: Pair,
        target_ratio: float,
        current_coin_price: float,
        other_coin_price: float,
    ) -> None:
        """Record a scout observation."""
        with self.session() as session:
            pair = session.merge(pair)
            from_coin = session.merge(pair.from_coin)
            to_coin = session.merge(pair.to_coin)
            sh = ScoutHistory(
                pair=pair,
                from_coin=from_coin,
                to_coin=to_coin,
                target_ratio=target_ratio,
                current_coin_price=current_coin_price,
                other_coin_price=other_coin_price,
            )
            session.add(sh)

    def prune_scout_history(self, hours: int = 24) -> None:
        """Remove scout history older than the specified hours."""
        time_diff = datetime.utcnow() - timedelta(hours=hours)
        with self.session() as session:
            session.query(ScoutHistory).filter(
                ScoutHistory.datetime < time_diff
            ).delete()

    # === Value Tracking Operations ===

    def log_coin_value(
        self, coin: Union[Coin, str], balance: float, usdt_value: float
    ) -> None:
        """Record a coin value snapshot."""
        coin_obj = self.get_coin(coin)
        if coin_obj is None:
            return
        with self.session() as session:
            coin_obj = session.merge(coin_obj)
            cv = CoinValue(
                coin=coin_obj,
                balance=balance,
                usdt_value=usdt_value,
                interval=Interval.MINUTELY,
            )
            session.add(cv)

    def prune_value_history(self) -> None:
        """Prune old value history, keeping aggregated data."""
        with self.session() as session:
            # Mark first entry per hour as hourly
            hourly_entries = (
                session.query(CoinValue)
                .group_by(CoinValue.coin_id, func.strftime("%H", CoinValue.datetime))
                .all()
            )
            for entry in hourly_entries:
                entry.interval = Interval.HOURLY

            # Mark first entry per day as daily
            daily_entries = (
                session.query(CoinValue)
                .group_by(CoinValue.coin_id, func.date(CoinValue.datetime))
                .all()
            )
            for entry in daily_entries:
                entry.interval = Interval.DAILY

            # Mark first entry per week as weekly
            weekly_entries = (
                session.query(CoinValue)
                .group_by(
                    CoinValue.coin_id, func.strftime("%Y-%W", CoinValue.datetime)
                )
                .all()
            )
            for entry in weekly_entries:
                entry.interval = Interval.WEEKLY

            # Delete old minutely entries (keep 24 hours)
            time_diff = datetime.utcnow() - timedelta(hours=24)
            session.query(CoinValue).filter(
                CoinValue.interval == Interval.MINUTELY,
                CoinValue.datetime < time_diff,
            ).delete()

            # Delete old hourly entries (keep 28 days)
            time_diff = datetime.utcnow() - timedelta(days=28)
            session.query(CoinValue).filter(
                CoinValue.interval == Interval.HOURLY,
                CoinValue.datetime < time_diff,
            ).delete()

            # Delete old daily entries (keep 1 year)
            time_diff = datetime.utcnow() - timedelta(days=365)
            session.query(CoinValue).filter(
                CoinValue.interval == Interval.DAILY,
                CoinValue.datetime < time_diff,
            ).delete()

    # === Trade Operations ===

    def start_trade_log(
        self, from_coin: Union[Coin, str], to_coin: Union[Coin, str], selling: bool
    ) -> TradeLog:
        """Start logging a new trade."""
        return TradeLog(self, from_coin, to_coin, selling)

    def get_trades(self, limit: int = 100) -> List[Trade]:
        """Get recent trades."""
        with self.session() as session:
            trades = (
                session.query(Trade)
                .order_by(Trade.datetime.desc())
                .limit(limit)
                .all()
            )
            session.expunge_all()
            return trades

    # === Migration ===

    def migrate_old_state(self) -> None:
        """Migrate from old dotfile format to database."""
        current_coin_file = Path(".current_coin")
        if current_coin_file.exists():
            coin_symbol = current_coin_file.read_text().strip()
            if coin_symbol:
                self.set_current_coin(coin_symbol)
            current_coin_file.rename(".current_coin.old")

        table_file = Path(".current_coin_table")
        if table_file.exists():
            table = json.loads(table_file.read_text())
            with self.session() as session:
                for from_symbol, to_dict in table.items():
                    for to_symbol, ratio in to_dict.items():
                        if from_symbol == to_symbol:
                            continue
                        from_coin = self.get_coin(from_symbol)
                        to_coin = self.get_coin(to_symbol)
                        if from_coin and to_coin:
                            from_coin = session.merge(from_coin)
                            to_coin = session.merge(to_coin)
                            pair = session.query(Pair).filter(
                                Pair.from_coin == from_coin,
                                Pair.to_coin == to_coin,
                            ).first()
                            if pair is None:
                                pair = Pair(from_coin=from_coin, to_coin=to_coin)
                                session.add(pair)
                            pair.ratio = ratio
            table_file.rename(".current_coin_table.old")


class TradeLog:
    """Context manager for logging a trade from start to completion."""

    def __init__(
        self,
        db: DatabaseManager,
        from_coin: Union[Coin, str],
        to_coin: Union[Coin, str],
        selling: bool,
    ):
        self.db = db
        self.from_coin = from_coin
        self.to_coin = to_coin
        self.selling = selling
        self.trade: Optional[Trade] = None
        self._create_trade()

    def _create_trade(self) -> None:
        """Create the initial trade record."""
        from_obj = self.db.get_coin(self.from_coin)
        to_obj = self.db.get_coin(self.to_coin)
        if from_obj is None or to_obj is None:
            return
        with self.db.session() as session:
            from_obj = session.merge(from_obj)
            to_obj = session.merge(to_obj)
            self.trade = Trade(
                from_coin=from_obj,
                to_coin=to_obj,
                selling=self.selling,
                state=TradeState.STARTED,
            )
            session.add(self.trade)
            session.flush()

    def set_ordered(
        self,
        alt_starting_balance: float,
        crypto_starting_balance: float,
        alt_trade_amount: float,
    ) -> None:
        """Mark the trade as ordered."""
        if self.trade is None:
            return
        with self.db.session() as session:
            trade = session.merge(self.trade)
            trade.alt_starting_balance = alt_starting_balance
            trade.crypto_starting_balance = crypto_starting_balance
            trade.alt_trade_amount = alt_trade_amount
            trade.state = TradeState.ORDERED

    def set_complete(self, crypto_trade_amount: float) -> None:
        """Mark the trade as complete."""
        if self.trade is None:
            return
        with self.db.session() as session:
            trade = session.merge(self.trade)
            trade.crypto_trade_amount = crypto_trade_amount
            trade.state = TradeState.COMPLETE

    def set_canceled(self) -> None:
        """Mark the trade as canceled."""
        if self.trade is None:
            return
        with self.db.session() as session:
            trade = session.merge(self.trade)
            trade.state = TradeState.CANCELED
