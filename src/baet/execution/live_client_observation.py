"""Live client for BAET - Observation Mode (Phase 3)."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from binance.client import Client as BinanceClient
from pydantic import SecretStr
from baet.config.loader import load_settings
from baet.config.models import Settings


class LiveClientObservation:
    """Live client in observation-only mode (no orders placed).

    Used for Phase 3 (Day 1-2) to validate signals
    without risking capital.

    Supports both testnet (demo) and production.
    Testnet URL: testnet.binance.vision
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.testnet = settings.live.testnet if hasattr(settings.live, "testnet") else True

        # Get API credentials from secrets
        secrets = settings.secrets
        api_key = secrets.live_binance_api_key or secrets.binance_api_key
        api_secret = secrets.live_binance_api_secret or secrets.binance_api_secret

        # Handle SecretStr properly
        if isinstance(api_key, SecretStr):
            api_key_str = api_key.get_secret_value()
        else:
            api_key_str = str(api_key) if api_key else ""

        if isinstance(api_secret, SecretStr):
            api_secret_str = api_secret.get_secret_value()
        else:
            api_secret_str = str(api_secret) if api_secret else ""

        # Initialize client with testnet support
        # According to Binance API docs:
        # - Testnet uses: https://testnet.binance.vision
        # - Production uses: https://api.binance.com
        if self.testnet:
            # Testnet configuration
            self.client = BinanceClient(api_key_str, api_secret_str, testnet=True)
            print(f"✅ Connected to Binance TESTNET (demo/sandbox)")
        else:
            # Production configuration
            self.client = BinanceClient(api_key_str, api_secret_str, testnet=False)
            print(f"⚠️ Connected to Binance PRODUCTION (real money)")

        self.observation_mode = True
        self.signals_generated = []
        self.account_info_cache = None
        self.last_account_check = 0

    def get_account_info(self) -> dict[str, Any]:
        """Get account information from Binance.

        Returns:
            Dictionary with account balances and status
        """
        try:
            account = self.client.get_account()

            # Extract relevant info
            balances = {}
            for balance in account.get("balances", []):
                free = float(balance.get("free", 0))
                locked = float(balance.get("locked", 0))
                if free > 0 or locked > 0:
                    balances[balance["asset"]] = {
                        "free": free,
                        "locked": locked,
                        "total": free + locked,
                    }

            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "account_type": account.get("accountType", "SPOT"),
                "can_trade": account.get("canTrade", False),
                "can_withdraw": account.get("canWithdraw", False),
                "can_deposit": account.get("canDeposit", False),
                "balances": balances,
                "total_usdt_value": self._calculate_total_usdt_value(balances),
                "raw": account,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    def get_open_orders(self, symbol: Optional[str] = None) -> dict[str, Any]:
        """Get open orders.

        Args:
            symbol: Optional symbol filter (e.g., "BTCUSDT")

        Returns:
            Dictionary with open orders
        """
        try:
            if symbol:
                orders = self.client.get_open_orders(symbol=symbol)
            else:
                orders = self.client.get_open_orders()

            return {
                "success": True,
                "count": len(orders),
                "orders": orders,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    def get_current_price(self, symbol: str) -> dict[str, Any]:
        """Get current price for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            Dictionary with price info
        """
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return {
                "success": True,
                "symbol": symbol,
                "price": float(ticker["price"]),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
            }

    def validate_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Validate a trading signal without executing it.

        Args:
            signal: Trading signal dictionary

        Returns:
            Validation result with account impact analysis
        """
        symbol = signal.get("symbol", "")
        side = signal.get("side", "")
        quantity = signal.get("quantity", 0)

        # Get current price
        price_info = self.get_current_price(symbol)
        if not price_info["success"]:
            return {"valid": False, "error": f"Cannot get price: {price_info.get('error')}"}

        current_price = price_info["price"]
        order_value = current_price * quantity

        # Get account info
        account_info = self.get_account_info()
        if not account_info["success"]:
            return {
                "valid": False,
                "error": f"Cannot get account info: {account_info.get('error')}",
            }

        # Check if we have enough balance
        quote_asset = symbol.replace("USDT", "")
        balance = account_info["balances"].get("USDT", {}).get("free", 0)

        validation = {
            "valid": True,
            "signal": signal,
            "current_price": current_price,
            "order_value_usdt": order_value,
            "account_balance_usdt": balance,
            "sufficient_balance": balance >= order_value,
            "timestamp": datetime.now().isoformat(),
        }

        # Log signal for observation
        self.signals_generated.append(
            {"signal": signal, "validation": validation, "timestamp": datetime.now().isoformat()}
        )

        return validation

    def _calculate_total_usdt_value(self, balances: dict) -> float:
        """Calculate total portfolio value in USDT."""
        total = 0.0

        # Add USDT balance directly
        if "USDT" in balances:
            total += balances["USDT"]["total"]

        # For other assets, get current price (simplified - just count if no price)
        for asset, data in balances.items():
            if asset == "USDT":
                continue
            try:
                ticker = self.client.get_symbol_ticker(symbol=f"{asset}USDT")
                price = float(ticker["price"])
                total += data["total"] * price
            except:
                # If can't get price, skip
                pass

        return total

    def get_observation_summary(self) -> dict[str, Any]:
        """Get summary of observation period.

        Returns:
            Dictionary with observation stats
        """
        return {
            "observation_mode": self.observation_mode,
            "signals_generated": len(self.signals_generated),
            "signals": self.signals_generated[-10:],  # Last 10
            "timestamp": datetime.now().isoformat(),
        }

    def check_emergency_stop(self) -> bool:
        """Check if emergency stop file exists.

        Returns:
            True if should stop, False otherwise
        """
        stop_file = Path("EMERGENCY_STOP.txt")
        return stop_file.exists()


def create_observation_client() -> Optional[LiveClientObservation]:
    """Create a live client in observation mode.

    Returns:
        LiveClientObservation instance or None if error
    """
    try:
        settings = load_settings()

        # Check if live mode is enabled in config
        if not hasattr(settings, "live") or not settings.live:
            print("Live mode not enabled in config")
            return None

        if not settings.live.enabled:
            print("Live mode not enabled in config")
            return None

        # Check if we have API credentials in secrets
        if not hasattr(settings, "secrets"):
            print("No secrets configured")
            return None

        # Get API credentials from secrets
        secrets = settings.secrets
        api_key = secrets.live_binance_api_key or secrets.binance_api_key
        api_secret = secrets.live_binance_api_secret or secrets.binance_api_secret

        if not api_key or not api_secret:
            print("API credentials not configured")
            print(f"  live_binance_api_key set: {bool(secrets.live_binance_api_key)}")
            print(f"  binance_api_key set: {bool(secrets.binance_api_key)}")
            return None

        # Validate credentials are SecretStr and have values
        if isinstance(api_key, SecretStr):
            api_key_value = api_key.get_secret_value()
        else:
            api_key_value = str(api_key) if api_key else ""

        if isinstance(api_secret, SecretStr):
            api_secret_value = api_secret.get_secret_value()
        else:
            api_secret_value = str(api_secret) if api_secret else ""

        if not api_key_value or not api_secret_value:
            print("API credentials are empty")
            return None

        print("  ✓ API credentials validated")

        return LiveClientObservation(settings)
    except Exception as e:
        print(f"Error creating observation client: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Test the observation client
    client = create_observation_client()

    if client:
        print("=== Account Info ===")
        info = client.get_account_info()
        print(f"Success: {info['success']}")
        if info["success"]:
            print(f"Account Type: {info['account_type']}")
            print(f"Can Trade: {info['can_trade']}")
            print(f"Total USDT Value: ${info['total_usdt_value']:.2f}")
            print(f"Balances: {info['balances']}")

        print("\n=== Current Prices ===")
        for symbol in ["BTCUSDT", "ETHUSDT"]:
            price = client.get_current_price(symbol)
            if price["success"]:
                print(f"{symbol}: ${price['price']:.2f}")

        print("\n=== Observation Summary ===")
        summary = client.get_observation_summary()
        print(f"Signals Generated: {summary['signals_generated']}")
    else:
        print("Failed to create observation client")
