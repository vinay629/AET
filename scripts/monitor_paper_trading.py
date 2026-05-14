"""Monitor paper trading stability during M4.4 observation window."""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not installed. Process monitoring disabled.")
    print("Install with: pip install psutil")

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("Warning: requests not installed. Dashboard monitoring disabled.")
    print("Install with: pip install requests")


def check_process_running(script_name: str = "baet.paper.engine") -> dict:
    """Check if paper trading process is running."""
    if not HAS_PSUTIL:
        return {"status": "unknown", "message": "psutil not installed"}

    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmdline = proc.info["cmdline"]
            if cmdline and any(script_name in arg for arg in cmdline):
                runtime = datetime.now() - datetime.fromtimestamp(proc.info["create_time"])
                return {
                    "status": "running",
                    "pid": proc.info["pid"],
                    "runtime_hours": runtime.total_seconds() / 3600,
                    "runtime_str": str(runtime).split(".")[0],  # Remove microseconds
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return {"status": "not_running", "message": "Process not found"}


def check_log_freshness(log_dir: str = "logs/paper") -> dict:
    """Check if log files are being updated."""
    log_path = Path(log_dir)
    if not log_path.exists():
        return {"status": "error", "message": "Log directory not found"}

    log_files = list(log_path.glob("paper_trading_*.log"))
    if not log_files:
        return {"status": "error", "message": "No log files found"}

    # Check most recent log file
    latest = max(log_files, key=lambda f: f.stat().st_mtime)
    mtime = datetime.fromtimestamp(latest.stat().st_mtime)
    age_seconds = (datetime.now() - mtime).total_seconds()

    # Count lines (trades) in log file
    try:
        with open(latest, "r") as f:
            line_count = sum(1 for _ in f)
    except:
        line_count = -1

    status = "ok"
    if age_seconds > 300:  # 5 minutes
        status = "stale"
    if age_seconds > 1800:  # 30 minutes
        status = "critical"

    return {
        "status": status,
        "latest_log": str(latest.name),
        "last_update_seconds_ago": int(age_seconds),
        "last_update_minutes_ago": int(age_seconds / 60),
        "log_size_mb": round(latest.stat().st_size / (1024 * 1024), 2),
        "line_count": line_count,
    }


def check_dashboard_accessible(port: int = 8501) -> dict:
    """Check if Streamlit dashboard is accessible."""
    if not HAS_REQUESTS:
        return {"status": "unknown", "message": "requests not installed"}

    try:
        response = requests.get(f"http://localhost:{port}", timeout=5)
        return {
            "status": "ok" if response.status_code == 200 else "error",
            "status_code": response.status_code,
        }
    except requests.exceptions.ConnectionError:
        return {"status": "not_running", "message": "Cannot connect to dashboard"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_log_errors(log_dir: str = "logs/paper", last_n_minutes: int = 60) -> dict:
    """Check for errors in recent log entries."""
    log_path = Path(log_dir)
    if not log_path.exists():
        return {"error_count": -1, "warning_count": 0, "message": "Log directory not found"}

    log_files = list(log_path.glob("paper_trading_*.log"))
    if not log_files:
        return {"error_count": 0, "warning_count": 0, "message": "No log files"}

    latest = max(log_files, key=lambda f: f.stat().st_mtime)
    cutoff_time = datetime.now() - timedelta(minutes=last_n_minutes)

    error_count = 0
    warning_count = 0

    try:
        with open(latest, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    timestamp_str = entry.get("timestamp", "")
                    if not timestamp_str:
                        continue

                    # Parse timestamp (handle various formats)
                    try:
                        if "T" in timestamp_str:
                            entry_time = datetime.fromisoformat(
                                timestamp_str.replace("Z", "+00:00")
                            )
                        else:
                            continue

                        if entry_time < cutoff_time:
                            continue

                        level = entry.get("level", "").upper()
                        if level == "ERROR":
                            error_count += 1
                        elif level == "WARNING":
                            warning_count += 1
                    except:
                        pass
                except:
                    pass
    except Exception as e:
        return {"error_count": -1, "warning_count": 0, "message": str(e)}

    return {
        "error_count": error_count,
        "warning_count": warning_count,
        "time_window_minutes": last_n_minutes,
    }


def send_alert(message: str, level: str = "warning"):
    """Send alert (prints to console, can be extended with webhooks)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = "🚨" if level == "critical" else "⚠️" if level == "warning" else "ℹ️"
    print(f"\n{prefix} ALERT [{timestamp}]: {message}\n")


def print_status_report(
    process_status: dict, log_status: dict, dashboard_status: dict, error_status: dict
):
    """Print a formatted status report."""
    print("\n" + "=" * 60)
    print(f"Paper Trading Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Process status
    print("\n[Process]")
    if process_status["status"] == "running":
        print(f"  ✅ Running (PID: {process_status['pid']})")
        print(f"  ⏱️  Uptime: {process_status['runtime_str']}")
    else:
        print(f"  ❌ {process_status.get('message', 'Not running')}")

    # Log status
    print("\n[Log Files]")
    if log_status["status"] == "ok":
        print(f"  ✅ Fresh (updated {log_status['last_update_minutes_ago']} min ago)")
        print(f"  📄 Latest: {log_status['latest_log']}")
        print(f"  📊 Size: {log_status['log_size_mb']} MB, Lines: {log_status['line_count']}")
    elif log_status["status"] == "stale":
        print(f"  ⚠️  Stale (updated {log_status['last_update_minutes_ago']} min ago)")
    else:
        print(f"  ❌ {log_status.get('message', 'Error')}")

    # Dashboard status
    print("\n[Dashboard]")
    if dashboard_status["status"] == "ok":
        print("  ✅ Accessible")
    elif dashboard_status["status"] == "not_running":
        print("  ⚠️  Not running")
    else:
        print(f"  ❌ {dashboard_status.get('message', 'Error')}")

    # Error status
    print(f"\n[Errors (last {error_status.get('time_window_minutes', 60)} min)]")
    if error_status["error_count"] > 0:
        print(f"  ❌ Errors: {error_status['error_count']}")
    else:
        print("  ✅ No errors")
    if error_status["warning_count"] > 0:
        print(f"  ⚠️  Warnings: {error_status['warning_count']}")

    print("\n" + "=" * 60 + "\n")


def main():
    """Run monitoring loop."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor paper trading stability")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument(
        "--interval", type=int, default=300, help="Check interval in seconds (default: 300)"
    )
    parser.add_argument("--log-dir", default="logs/paper", help="Log directory")
    parser.add_argument("--dashboard-port", type=int, default=8501, help="Dashboard port")
    args = parser.parse_args()

    print("Starting paper trading monitor...")
    print(f"Log directory: {args.log_dir}")
    print(f"Check interval: {args.interval} seconds")
    if args.once:
        print("Mode: Single check")
    else:
        print("Mode: Continuous monitoring (Ctrl+C to stop)")

    try:
        while True:
            # Check all components
            process_status = check_process_running()
            log_status = check_log_freshness(args.log_dir)
            dashboard_status = check_dashboard_accessible(args.dashboard_port)
            error_status = check_log_errors(args.log_dir)

            # Print report
            print_status_report(process_status, log_status, dashboard_status, error_status)

            # Send alerts for issues
            if process_status["status"] != "running":
                send_alert("Paper trading process is not running!", "critical")

            if log_status["status"] == "critical":
                send_alert(
                    f"Log file is stale ({log_status['last_update_minutes_ago']} min old)!",
                    "critical",
                )
            elif log_status["status"] == "stale":
                send_alert(
                    f"Log file is getting stale ({log_status['last_update_minutes_ago']} min old)",
                    "warning",
                )

            if dashboard_status["status"] != "ok":
                send_alert("Dashboard is not accessible!", "warning")

            if error_status.get("error_count", 0) > 0:
                send_alert(
                    f"Found {error_status['error_count']} errors in last {error_status.get('time_window_minutes', 60)} minutes!",
                    "warning",
                )

            if args.once:
                break

            # Wait for next check
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
