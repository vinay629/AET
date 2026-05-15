"""Script to launch the BAET HTML/JS dashboard."""

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = PROJECT_ROOT / "src" / "baet" / "dashboard" / "web"
API_SERVER_PATH = PROJECT_ROOT / "src" / "baet" / "dashboard" / "web" / "api_server.py"
PORT = os.getenv("BAET_DASHBOARD_PORT", "8501")
URL = f"http://localhost:{PORT}"


def wait_for_server(url, timeout=15):
    """Poll /api/status until the server responds or timeout."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            urlopen(f"{url}/api/status", timeout=2)
            return True
        except (URLError, OSError):
            time.sleep(0.5)
    return False


def main():
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

    cmd = [sys.executable, str(API_SERVER_PATH),
           "--host", "localhost", "--port", PORT]

    # Start Flask in a background thread so we can open the browser after it's ready
    server_thread = threading.Thread(
        target=lambda: subprocess.run(cmd, cwd=str(DASHBOARD_DIR)),
        daemon=True,
    )
    server_thread.start()

    print("  Waiting for server to start...")
    if wait_for_server(URL):
        print("  Server ready! Opening dashboard...")
        webbrowser.open(URL)
    else:
        print("  Server did not start in time. Open manually:")
        print(f"  {URL}")

    # Keep main thread alive for Ctrl+C
    try:
        while server_thread.is_alive():
            server_thread.join(timeout=1.0)
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
