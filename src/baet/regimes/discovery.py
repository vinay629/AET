from __future__ import annotations

import pkgutil
from importlib import import_module
from pathlib import Path

from baet.regimes.contracts import RegimeDetector


def discover_regimes() -> list[RegimeDetector]:
    package_dir = Path(__file__).resolve().parent
    package_name = "baet.regimes"
    discovered: list[RegimeDetector] = []

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name.startswith("_") or module_info.name in {"contracts", "discovery"}:
            continue
        module = import_module(f"{package_name}.{module_info.name}")
        # Look for classes with metadata attribute (detector instances or classes)
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            obj = getattr(module, attr_name)
            # Accept classes that appear to be detectors (have detect method)
            if hasattr(obj, "detect") and hasattr(obj, "metadata"):
                try:
                    instance = obj() if not isinstance(obj, type) else obj
                    if hasattr(instance, "detect"):
                        discovered.append(instance)
                except Exception:
                    continue
    return discovered


def filter_supported_regimes(
    regimes: list[RegimeDetector],
    symbol: str,
    timeframe: str,
) -> list[RegimeDetector]:
    # For now, all regime detectors are considered applicable to all symbols/timeframes.
    # This can be extended later with a supports() method on detectors.
    return regimes
