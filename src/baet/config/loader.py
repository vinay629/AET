from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import SecretStr

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
    """Load secrets from environment variables."""
    def _get_secret(env_var: str) -> SecretStr:
        value = os.getenv(env_var, "")
        return SecretStr(value) if value else SecretStr("")
    
    return SecretsConfig(
        binance_api_key=_get_secret("BAET_BINANCE_API_KEY"),
        binance_api_secret=_get_secret("BAET_BINANCE_API_SECRET"),
        live_binance_api_key=_get_secret("BAET_LIVE_BINANCE_API_KEY") if os.getenv("BAET_LIVE_BINANCE_API_KEY") else _get_secret("BAET_BINANCE_API_KEY"),
        live_binance_api_secret=_get_secret("BAET_LIVE_BINANCE_API_SECRET") if os.getenv("BAET_LIVE_BINANCE_API_SECRET") else _get_secret("BAET_BINANCE_API_SECRET"),
    )


def load_settings(mode: str | None = None, env_file: Path | None = None) -> Settings:
    """Load and validate configuration for the specified mode."""
    # Determine which env file to load
    env_file_to_load = env_file or ROOT_DIR / ".env"
    
    # Only capture live credentials from environment if we're loading the default .env file
    # This prevents environment variables from interfering with tests that use .env.example
    import os
    capture_env_vars = (env_file is None)  # Only capture if no specific env_file is provided
    
    if capture_env_vars:
        env_live_key = os.getenv("BAET_LIVE_BINANCE_API_KEY", "")
        env_live_secret = os.getenv("BAET_LIVE_BINANCE_SECRET", "")
    else:
        env_live_key = ""
        env_live_secret = ""
    
    # Load .env file (with override=False so existing env vars are not overwritten)
    load_dotenv(dotenv_path=env_file_to_load, override=False)    
    
    base_config = _read_yaml(CONFIG_DIR / "base.yaml")
    selected_mode = mode or os.getenv("BAET_MODE") or base_config.get("app", {}).get("mode", "dev")
    mode_config = _read_yaml(CONFIG_DIR / f"{selected_mode}.yaml")
    merged_config = _deep_merge(base_config, mode_config)

    if "BAET_LOG_LEVEL" in os.environ:
        merged_config.setdefault("app", {})
        merged_config["app"]["logging_level"] = os.environ["BAET_LOG_LEVEL"]

    merged_config.setdefault("app", {})
    merged_config["app"]["mode"] = selected_mode
    
    # Load secrets - use captured env vars if available
    secrets = _load_secret_settings()
    # Override with captured environment variables if they exist
    if env_live_key:
        secrets.live_binance_api_key = env_live_key
    if env_live_secret:
        secrets.live_binance_api_secret = env_live_secret
    
    merged_config["secrets"] = secrets.model_dump()
    
    return Settings.model_validate(merged_config)
