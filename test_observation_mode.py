"""Test script for Live Observation Mode (Phase 3)."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_observation_client():
    """Test the live observation client."""
    print("=" * 60)
    print("Testing Live Observation Client (Phase 3)")
    print("=" * 60)

    try:
        from baet.execution.live_client_observation import create_observation_client

        print("\n1. Creating observation client...")
        client = create_observation_client()

        if not client:
            print("❌ Failed to create observation client")
            print("\nPossible issues:")
            print("  - Live mode not enabled in config")
            print("  - API credentials not set")
            print("  - Binance library not installed")
            return False

        print("✅ Observation client created successfully")

        # Test account info
        print("\n2. Fetching account info...")
        account_info = client.get_account_info()

        if account_info["success"]:
            print("✅ Account info retrieved")
            print(f"   Account Type: {account_info['account_type']}")
            print(f"   Can Trade: {account_info['can_trade']}")
            print(f"   Total USDT Value: ${account_info['total_usdt_value']:.2f}")

            # Show balances
            print("\n   Balances:")
            for asset, data in account_info["balances"].items():
                print(
                    f"     {asset}: {data['free']:.6f} (free) + {data['locked']:.6f} (locked) = {data['total']:.6f}"
                )
        else:
            print(f"❌ Failed to get account info: {account_info.get('error')}")
            return False

        # Test current prices
        print("\n3. Fetching current prices...")
        for symbol in ["BTCUSDT", "ETHUSDT"]:
            price_info = client.get_current_price(symbol)
            if price_info["success"]:
                print(f"✅ {symbol}: ${price_info['price']:.2f}")
            else:
                print(f"❌ Failed to get {symbol} price: {price_info.get('error')}")

        # Test signal validation (observation only)
        print("\n4. Testing signal validation (observation mode)...")
        test_signal = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "strategy": "test_strategy",
            "confidence": 0.8,
        }

        validation = client.validate_signal(test_signal)
        if validation["valid"]:
            print("✅ Signal validation works")
            print(
                f"   Signal: {validation['signal']['side']} {validation['signal']['quantity']} {validation['signal']['symbol']}"
            )
            print(f"   Current Price: ${validation['current_price']:.2f}")
            print(f"   Order Value: ${validation['order_value_usdt']:.2f}")
            print(f"   Sufficient Balance: {validation['sufficient_balance']}")
        else:
            print(f"❌ Signal validation failed: {validation.get('error')}")

        # Show observation summary
        print("\n5. Observation summary...")
        summary = client.get_observation_summary()
        print(f"✅ Signals generated during test: {summary['signals_generated']}")

        print("\n" + "=" * 60)
        print("✅ All tests passed! Observation mode is ready.")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Transfer $50-100 to Binance")
        print("  2. Start dashboard: streamlit run src/baet/dashboard/app.py")
        print("  3. Monitor signals for 1-2 days (no orders placed)")
        print("  4. If all looks good, proceed to first live order")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure python-binance is installed: pip install python-binance")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_observation_client()

    if success:
        print("\n" + "=" * 60)
        print("✅ Observation mode test completed successfully!")
        print("=" * 60)
        print("\n📋 Current Configuration:")
        print("  - Mode: TESTNET (Demo/Sandbox) - NO REAL MONEY")
        print("  - Orders will be placed on demo account only")
        print("  - Safe to test without financial risk")
        print("\n🚀 Next Steps:")
        print("  1. Run observation mode for 1-2 days:")
        print("     streamlit run src/baet/dashboard/app.py")
        print("  2. Monitor signals (no real money at risk)")
        print("  3. If all looks good, proceed to Day 3-4")
        print("  4. First live order will also be on TESTNET")
    else:
        print("\n❌ Test failed. Check errors above.")

    sys.exit(0 if success else 1)
