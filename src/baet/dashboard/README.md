# BAET Dashboard

Streamlit-based dashboard for monitoring paper trading activity in the BAET (Binance Adaptive Ensemble Trader) system.

## Features

The dashboard provides real-time monitoring of paper trading with the following features:

### Overview Tab
- **Portfolio Summary**: Current balance, equity, daily P&L, and return percentage
- **Performance Metrics**: Sharpe ratio, Sortino ratio, max drawdown, total return
- **Equity Chart**: Interactive equity curve visualization using Plotly

### Positions Tab
- Current open positions with entry price, current price, and P&L
- Position sizing information
- Real-time unrealized P&L tracking

### Trades Tab
- Recent trade history with entry/exit details
- Trade P&L and duration
- Color-coded profit/loss display

### Performance Tab
- Daily P&L summary with bar chart
- Detailed daily performance metrics
- Cumulative return visualization

### Logs Tab
- Raw paper trading log viewer
- Filter by event type (PORTFOLIO_UPDATE, TRADE, etc.)
- Most recent entries displayed first

## Installation

The dashboard requires Streamlit and Plotly. Install with:

```bash
pip install streamlit plotly
```

Or install all BAET dependencies:

```bash
pip install -e ".[dashboard]"
```

## Usage

### Quick Start

Use the provided launcher script:

```bash
python scripts/run_dashboard.py
```

Or run Streamlit directly:

```bash
streamlit run src/baet/dashboard/app.py
```

### Configuration

The dashboard reads from the `dashboard:` section in your configuration file (`config/base.yaml` by default):

```yaml
dashboard:
  log_dir: "logs/paper"
  refresh_interval: 60  # seconds
  default_initial_balance: 10000.0
  risk:
    max_position_size: 0.10
    max_portfolio_risk: 0.50
```

#### Configuration Options

- `log_dir`: Directory where paper trading logs are stored
- `refresh_interval`: How often the dashboard auto-refreshes (in seconds)
- `default_initial_balance`: Fallback balance if no log data is available
- `risk.max_position_size`: Maximum position size as fraction of portfolio (displayed in risk status)
- `risk.max_portfolio_risk`: Maximum portfolio risk exposure (displayed in risk status)

## Data Source

The dashboard reads from JSON-formatted paper trading log files:

```
logs/paper/paper_trading_YYYY-MM-DD.log
```

Each line in the log file should be a JSON object with at least a `timestamp` field. Supported event types:

- `PORTFOLIO_UPDATE`: Updates to portfolio state (balance, equity, positions)
- `TRADE`: Trade execution events (entry, exit, etc.)
- `ORDER_FILLED`: Order fill notifications
- `RISK_ACTION`: Risk management actions

### Log Format Example

```json
{"timestamp": "2024-01-15T10:30:00", "event": "PORTFOLIO_UPDATE", "balance": 10000.0, "equity": 10100.0, "positions": {...}}
{"timestamp": "2024-01-15T10:31:00", "event": "TRADE", "symbol": "BTCUSDT", "side": "BUY", "quantity": 0.1, "price": 45000.0, "pnl": 0.0}
```

## Dashboard Components

### Data Loading (`data_loader.py`)

- `find_latest_log_file()`: Locates the most recent log file
- `parse_log_file()`: Parses JSON log files into structured data
- `load_latest_state()`: Extracts the most recent portfolio state
- `load_recent_trades()`: Retrieves recent trade history
- `load_equity_curve()`: Builds equity curve from portfolio updates
- `calculate_daily_summary()`: Aggregates daily P&L
- `calculate_performance_metrics()`: Computes Sharpe, Sortino, max drawdown, etc.

### UI Components (`components.py`)

- `render_portfolio_overview()`: Portfolio metrics display
- `render_positions_table()`: Current positions grid
- `render_recent_trades()`: Recent trades table
- `render_performance_metrics()`: Key performance indicators
- `render_equity_chart()`: Interactive equity curve chart
- `render_daily_summary()`: Daily P&L visualization
- `render_risk_status()`: Risk exposure indicators
- `render_log_viewer()`: Raw log viewer with filtering

## Development

### Running Tests

```bash
python -m pytest tests/test_dashboard.py -v
```

### Project Structure

```
src/baet/dashboard/
├── __init__.py       # Module exports
├── app.py            # Main Streamlit application
├── components.py     # UI components
└── data_loader.py    # Data loading utilities
```

## Troubleshooting

### Dashboard won't start
- Ensure Streamlit is installed: `pip install streamlit`
- Check that log directory exists and contains log files
- Verify JSON format in log files (one JSON object per line)

### No data showing
- Verify `log_dir` in config points to correct location
- Check file permissions on log files
- Ensure log files have `.log` extension and match pattern `paper_trading_*.log`

### Import errors
- Make sure you're running from the project root directory
- Verify the BAET package is installed: `pip install -e .`
- Check that all dependencies are installed

## Next Steps

After setting up the dashboard, you can:

1. Start paper trading to generate log data (see `src/baet/paper/README.md`)
2. Monitor your paper trading activity in real-time
3. Analyze performance metrics and equity curves
4. Review trade history and position management

## Related Documentation

- [Paper Trading Module](../paper/README.md)
- [Configuration Guide](../../SETUP.md)
- [Main Project README](../../README.md)
