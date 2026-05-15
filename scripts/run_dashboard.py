"""Script to launch the BAET HTML/JS dashboard."""

import os
import subprocess
import sys
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Path to the HTML dashboard
DASHBOARD_DIR = PROJECT_ROOT / "src" / "baet" / "dashboard" / "web"

# Path to the API server
API_SERVER_PATH = PROJECT_ROOT / "src" / "baet" / "dashboard" / "web" / "api_server.py"

# Default port
PORT = os.getenv("BAET_DASHBOARD_PORT", "8501")
URL = f"http://localhost:{PORT}"


def main():
    """Launch the HTML/JS dashboard with Flask API server."""
    if not DASHBOARD_DIR.exists():
        print(f"Error: Dashboard directory not found at {DASHBOARD_DIR}")
        sys.exit(1)

    if not API_SERVER_PATH.exists():
        print(f"Error: API server not found at {API_SERVER_PATH}")
        sys.exit(1)

    print("=" * 50)
    print("  BAET Dashboard - Binance Adaptive Ensemble Trader")
    print("=" * 50)
    print(f"  URL: {URL}")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    print()

    # Build the command for Flask API server (no debug mode to prevent double browser open)
    cmd = [
        sys.executable,
        str(API_SERVER_PATH),
        "--host",
        "localhost",
        "--port",
        PORT,
    ]

    try:
        # Change to the dashboard directory and run the Flask server
        subprocess.run(cmd, cwd=str(DASHBOARD_DIR))
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    except Exception as e:
        print(f"Error launching dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
