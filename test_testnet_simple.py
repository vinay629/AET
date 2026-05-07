"""Simple test to debug testnet connection."""

from binance.client import Client

# Your testnet credentials
API_KEY = "fhLjAkADLHUP4N51WRJiPNMqr3r2sCb2ectAUorHD7jAS5aigGdZv4djc3Ir5Wur"
SECRET = "T5MR1pmv3k6NaIJqRce04JZYdmkZZciQJ8SBYWHoAKi7LW3BcJgMuoGjrORE7ngA"

print("Testing testnet connection...")
print(f"API Key length: {len(API_KEY)}")
print(f"Secret length: {len(SECRET)}")
print(f"API Key starts with: {API_KEY[:20]}")
print(f"Secret starts with: {SECRET[:20]}")

try:
    client = Client(API_KEY, SECRET, testnet=True)
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
