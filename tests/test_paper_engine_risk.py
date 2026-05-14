from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from baet.paper.engine import PaperTradingEngine


class FakeOrderSimulator:
    def simulate_buy(self, price: float, units: float) -> tuple[float, float, float]:
        return price * 1.01, units, 1.0

    def simulate_sell(self, price: float, units: float) -> tuple[float, float, float]:
        fill_price = price * 0.99
        gross = fill_price * units
        return fill_price, gross - 1.0, 1.0


class FakePortfolio:
    def __init__(self) -> None:
        self.cash = 1000.0
        self.positions = {"BTCUSDT": {"units": 2.0, "avg_price": 100.0}}

    def buy(self, symbol: str, units: float, price: float, fee: float) -> bool:
        _ = fee
        self.positions[symbol] = {"units": units, "avg_price": price}
        return True

    def sell(self, symbol: str, units: float, price: float, fee: float) -> bool:
        _ = (units, price, fee)
        self.positions.pop(symbol, None)
        return True

    def get_positions(self) -> dict[str, dict[str, float]]:
        return self.positions.copy()

    def get_total_value(self, _market_data: Any = None) -> float:
        return 1000.0


class FakeRiskTracker:
    def __init__(self) -> None:
        self.executed_calls: list[tuple[str, float, float]] = []
        self.closed_calls: list[tuple[str, float, float, float]] = []

    def on_trade_executed(self, position_id: str, quantity: float, entry_price: float) -> None:
        self.executed_calls.append((position_id, quantity, entry_price))

    def on_position_closed(
        self, position_id: str, exit_price: float, entry_price: float, quantity: float
    ) -> None:
        self.closed_calls.append((position_id, exit_price, entry_price, quantity))


class FakeBrain:
    def __init__(self) -> None:
        self.trade_outcomes: list[dict[str, float | str]] = []

    def learn_from_trade(self, trade_outcome: dict[str, float | str]) -> None:
        self.trade_outcomes.append(trade_outcome)


class FakeAuditTrail:
    def log_trade_executed(self, *args: Any, **kwargs: Any) -> None:
        pass

    def log_position_opened(self, *args: Any, **kwargs: Any) -> None:
        pass

    def log_position_closed(self, *args: Any, **kwargs: Any) -> None:
        pass


def test_execute_paper_trades_tracks_risk_and_realized_learning() -> None:
    engine = cast(Any, PaperTradingEngine.__new__(PaperTradingEngine))
    engine.order_simulator = FakeOrderSimulator()
    engine.portfolio = FakePortfolio()
    engine.risk_tracker = FakeRiskTracker()
    engine.brain = FakeBrain()
    engine.audit_trail = FakeAuditTrail()
    engine.paper_logger = None
    engine._position_ids = {"BTCUSDT": "btc_position"}
    engine.config = SimpleNamespace()

    market_data = {"BTCUSDT": {"price": 110.0}}
    decisions = [{"symbol": "BTCUSDT", "action": "SELL", "units": 2.0}]

    engine._execute_paper_trades(decisions, market_data)

    assert engine.risk_tracker.closed_calls == [("btc_position", 108.9, 100.0, 2.0)]
    assert len(engine.brain.trade_outcomes) == 1
    assert engine.brain.trade_outcomes[0]["symbol"] == "BTCUSDT"
    assert engine.brain.trade_outcomes[0]["pnl_pct"] > 0


def test_execute_paper_trades_uses_position_id_on_buy() -> None:
    engine = cast(Any, PaperTradingEngine.__new__(PaperTradingEngine))
    engine.order_simulator = FakeOrderSimulator()
    engine.portfolio = FakePortfolio()
    engine.portfolio.positions = {}
    engine.risk_tracker = FakeRiskTracker()
    engine.brain = FakeBrain()
    engine.audit_trail = FakeAuditTrail()
    engine.paper_logger = None
    engine._position_ids = {}
    engine.config = SimpleNamespace()

    market_data = {"ETHUSDT": {"price": 200.0}}
    decisions = [{"symbol": "ETHUSDT", "action": "BUY", "units": 1.5}]

    engine._execute_paper_trades(decisions, market_data)

    assert len(engine.risk_tracker.executed_calls) == 1
    position_id, quantity, entry_price = engine.risk_tracker.executed_calls[0]
    assert position_id.startswith("ETHUSDT_")
    assert quantity == 1.5
    assert entry_price == 202.0
