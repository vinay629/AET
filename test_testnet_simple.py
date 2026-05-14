"""Simple test to debug testnet connection."""

import os
from binance.client import Client

# Load credentials from environment variables
API_KEY = os.getenv("BAET_TESTNET_API_KEY", "")
API_SECRET = os.getenv("BAET_TESTNET_API_SECRET", "")

print("Testing testnet connection...")

# Check if credentials are provided
if not API_KEY or not API_SECRET:
    print("❌ Error: BAET_TESTNET_API_KEY and BAET_TESTNET_API_SECRET must be set.")
    print("Set them using environment variables:")
    print("  $env:BAET_TESTNET_API_KEY='your_testnet_api_key'")
    print("  $env:BAET_TESTNET_API_SECRET='your_testnet_api_secret'")
    exit(1)

print("✅ Credentials loaded from environment variables")

try:
    client = Client(API_KEY, API_SECRET, testnet=True)
    print("\n✅ Client created successfully")

    print("\nFetching account info...")
    info = client.get_account()
    print(f"✅ Account info retrieved")
    print(f"Can Trade: {info['canTrade']}")
    print(f"Account Type: {info.get('accountType', 'N/A')}")

    # Show balances
    print("\nBalances:")
    for balance in info.get("balances", []):
        free = float(balance.get("free", 0))
        locked = float(balance.get("locked", 0))
        if free > 0 or locked > 0:
            print(f"  {balance['asset']}: {free} (free) + {locked} (locked)")

    print("\n✅ Testnet connection successful!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
