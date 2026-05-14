"""Script to launch the BAET HTML/JS dashboard."""

import os
import subprocess
import sys
import threading
import time
import webbrowser
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


def open_browser_delayed(url: str, delay: float = 2.0):
    """Open the browser after a short delay to let the server start."""
    time.sleep(delay)
    webbrowser.open(url)


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

    # Open browser in background thread (waits 2s for server to start)
    browser_thread = threading.Thread(target=open_browser_delayed, args=(URL,), daemon=True)
    browser_thread.start()

    # Build the command for Flask API server
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
