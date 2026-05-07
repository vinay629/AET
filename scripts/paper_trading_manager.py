"""CLI manager for paper trading process.

Usage:
    python scripts/paper_trading_manager.py start
    python scripts/paper_trading_manager.py stop
    python scripts/paper_trading_manager.py status
    python scripts/paper_trading_manager.py emergency-stop
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def main():
    """Main entry point for paper trading manager."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Manage BAET paper trading process"
    )
    parser.add_argument(
        "action",
        choices=["start", "stop", "status", "emergency-stop"],
        help="Action to perform"
    )
    parser.add_argument(
        "--config",
        default="paper",
        help="Configuration mode (default: paper)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output status as JSON"
    )
    
    args = parser.parse_args()
    
    # Import control functions
    try:
        from baet.dashboard.control import (
            check_paper_trading_status,
            start_paper_trading,
            stop_paper_trading,
            emergency_stop,
        )
    except ImportError as e:
        print(f"Error: Could not import control module: {e}")
        print("Make sure BAET is installed: pip install -e .")
        sys.exit(1)
    
    # Execute action
    if args.action == "start":
        success, msg = start_paper_trading(config_mode=args.config)
        print(msg)
        sys.exit(0 if success else 1)
    
    elif args.action == "stop":
        success, msg = stop_paper_trading()
        print(msg)
        sys.exit(0 if success else 1)
    
    elif args.action == "emergency-stop":
        success, msg = emergency_stop()
        print(msg)
        sys.exit(0 if success else 1)
    
    elif args.action == "status":
        status = check_paper_trading_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print("Paper Trading Status")
            print("=" * 40)
            if status.get("running"):
                print(f"Status: ● RUNNING")
                print(f"PID: {status.get('pid', 'Unknown')}")
                print(f"Uptime: {status.get('uptime_str', 'Unknown')}")
            else:
                print("Status: ● STOPPED")
                if status.get("error"):
                    print(f"Error: {status['error']}")
        sys.exit(0)


if __name__ == "__main__":
    main()
