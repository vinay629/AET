from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from baet.config.models import BacktestConfig
from baet.core.models import BacktestArtifacts
from baet.data.interfaces import BacktestEngine
from baet.strategies.adapters import adapt_order_intent_to_backtest_signals

if TYPE_CHECKING:
    from baet.risk.engine import RiskEngine


# Lazy import to avoid circular imports
def _get_risk_engine() -> type[RiskEngine]:
    from baet.risk.engine import RiskEngine

    return RiskEngine


class PortfolioBacktestEngine(BacktestEngine):
    def __init__(self, config: BacktestConfig, risk_engine: RiskEngine | None = None) -> None:
        self.config = config
        self.risk_engine = risk_engine  # NEW: Optional RiskEngine

    def run(
        self,
        market_frames: dict[tuple[str, str], pd.DataFrame],
        signals: dict[tuple[str, str], pd.DataFrame],
        run_name: str,
    ) -> BacktestArtifacts:
        prepared = []
        for key, market in market_frames.items():
            # Check if signals need adaptation
            sig = signals[key]
            if "close_time" not in sig.columns and "timestamp" in sig.columns:
                sig = sig.rename(columns={"timestamp": "close_time"})

            if "signal" not in sig.columns and "target_position" in sig.columns:
                sig["signal"] = (sig["target_position"] > 0).astype(int)

            signal_frame = sig[["close_time", "signal"]].copy()
            merged = market.merge(signal_frame, on="close_time", how="left").fillna({"signal": 0})
            merged["symbol_key"] = f"{key[0]}:{key[1]}"
            prepared.append(merged)

        combined = (
            pd.concat(prepared, ignore_index=True).sort_values("close_time").reset_index(drop=True)
        )

        cash = self.config.initial_cash
        positions: dict[str, float] = {}
        equity_rows: list[dict[str, object]] = []
        trade_rows: list[dict[str, object]] = []

        # BOLT: Using itertuples and manual grouping for massive speedup over groupby().iterrows()
        # Conversion to itertuples avoids the heavy overhead of creating Pandas Series for each row.
        last_timestamp = None
        current_group_rows = []

        # Helper to process equity snapshot at the end of a timestamp
        def record_equity(ts, group_items):
            m_value = 0.0
            snapshots = {}
            for item in group_items:
                s_key = str(item.symbol_key)
                u = positions.get(s_key, 0.0)
                val = u * float(item.close)
                m_value += val
                snapshots[s_key] = val

            equity_rows.append(
                {
                    "timestamp": ts,
                    "cash": cash,
                    "market_value": m_value,
                    "equity": cash + m_value,
                    **snapshots,
                }
            )

        price_col_name = "open" if self.config.execution_price == "next_open" else "close"

        for row in combined.itertuples(index=False):
            timestamp = row.close_time

            if last_timestamp is not None and timestamp != last_timestamp:
                record_equity(last_timestamp, current_group_rows)
                current_group_rows = []

            symbol_key = str(row.symbol_key)
            current_units = positions.get(symbol_key, 0.0)
            signal = int(row.signal)
            fill_price = float(getattr(row, price_col_name)) * (1.0 + self.config.slippage_rate)

            # Risk check
            if self.risk_engine:
                signal_dict = {
                    "action": "BUY" if signal > 0 else ("SELL" if signal < 0 else "HOLD"),
                    "target_position": signal,
                    "confidence": 1.0,
                    "size_hint": self.config.allocation_per_signal,
                    "strategy_name": "backtest",
                    "symbol": row.symbol,
                    "timestamp": timestamp,
                }
                # BOLT: Removed redundant _get_risk_engine() call in hot loop
                result = self.risk_engine.evaluate_signal(signal_dict)

                if not result.approved or result.adjusted_action == "HOLD":
                    # Still track for equity snapshot even if trade is rejected
                    current_group_rows.append(row)
                    last_timestamp = timestamp
                    continue

                if result.adjusted_size is not None:
                    self.config.allocation_per_signal = result.adjusted_size

            # Execution logic
            if signal > 0 and current_units == 0.0:
                target_cash = cash * self.config.allocation_per_signal
                if target_cash > 0.0:
                    fee = target_cash * self.config.fee_rate
                    net_cash = target_cash - fee
                    units = net_cash / fill_price
                    cash -= target_cash
                    positions[symbol_key] = units
                    trade_rows.append(
                        {
                            "timestamp": timestamp,
                            "symbol": row.symbol,
                            "timeframe": row.timeframe,
                            "side": "BUY",
                            "price": fill_price,
                            "units": units,
                            "fee": fee,
                        }
                    )
            elif signal <= 0 and current_units > 0.0:
                gross = current_units * fill_price
                fee = gross * self.config.fee_rate
                cash += gross - fee
                positions[symbol_key] = 0.0
                trade_rows.append(
                    {
                        "timestamp": timestamp,
                        "symbol": row.symbol,
                        "timeframe": row.timeframe,
                        "side": "SELL",
                        "price": fill_price,
                        "units": current_units,
                        "fee": fee,
                    }
                )

            current_group_rows.append(row)
            last_timestamp = timestamp

        if last_timestamp is not None:
            record_equity(last_timestamp, current_group_rows)

        equity_curve = pd.DataFrame(equity_rows)
        trades = pd.DataFrame(trade_rows)
        if equity_curve.empty:
            symbol_returns = pd.DataFrame(columns=["timestamp", "symbol_key", "return"])
            metrics = pd.DataFrame(columns=["metric", "value"])
        else:
            symbol_columns = [col for col in equity_curve.columns if ":" in col]
            symbol_returns = equity_curve[["timestamp", *symbol_columns]].melt(
                id_vars="timestamp",
                var_name="symbol_key",
                value_name="market_value",
            )
            symbol_returns["return"] = symbol_returns.groupby("symbol_key")[
                "market_value"
            ].pct_change()
            returns = equity_curve["equity"].pct_change().fillna(0.0)
            final_equity = float(equity_curve["equity"].iloc[-1])
            initial_equity = float(equity_curve["equity"].iloc[0])
            metrics = pd.DataFrame(
                [
                    {"metric": "final_equity", "value": final_equity},
                    {
                        "metric": "total_return",
                        "value": float((final_equity / initial_equity) - 1.0),
                    },
                    {"metric": "trade_count", "value": float(len(trades))},
                    {"metric": "mean_bar_return", "value": float(returns.mean())},
                ]
            )

        metadata: dict[str, object] = {
            "run_name": run_name,
            "config": self.config.model_dump(),
            "symbols": sorted({key[0] for key in market_frames}),
            "timeframes": sorted({key[1] for key in market_frames}),
        }
        return BacktestArtifacts(
            equity_curve=equity_curve,
            trades=trades,
            symbol_returns=symbol_returns,
            metrics=metrics,
            metadata=metadata,
        )

    def run_order_intent(
        self,
        market_frames: dict[tuple[str, str], pd.DataFrame],
        signals: dict[tuple[str, str], pd.DataFrame],
        run_name: str,
    ) -> BacktestArtifacts:
        adapted = {
            key: adapt_order_intent_to_backtest_signals(signal_frame)
            for key, signal_frame in signals.items()
        }
        return self.run(market_frames=market_frames, signals=adapted, run_name=run_name)
