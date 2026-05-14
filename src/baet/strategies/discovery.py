from __future__ import annotations

import pkgutil
from importlib import import_module
from pathlib import Path

from baet.strategies.contracts import StrategyContract


def discover_strategies() -> list[StrategyContract]:
    package_dir = Path(__file__).resolve().parent
    package_name = "baet.strategies"
    discovered: list[StrategyContract] = []
    seen_names: set[str] = set()

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name.startswith("_") or module_info.name in {"contracts", "discovery"}:
            continue
        module = import_module(f"{package_name}.{module_info.name}")
        strategy_classes = getattr(module, "STRATEGY_CLASSES", None)
        if strategy_classes is None:
            strategy_class = getattr(module, "STRATEGY_CLASS", None)
            if strategy_class is not None:
                strategy_classes = [strategy_class]
        if strategy_classes is None:
            continue
        for strategy_class in strategy_classes:
            strategy = strategy_class()
            if not isinstance(strategy, StrategyContract):
                raise TypeError(
                    f"Discovered strategy {module_info.name} does not implement StrategyContract"
                )
            if strategy.metadata.name in seen_names:
                raise ValueError(f"Duplicate strategy name discovered: {strategy.metadata.name}")
            seen_names.add(strategy.metadata.name)
            discovered.append(strategy)

    return discovered


def filter_supported_strategies(
    strategies: list[StrategyContract],
    symbol: str,
    timeframe: str,
) -> list[StrategyContract]:
    return [strategy for strategy in strategies if strategy.supports(symbol, timeframe)]
