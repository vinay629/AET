"""Check recent orders on testnet."""

from pydantic import SecretStr
from binance.client import Client
from baet.config.loader import load_settings

settings = load_settings()
secrets = settings.secrets

api_key = secrets.live_binance_api_key or secrets.binance_api_key
api_secret = secrets.live_binance_api_secret or secrets.binance_api_secret

# Handle SecretStr properly
if isinstance(api_key, SecretStr):
    api_key = api_key.get_secret_value()
if isinstance(api_secret, SecretStr):
    api_secret = api_secret.get_secret_value()

client = Client(api_key, api_secret, testnet=True)

print("Recent BTCUSDT Orders:")
print("=" * 60)

orders = client.get_all_orders(symbol='BTCUSDT')

for order in orders[-5:]:  # Last 5 orders
    print(f"  ID: {order['orderId']}")
    print(f"    Side: {order['side']}")
    print(f"    Type: {order['type']}")
    print(f"    Status: {order['status']}")
    print(f"    Executed: {order['executedQty']} BTC")
    print(f"    Total: ${float(order['cummulativeQuoteQty']):.2f}")
    print()
