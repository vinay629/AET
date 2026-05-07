"""Script to place the first testnet order (M5.2 Day 3-4)."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from baet.config.loader import load_settings
from baet.execution.live_client_observation import create_observation_client
from datetime import datetime


def main():
    """Place the first testnet order."""
    print("=" * 60)
    print("BAET - Place First Testnet Order (M5.2 Day 3-4)")
    print("=" * 60)
    print()
    
    # Load settings
    try:
        settings = load_settings()
    except Exception as e:
        print(f"❌ Failed to load settings: {e}")
        sys.exit(1)
    
    # Check if live mode is enabled
    if not hasattr(settings, 'live') or not settings.live or not settings.live.enabled:
        print("❌ Live mode is not enabled in settings!")
        print("   Please set 'live.enabled: true' in config/live.yaml")
        sys.exit(1)
    
    print("✅ Live mode enabled")
    print(f"   Testnet: {settings.live.testnet}")
    print(f"   Simulation mode: {settings.live.simulation_mode}")
    print()
    
    # Create observation client (it can also place orders)
    print("Connecting to Binance TESTNET...")
    client = create_observation_client()
    
    if not client:
        print("❌ Failed to create client!")
        sys.exit(1)
    
    print("✅ Connected to Binance TESTNET")
    print()
    
    # Get account info
    print("Fetching account info...")
    account_info = client.get_account_info()
    
    if not account_info.get("success"):
        print(f"❌ Failed to get account info: {account_info.get('error')}")
        sys.exit(1)
    
    print(f"✅ Account Type: {account_info.get('account_type')}")
    print(f"✅ Total Value (USDT): ${account_info.get('total_usdt_value', 0):.2f}")
    print(f"✅ Can Trade: {account_info.get('can_trade')}")
    print()
    
    # Check risk limits
    print("Checking risk limits...")
    max_position_value = settings.live.risk.max_position_value_usdt
    max_daily_loss = settings.live.risk.max_daily_loss_usdt
    print(f"   Max position value: ${max_position_value}")
    print(f"   Max daily loss: ${max_daily_loss}")
    print()
    
    # Get current BTC price
    print("Getting current BTC price...")
    btc_price_data = client.get_current_price("BTCUSDT")
    
    if not btc_price_data.get("success"):
        print(f"❌ Failed to get BTC price: {btc_price_data.get('error')}")
        sys.exit(1)
    
    btc_price = btc_price_data.get("price", 0)
    print(f"✅ BTC Price: ${btc_price:,.2f}")
    print()
    
    # Calculate order size (small: $10-20)
    order_value_usdt = 15.0  # $15 demo order
    btc_quantity = order_value_usdt / btc_price
    
    # Round to appropriate precision (BTC: 6 decimal places)
    btc_quantity = round(btc_quantity, 6)
    
    print("Order Details:")
    print(f"   Symbol: BTCUSDT")
    print(f"   Side: BUY")
    print(f"   Quantity: {btc_quantity} BTC")
    print(f"   Price: ${btc_price:,.2f}")
    print(f"   Total Value: ~${order_value_usdt}")
    print()
    
    # Validate signal (check if we have enough balance)
    print("Validating signal...")
    signal = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": btc_quantity,
        "price": btc_price,
        "value_usdt": order_value_usdt
    }
    
    validation = client.validate_signal(signal)
    
    if not validation.get("success"):
        print(f"❌ Signal validation failed: {validation.get('error')}")
        sys.exit(1)
    
    if not validation.get("sufficient_balance"):
        print(f"❌ Insufficient balance!")
        print(f"   Required: ${validation.get('required_balance', 0):.2f}")
        print(f"   Available: ${validation.get('available_balance', 0):.2f}")
        sys.exit(1)
    
    print("✅ Signal validated")
    print(f"   Sufficient balance: Yes")
    print(f"   Required: ${validation.get('required_balance', 0):.2f}")
    print(f"   Available: ${validation.get('available_balance', 0):.2f}")
    print()
    
    # Check emergency stop
    if client.check_emergency_stop():
        print("🚨 EMERGENCY STOP DETECTED!")
        print("Order cancelled.")
        sys.exit(1)
    
    # Place the order
    print("=" * 60)
    print("PLACING ORDER...")
    print("=" * 60)
    print()
    
    # Note: The observation client doesn't have a place_order method
    # We need to use the Binance client directly for this first test
    print("Using Binance client to place MARKET order...")
    
    try:
        # Place a MARKET buy order
        order = client.client.create_order(
            symbol="BTCUSDT",
            side="BUY",
            type="MARKET",
            quantity=btc_quantity
        )
        
        print("✅ ORDER PLACED SUCCESSFULLY!")
        print()
        print("Order Details:")
        print(f"   Order ID: {order.get('orderId')}")
        print(f"   Symbol: {order.get('symbol')}")
        print(f"   Side: {order.get('side')}")
        print(f"   Type: {order.get('type')}")
        print(f"   Status: {order.get('status')}")
        print(f"   Executed Qty: {order.get('executedQty')}")
        print(f"   Cum Quote Qty: ${float(order.get('cummulativeQuoteQty', 0)):.2f}")
        print()
        print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("=" * 60)
        print("✅ First testnet order completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Failed to place order: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
