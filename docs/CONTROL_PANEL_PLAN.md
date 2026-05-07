# Dashboard Control Panel Implementation Plan

## Objective
Add interactive control panel to the Streamlit dashboard for managing paper trading operations.

## Current State
- ✅ M4.3b Dashboard created (read-only monitoring)
- ✅ Tabs: Overview, Positions, Trades, Performance, Logs
- ❌ No way to START/STOP paper trading from dashboard
- ❌ No way to configure parameters from GUI
- ❌ No emergency stop button

## Proposed Control Panel Features

### 1. Trading Controls Section
Add to Overview tab or new "Controls" tab:

```python
def render_control_panel():
    """Render control panel for paper trading."""
    st.sidebar.title("🎮 Control Panel")
    
    # Status indicator
    status = check_paper_trading_status()
    if status["running"]:
        st.sidebar.success("● Running")
    else:
        st.sidebar.error("● Stopped")
    
    # Start/Stop buttons
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("▶️ Start", disabled=status["running"]):
            start_paper_trading()
            st.rerun()
    
    with col2:
        if st.button("⏸️ Stop", disabled=not status["running"]):
            stop_paper_trading()
            st.rerun()
    
    # Emergency stop
    if st.sidebar.button("🚨 EMERGENCY STOP", type="primary"):
        emergency_stop()
        st.rerun()
    
    # Configuration
    with st.sidebar.expander("⚙️ Settings"):
        initial_balance = st.number_input(
            "Initial Balance ($)",
            value=10000.0,
            step=1000.0
        )
        loop_interval = st.slider(
            "Loop Interval (seconds)",
            min_value=10,
            max_value=300,
            value=60
        )
        
        if st.button("💾 Save Config"):
            update_config({
                "paper.initial_balance": initial_balance,
                "paper.loop_interval_seconds": loop_interval
            })
            st.success("Config updated!")
```

### 2. Backend Control Functions

Create `src/baet/dashboard/control.py`:

```python
"""Control functions for paper trading dashboard."""

import subprocess
import psutil
from pathlib import Path
from typing import Optional

import streamlit as st

from baet.config.loader import load_settings
from baet.config.models import Settings


def check_paper_trading_status() -> dict:
    """Check if paper trading process is running."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('baet.paper.engine' in arg for arg in cmdline):
                return {
                    "running": True,
                    "pid": proc.info['pid'],
                    "uptime": get_uptime(proc.info['create_time']),
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return {"running": False, "pid": None, "uptime": None}


def start_paper_trading():
    """Start paper trading process."""
    try:
        # Start in background
        subprocess.Popen(
            ["python", "-m", "baet.paper.engine", "--config", "config/paper.yaml"],
            cwd=Path.cwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        st.success("Paper trading started!")
    except Exception as e:
        st.error(f"Failed to start: {e}")


def stop_paper_trading():
    """Stop paper trading process gracefully."""
    status = check_paper_trading_status()
    if status["pid"]:
        try:
            proc = psutil.Process(status["pid"])
            proc.terminate()
            st.success("Paper trading stopped!")
        except Exception as e:
            st.error(f"Failed to stop: {e}")


def emergency_stop():
    """Emergency stop - close all positions, stop trading."""
    status = check_paper_trading_status()
    if status["pid"]:
        try:
            proc = psutil.Process(status["pid"])
            proc.kill()  # Force kill
            
            # Log emergency stop
            from baet.paper.logging import PaperTradingLogger
            logger = PaperTradingLogger(log_dir="logs/paper")
            logger.log_engine_event("EMERGENCY_STOP", {
                "action": "force_kill",
                "pid": status["pid"],
            })
            
            st.warning("🚨 EMERGENCY STOP ACTIVATED!")
        except Exception as e:
            st.error(f"Emergency stop failed: {e}")


def update_config(updates: dict):
    """Update configuration file with new values."""
    try:
        from baet.config.loader import CONFIG_DIR
        import yaml
        
        # Load current config
        config_file = CONFIG_DIR / "paper.yaml"
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        # Apply updates
        for key, value in updates.items():
            parts = key.split('.')
            current = config
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = value
        
        # Save
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            
    except Exception as e:
        st.error(f"Failed to update config: {e}")


def get_uptime(start_time: float) -> str:
    """Format uptime from start time."""
    from datetime import datetime, timedelta
    uptime = datetime.now() - datetime.fromtimestamp(start_time)
    return str(uptime).split('.')[0]  # Remove microseconds
```

### 3. Integration with Dashboard

Update `src/baet/dashboard/app.py` to include control panel:

```python
# At top of app.py
try:
    from baet.dashboard import control
    HAS_CONTROL = True
except ImportError:
    HAS_CONTROL = False

# In main()
st.title("BAET Paper Trading Dashboard")

# Add control panel to sidebar
if HAS_CONTROL:
    control.render_control_panel()

# Continue with existing tabs...
```

### 4. Process Management

For reliable start/stop, create `scripts/paper_trading_manager.py`:

```python
"""Process manager for paper trading."""
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def main():
    import argparse
    from baet.dashboard.control import (
        check_paper_trading_status,
        start_paper_trading,
        stop_paper_trading,
        emergency_stop,
    )
    
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status", "emergency-stop"])
    args = parser.parse_args()
    
    if args.action == "start":
        start_paper_trading()
    elif args.action == "stop":
        stop_paper_trading()
    elif args.action == "emergency-stop":
        emergency_stop()
    elif args.action == "status":
        status = check_paper_trading_status()
        print(json.dumps(status, indent=2))

if __name__ == "__main__":
    main()
```

## Implementation Steps

1. **Create `src/baet/dashboard/control.py`**
   - Process management functions
   - Config update functions
   - Status checking

2. **Update `src/baet/dashboard/app.py`**
   - Import control module
   - Add control panel to sidebar
   - Handle button actions

3. **Create `scripts/paper_trading_manager.py`**
   - CLI interface for process management
   - Can be called from dashboard or command line

4. **Update `src/baet/dashboard/__init__.py`**
   - Export control module

5. **Add Tests**
   - Test control functions
   - Test process management
   - Test config updates

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/baet/dashboard/control.py` | CREATE | Control panel backend |
| `src/baet/dashboard/app.py` | MODIFY | Add control panel UI |
| `src/baet/dashboard/__init__.py` | MODIFY | Export control module |
| `scripts/paper_trading_manager.py` | CREATE | CLI process manager |
| `tests/test_control_panel.py` | CREATE | Tests for control functions |

## Acceptance Criteria

- [ ] Can START paper trading from dashboard
- [ ] Can STOP paper trading from dashboard
- [ ] Emergency STOP button works
- [ ] Status indicator shows running/stopped
- [ ] Can update config from dashboard (initial balance, loop interval)
- [ ] Process manager CLI works (`python scripts/paper_trading_manager.py status`)
- [ ] All control functions have tests

## Integration with M4.4 Observation

If implemented during M4.4 observation:
- Makes monitoring easier (start/stop from dashboard)
- Adds emergency stop capability
- Should be added AFTER observation starts (don't disrupt validation)

## Priority

**Medium** - Nice to have for M4.4, but not required.
**High** - Should have for M5.1a (Live Readiness Controls).

## Next Steps

1. Implement `control.py` module
2. Integrate with dashboard
3. Add tests
4. Update documentation
5. Commit and push

---

**Recommendation:** Implement this as part of **M5.1a: Live Readiness Controls** since it's a control/ safety feature needed before live trading.
