from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from baet.config.models import SecretsConfig, Settings

ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT_DIR / "config"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file {path} must contain a top-level mapping")
    return loaded


def _load_secret_settings() -> SecretsConfig:
    return SecretsConfig(
        binance_api_key=os.getenv("BAET_BINANCE_API_KEY", ""),
        binance_api_secret=os.getenv("BAET_BINANCE_API_SECRET", ""),
        live_binance_api_key=os.getenv("BAET_LIVE_BINANCE_API_KEY", ""),
        live_binance_api_secret=os.getenv("BAET_LIVE_BINANCE_API_SECRET", ""),
    )


def load_settings(mode: str | None = None, env_file: Path | None = None) -> Settings:
    load_dotenv(dotenv_path=env_file or ROOT_DIR / ".env", override=True)

    base_config = _read_yaml(CONFIG_DIR / "base.yaml")
    selected_mode = mode or os.getenv("BAET_MODE") or base_config.get("app", {}).get("mode", "dev")
    mode_config = _read_yaml(CONFIG_DIR / f"{selected_mode}.yaml")
    merged_config = _deep_merge(base_config, mode_config)

    if "BAET_LOG_LEVEL" in os.environ:
        merged_config.setdefault("app", {})
        merged_config["app"]["logging_level"] = os.environ["BAET_LOG_LEVEL"]

    merged_config.setdefault("app", {})
    merged_config["app"]["mode"] = selected_mode
    merged_config["secrets"] = _load_secret_settings().model_dump()

    return Settings.model_validate(merged_config)
