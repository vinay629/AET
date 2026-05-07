"""Control functions for BAET paper trading dashboard.

Provides start/stop/emergency stop functionality and configuration management.
"""

from __future__ import annotations

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

from baet.config.loader import load_settings, CONFIG_DIR
from baet.config.models import Settings


# Process name to look for
PROCESS_KEYWORDS = ["baet.paper.engine", "start_observation.py", "start_paper_trading"]


def check_paper_trading_status() -> dict:
    """Check if paper trading process is running."""
    if not HAS_PSUTIL:
        return {"running": False, "pid": None, "uptime": None, "error": "psutil not installed"}
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any(keyword in ' '.join(cmdline) for keyword in PROCESS_KEYWORDS):
                uptime_seconds = None
                if proc.info['create_time']:
                    from datetime import datetime
                    uptime = datetime.now() - datetime.fromtimestamp(proc.info['create_time'])
                    uptime_seconds = uptime.total_seconds()
                
                return {
                    "running": True,
                    "pid": proc.info['pid'],
                    "uptime_seconds": uptime_seconds,
                    "uptime_str": str(uptime).split('.')[0] if 'uptime' in locals() else "Unknown",
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception:
            pass
    
    return {"running": False, "pid": None, "uptime_seconds": None, "uptime_str": None}


def start_paper_trading(config_mode: str = "paper") -> tuple[bool, str]:
    """Start paper trading process.
    
    Args:
        config_mode: Configuration mode to use (paper, live, etc.)
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Build command
        cmd = [
            sys.executable if 'sys' in globals() else "python",
            "-m", "baet.paper.engine",
            "--config", config_mode,
        ]
        
        # Start process
        if os.name == 'nt':  # Windows
            # Use CREATE_NEW_CONSOLE to run independently
            proc = subprocess.Popen(
                cmd,
                cwd=Path.cwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:  # Linux/Mac
            proc = subprocess.Popen(
                cmd,
                cwd=Path.cwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        
        return True, f"Paper trading started (PID: {proc.pid})"
    
    except Exception as e:
        return False, f"Failed to start: {str(e)}"


def stop_paper_trading() -> tuple[bool, str]:
    """Stop paper trading process gracefully.
    
    Returns:
        Tuple of (success, message)
    """
    status = check_paper_trading_status()
    
    if not status["running"]:
        return False, "Paper trading is not running"
    
    if not status["pid"]:
        return False, "Could not determine process PID"
    
    try:
        proc = psutil.Process(status["pid"])
        proc.terminate()
        
        # Wait for process to terminate (max 10 seconds)
        try:
            proc.wait(timeout=10)
            return True, "Paper trading stopped gracefully"
        except psutil.TimeoutExpired:
            # Force kill if still running
            proc.kill()
            return True, "Paper trading force-killed (timeout waiting for termination)"
    
    except psutil.NoSuchProcess:
        return True, "Process already stopped"
    except Exception as e:
        return False, f"Failed to stop: {str(e)}"


def emergency_stop() -> tuple[bool, str]:
    """Emergency stop - force kill paper trading process.
    
    Returns:
        Tuple of (success, message)
    """
    status = check_paper_trading_status()
    
    if not status["running"]:
        return False, "Paper trading is not running"
    
    if not status["pid"]:
        return False, "Could not determine process PID"
    
    try:
        proc = psutil.Process(status["pid"])
        
        # Log emergency stop
        try:
            from baet.paper.logging import PaperTradingLogger
            logger = PaperTradingLogger(log_dir="logs/paper")
            logger.log_engine_event("EMERGENCY_STOP", {
                "action": "force_kill",
                "pid": status["pid"],
                "source": "dashboard_control_panel",
            })
        except:
            pass
        
        # Force kill
        proc.kill()
        
        return True, "🚨 EMERGENCY STOP ACTIVATED - Process killed"
    
    except psutil.NoSuchProcess:
        return True, "Process already stopped"
    except Exception as e:
        return False, f"Emergency stop failed: {str(e)}"


def get_config() -> dict:
    """Load current configuration.
    
    Returns:
        Dictionary of current configuration
    """
    try:
        settings = load_settings("paper")
        return {
            "initial_balance": settings.paper.initial_balance,
            "loop_interval_seconds": settings.paper.loop_interval_seconds,
            "stop_on_error": settings.paper.stop_on_error,
            "max_consecutive_errors": settings.paper.max_consecutive_errors,
        }
    except Exception as e:
        if HAS_STREAMLIT:
            st.error(f"Failed to load config: {e}")
        return {}


def update_config(updates: dict) -> tuple[bool, str]:
    """Update configuration file with new values.
    
    Args:
        updates: Dictionary of config updates (e.g., {"paper.initial_balance": 15000})
        
    Returns:
        Tuple of (success, message)
    """
    try:
        import yaml
        
        # Load current config
        config_file = CONFIG_DIR / "paper.yaml"
        if not config_file.exists():
            return False, f"Config file not found: {config_file}"
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        # Apply updates (handle nested keys like "paper.initial_balance")
        for key, value in updates.items():
            parts = key.split('.')
            current = config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        
        # Save
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        return True, "Configuration updated successfully"
    
    except Exception as e:
        return False, f"Failed to update config: {str(e)}"


def render_control_panel():
    """Render the control panel in Streamlit sidebar."""
    if not HAS_STREAMLIT:
        print("Streamlit not available")
        return
    
    st.sidebar.title("🎮 Control Panel")
    
    # Status indicator
    status = check_paper_trading_status()
    
    if status.get("running"):
        st.sidebar.success("● Running")
        if status.get("uptime_str"):
            st.sidebar.caption(f"Uptime: {status['uptime_str']}")
    else:
        st.sidebar.error("● Stopped")
        if status.get("error"):
            st.sidebar.caption(f"Error: {status['error']}")
    
    st.sidebar.divider()
    
    # Control buttons
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("▶️ Start", 
                    disabled=status.get("running"),
                    use_container_width=True,
                    type="primary" if not status.get("running") else "secondary"):
            with st.spinner("Starting paper trading..."):
                success, msg = start_paper_trading()
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    
    with col2:
        if st.button("⏸️ Stop",
                    disabled=not status.get("running"),
                    use_container_width=True):
            with st.spinner("Stopping paper trading..."):
                success, msg = stop_paper_trading()
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    
    # Emergency stop
    st.sidebar.divider()
    if st.button("🚨 EMERGENCY STOP",
                 type="primary",
                 use_container_width=True,
                 disabled=not status.get("running")):
        # Confirmation
        confirm = st.sidebar.checkbox("I understand this will force-kill the process")
        if confirm:
            success, msg = emergency_stop()
            if success:
                st.sidebar.error(msg)
                st.rerun()
            else:
                st.sidebar.error(msg)
    
    st.sidebar.divider()
    
    # Configuration
    with st.sidebar.expander("⚙️ Settings"):
        config = get_config()
        
        if config:
            new_balance = st.number_input(
                "Initial Balance ($)",
                min_value=100.0,
                max_value=1000000.0,
                value=float(config.get("initial_balance", 10000.0)),
                step=1000.0,
            )
            
            new_interval = st.slider(
                "Loop Interval (seconds)",
                min_value=10,
                max_value=300,
                value=int(config.get("loop_interval_seconds", 60)),
                step=10,
            )
            
            new_stop_on_error = st.checkbox(
                "Stop on Error",
                value=bool(config.get("stop_on_error", False)),
            )
            
            if st.button("💾 Save Settings", use_container_width=True):
                updates = {
                    "paper.initial_balance": new_balance,
                    "paper.loop_interval_seconds": new_interval,
                    "paper.stop_on_error": new_stop_on_error,
                }
                success, msg = update_config(updates)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
        else:
            st.warning("Could not load configuration")


def render_status_bar():
    """Render a status bar at the top of the dashboard."""
    if not HAS_STREAMLIT:
        return
    
    status = check_paper_trading_status()
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if status.get("running"):
            st.success("● Running")
        else:
            st.error("● Stopped")
    
    with col2:
        if status.get("uptime_str"):
            st.caption(f"Uptime: {status['uptime_str']}")
    
    with col3:
        if status.get("running"):
            if st.button("🚨 Emergency Stop", type="primary"):
                success, msg = emergency_stop()
                if success:
                    st.error(msg)
                    st.rerun()
                else:
                    st.error(msg)
