"""Place a small testnet order quickly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from baet.config.loader import load_settings
from binance.client import Client


def main():
    print("Placing small testnet order...")
    
    # Load settings
    settings = load_settings()
    
    # Get API credentials
    secrets = settings.secrets
    api_key = secrets.live_binance_api_key or secrets.binance_api_key
    api_secret = secrets.live_binance_api_secret or secrets.binance_api_secret
    
    # Handle SecretStr
    if hasattr(api_key, 'get_secret_value'):
        api_key = api_key.get_secret_value()
    if hasattr(api_secret, 'get_secret_value'):
        api_secret = api_secret.get_secret_value()
    
    # Create testnet client
    client = Client(api_key, api_secret, testnet=True)
    
    print("✅ Connected to Binance TESTNET")
    
    # Get BTC price
    ticker = client.get_symbol_ticker(symbol="BTCUSDT")
    btc_price = float(ticker['price'])
    print(f"✅ BTC Price: ${btc_price:,.2f}")
    
    # Calculate quantity for $15 order - must be multiple of stepSize (0.00001)
    order_value = 15.0
    raw_quantity = order_value / btc_price
    # Round to 5 decimal places (stepSize = 0.00001)
    quantity = round(round(raw_quantity / 0.00001) * 0.00001, 5)
    
    print(f"\nPlacing order:")
    print(f"  Symbol: BTCUSDT")
    print(f"  Side: BUY")
    print(f"  Quantity: {quantity} BTC")
    print(f"  Value: ~${quantity * btc_price:.2f}")
    
    # Place market order
    try:
        order = client.create_order(
            symbol="BTCUSDT",
            side="BUY",
            type="MARKET",
            quantity=quantity
        )
        
        print("\n✅ ORDER PLACED SUCCESSFULLY!")
        print(f"  Order ID: {order['orderId']}")
        print(f"  Status: {order['status']}")
        print(f"  Executed Qty: {order['executedQty']}")
        print(f"  Cummulative Quote Qty: ${float(order['cummulativeQuoteQty']):.2f}")
        
    except Exception as e:
        print(f"\n❌ Order failed: {e}")


if __name__ == "__main__":
    main()
