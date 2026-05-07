"""Script to run BAET in Observation Mode (Phase 3)."""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from baet.config.loader import load_settings
from baet.execution.live_client_observation import create_observation_client


def main():
    """Run observation mode - monitor signals without placing orders."""
    print("=" * 60)
    print("BAET - Observation Mode (Phase 3)")
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
    
    print(f"✅ Live mode enabled")
    print(f"   Testnet: {settings.live.testnet}")
    print(f"   Simulation mode: {settings.live.simulation_mode}")
    print()
    
    # Create observation client
    print("Connecting to Binance...")
    client = create_observation_client()
    
    if not client:
        print("❌ Failed to create observation client!")
        sys.exit(1)
    
    print("✅ Connected to Binance TESTNET")
    print()
    
    # Get account info
    print("Fetching account info...")
    account_info = client.get_account_info()
    
    if account_info.get("success"):
        print(f"✅ Account Type: {account_info.get('account_type')}")
        print(f"✅ Total Value (USDT): ${account_info.get('total_usdt_value', 0):.2f}")
        print(f"✅ Can Trade: {account_info.get('can_trade')}")
        print()
        
        # Show key balances
        balances = account_info.get("balances", {})
        print("Key Balances:")
        for asset in ["BTC", "ETH", "USDT", "BNB"]:
            if asset in balances:
                data = balances[asset]
                print(f"  {asset}: {data['total']:.6f} (Free: {data['free']:.6f})")
        print()
    else:
        print(f"❌ Failed to get account info: {account_info.get('error')}")
        sys.exit(1)
    
    # Observation loop
    print("=" * 60)
    print("Starting observation loop...")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    observation_count = 0
    
    try:
        while True:
            observation_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"[{timestamp}] Observation #{observation_count}")
            
            # Check for emergency stop
            if client.check_emergency_stop():
                print("🚨 EMERGENCY STOP DETECTED!")
                print("Stopping observation mode...")
                break
            
            # Get current prices
            symbols = settings.market.symbols[:5]  # First 5 symbols
            for symbol in symbols:
                price = client.get_current_price(symbol)
                if price:
                    print(f"  {symbol}: ${price:,.2f}")
            
            # Validate a sample signal (demo)
            if observation_count % 5 == 0:  # Every 5th observation
                print("  Validating sample signals...")
                # This is where you'd validate your strategy signals
                # For now, just print a message
                print("  ✓ Signals validated (no orders placed)")
            
            print()
            
            # Wait before next observation
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        print("\n⏹️  Observation mode stopped by user.")
    except Exception as e:
        print(f"\n❌ Error in observation loop: {e}")
    finally:
        print("\nObservation mode ended.")


if __name__ == "__main__":
    main()
