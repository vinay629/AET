"""Script to launch the BAET Streamlit dashboard."""

import os
import subprocess
import sys
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Path to the Streamlit app
APP_PATH = PROJECT_ROOT / "src" / "baet" / "dashboard" / "app.py"

# Default port
PORT = os.getenv("BAET_DASHBOARD_PORT", "8501")


def main():
    """Launch the Streamlit dashboard."""
    if not APP_PATH.exists():
        print(f"Error: Dashboard app not found at {APP_PATH}")
        sys.exit(1)
    
    print("Starting BAET Dashboard...")
    print(f"App path: {APP_PATH}")
    print(f"Port: {PORT}")
    print(f"URL: http://localhost:{PORT}")
    print("\nPress Ctrl+C to stop\n")
    
    # Build the command
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(APP_PATH),
        "--server.port", PORT,
        "--server.address", "localhost",
        "--browser.serverAddress", "localhost",
    ]
    
    try:
        subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    except Exception as e:
        print(f"Error launching dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
