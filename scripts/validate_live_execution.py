"""Validate live execution path in testnet/simulation mode."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    """Run live execution validation."""
    print("=" * 60)
    print("BAET Live Execution Validation")
    print("=" * 60)
    print()

    # Check environment variables
    print("0. Checking environment variables...")
    import os

    live_key = os.getenv("BAET_LIVE_BINANCE_API_KEY")
    live_secret = os.getenv("BAET_LIVE_BINANCE_SECRET")

    if not live_key or not live_secret:
        print("   [ERROR] Environment variables not set!")
        print()
        print("   Set them with:")
        print("     $env:BAET_LIVE_BINANCE_API_KEY='your_key'")
        print("     $env:BAET_LIVE_BINANCE_SECRET='your_secret'")
        print()
        print("   Or create a .env file with:")
        print("     BAET_LIVE_BINANCE_API_KEY=your_key")
        print("     BAET_LIVE_BINANCE_SECRET=your_secret")
        sys.exit(1)

    print(f"   [OK] BAET_LIVE_BINANCE_API_KEY found")
    print(f"   [OK] BAET_LIVE_BINANCE_SECRET found")
    print()

    try:
        from baet.config.loader import load_settings
        from baet.live.execution import LiveExecutionClient

        # Load live config
        print("1. Loading live configuration...")
        settings = load_settings("live")
        print(f"   Mode: {settings.app.mode}")
        print(f"   Live enabled: {settings.live.enabled}")
        print(f"   Simulation mode: {settings.live.simulation_mode}")
        print(f"   Require confirmation: {settings.live.require_explicit_confirmation}")
        print()

        # Check API credentials
        print("2. Checking API credentials...")
        # Use secrets from settings, not a new empty SecretsConfig
        secrets = settings.secrets

        if not secrets.live_binance_api_key or not secrets.live_binance_api_secret:
            print("   [ERROR] API credentials not found in settings!")
            print()
            print("   Set environment variables:")
            print("     $env:BAET_LIVE_BINANCE_API_KEY='your_key'")
            print("     $env:BAET_LIVE_BINANCE_SECRET='your_secret'")
            sys.exit(1)

        print(f"   [OK] API credentials found in settings")
        print()

        # Initialize client in validation mode
        print("3. Initializing execution client (VALIDATION MODE)...")
        client = LiveExecutionClient(
            api_key=secrets.live_binance_api_key,
            api_secret=secrets.live_binance_api_secret,
            testnet=True,
            simulation=True,  # Don't actually submit orders
        )
        print("   [OK] Client initialized")
        print()

        # Validate account access
        print("4. Validating account access...")
        try:
            account = client.get_account_info()
            print(f"   [OK] Account type: {account.get('accountType', 'Unknown')}")

            balance = client.get_balance("USDT")
            print(f"   [OK] USDT Balance: ${balance:.2f}")
        except Exception as e:
            print(f"   [ERROR] Failed: {e}")
            sys.exit(1)
        print()

        # Test order simulation
        print("5. Testing order simulation...")
        test_symbol = "BTCUSDT"

        # Simulate buy
        print(f"   Testing BUY simulation for {test_symbol}...")
        result = client.place_market_buy(test_symbol, 0.001)
        print(f"   ✓ Simulation: {result}")

        # Simulate sell
        print(f"   Testing SELL simulation for {test_symbol}...")
        result = client.place_market_sell(test_symbol, 0.001)
        print(f"   ✓ Simulation: {result}")
        print()

        print("=" * 60)
        print("VALIDATION COMPLETE!")
        print("=" * 60)
        print()
        print("Results:")
        print("  ✓ Configuration loaded")
        print("  ✓ API credentials valid")
        print("  ✓ Account accessible")
        print("  ✓ Order simulation working")
        print()
        print("Next steps:")
        print("  1. Review logs for any warnings")
        print("  2. Test with testnet=True, simulation=False")
        print("  3. Monitor with dashboard")
        print("  4. When confident, switch to live trading")
        print()

    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Make sure python-binance is installed: pip install python-binance")
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 60)
        print("VALIDATION FAILED!")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
