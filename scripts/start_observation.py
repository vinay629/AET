"""Start paper trading observation window with simulation mode.

This script starts the paper trading engine with simulated market data
for the M4.4 observation period (7-14 days).

Usage:
    python scripts/start_observation.py
    
Or with auto-restart (recommended):
    scripts\start_paper_trading.bat
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def main():
    """Start paper trading with simulation for observation."""
    print("=" * 60)
    print("BAET Paper Trading - M4.4 Observation Window")
    print("=" * 60)
    print()
    
    try:
        from baet.config.loader import load_settings
        from baet.paper.engine import PaperTradingEngine
        from baet.paper.simulation import patch_engine_for_simulation
        
        # Load settings
        print("Loading configuration...")
        settings = load_settings("paper")
        print(f"  Mode: {settings.app.mode}")
        print(f"  Initial Balance: ${settings.paper.initial_balance}")
        print()
        
        # Create engine
        print("Initializing PaperTradingEngine...")
        engine = PaperTradingEngine(config=settings)
        print("  ✓ Engine created")
        
        # Patch with simulation mode
        print("Enabling simulation mode for observation...")
        engine = patch_engine_for_simulation(engine)
        print("  ✓ Simulation mode active")
        print()
        
        # Print observation info
        print("=" * 60)
        print("OBSERVATION WINDOW STARTED")
        print("=" * 60)
        print(f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Handle logging directory
        log_dir = "logs/paper"  # default
        if hasattr(settings.paper, 'logging') and isinstance(settings.paper.logging, dict):
            log_dir = settings.paper.logging.get('directory', log_dir)
        elif hasattr(settings.paper, 'logging') and hasattr(settings.paper.logging, 'directory'):
            log_dir = settings.paper.logging.directory
            
        print(f"Log Directory: {log_dir}")
        print(f"Loop Interval: {settings.paper.loop_interval_seconds} seconds")
        print()
        print("Monitoring Options:")
        print("  1. Dashboard: python scripts/run_dashboard.py")
        print("  2. Monitor: python scripts/monitor_paper_trading.py")
        print("  3. Logs: Check logs/paper/ directory")
        print()
        print("Daily Checklist: docs/M4.4_DAILY_CHECKLIST.md")
        print("Observation Log: docs/M4.4_OBSERVATION_LOG.md")
        print("=" * 60)
        print()
        
        # Start the engine (this runs forever until stopped)
        print("Starting paper trading engine...")
        print("(Press Ctrl+C to stop)")
        print()
        
        engine.start()
        
    except KeyboardInterrupt:
        print()
        print("=" * 60)
        print("Paper trading stopped by user.")
        print("=" * 60)
        sys.exit(0)
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"ERROR: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
