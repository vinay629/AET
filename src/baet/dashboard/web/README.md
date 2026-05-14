# BAET Web Dashboard

A modern, responsive HTML/JavaScript/CSS dashboard for BAET (Binance Adaptive Ensemble Trader) that replaces the Streamlit implementation.

## Features

- **Real-time monitoring** of paper trading activity
- **Interactive charts** using Chart.js
- **Responsive design** with dark terminal theme
- **REST API endpoints** for data retrieval
- **Auto-refresh** every 30 seconds
- **No external dependencies** except web browser

## Dashboard Components

### Top Status Strip
- Current mode (PAPER/LIVE)
- System status (RUNNING/WARNING/CRITICAL)
- Portfolio equity and daily P&L
- Number of open positions
- AI signal and risk status
- Last update timestamp

### Left Column
- **Market Chart**: Interactive OHLCV chart with technical indicators
- **Equity Curve**: Portfolio value over time

### Right Column
- **Portfolio Overview**: Key metrics (cash, total value, returns, positions value)
- **Performance Metrics**: Sharpe ratio, Sortino ratio, max drawdown, win rate, etc.
- **Current Positions**: Table with open positions and P&L
- **Recent Trades**: Latest trade executions
- **Recent Logs**: Real-time log entries

## API Endpoints

The dashboard provides REST API endpoints for data:

| Endpoint | Description |
|---|---|
| `/` | Main dashboard HTML |
| `/api/portfolio` | Current portfolio state |
| `/api/equity` | Equity curve data |
| `/api/trades` | Recent trades |
| `/api/positions` | Current positions |
| `/api/logs` | Recent logs |
| `/api/performance` | Performance metrics |
| `/api/ohlcv/<symbol>` | OHLCV data for symbol |
| `/api/daily-summary` | Daily summary |
| `/api/ai-signal` | Latest AI signal |
| `/api/status` | System status |
| `/api/symbols` | Available symbols and timeframes |

## Running the Dashboard

### Prerequisites

Install the required dependencies:

```bash
uv sync --all-extras
```

### Launch

```bash
# Using the provided script
uv run python scripts/run_dashboard.py

# Or run directly
uv run python src/baet/dashboard/web/api_server.py
```

The dashboard will be available at **http://localhost:8501**

### Configuration

The dashboard reads configuration from:

- `config/base.yaml` - Default settings
- `config/paper.yaml` - Paper trading mode (if active)
- Environment variables (via `.env` file)

Key configuration options:

```yaml
dashboard:
  enabled: true
  port: 8501
  theme: light
  auto_refresh: true
  refresh_interval_seconds: 30
  max_recent_trades: 50
  max_log_entries: 100
```

## Data Sources

The dashboard reads data from:

1. **Log files** in `logs/paper/paper_trading_YYYY-MM-DD.jsonl`
2. **Parquet storage** for historical market data
3. **Binance API** for real-time market data (fallback)

## File Structure

```
src/baet/dashboard/web/
├── index.html          # Main dashboard HTML
├── styles.css          # Dashboard styling
├── dashboard.js        # JavaScript functionality
├── api_server.py       # Flask API server
└── README.md           # This file
```

## Customization

### Styling

Edit `styles.css` to customize:
- Colors and themes
- Layout and spacing
- Chart styling
- Table formatting

### JavaScript

Edit `dashboard.js` to modify:
- Chart configurations
- Data loading logic
- UI update functions
- Auto-refresh behavior

### API Server

Edit `api_server.py` to:
- Add new endpoints
- Modify data processing
- Change caching behavior
- Add authentication

## Browser Compatibility

- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

## Performance

- **Auto-refresh**: 30 seconds (configurable)
- **Data caching**: 30 seconds (configurable)
- **Chart rendering**: Optimized for real-time updates
- **Memory usage**: Minimal, efficient data structures

## Troubleshooting

### Common Issues

**Dashboard not loading**
- Check that the API server is running
- Verify port 8501 is available
- Check browser console for errors

**No data displayed**
- Ensure paper trading logs exist in `logs/paper/`
- Check API server logs for errors
- Verify configuration files are valid

**Charts not updating**
- Check auto-refresh is enabled
- Verify data source is accessible
- Check browser console for JavaScript errors

### Debug Mode

Run the API server with debug mode:

```bash
uv run python src/baet/dashboard/web/api_server.py --debug
```

This will enable detailed logging and error messages.

## Migration from Streamlit

This dashboard replaces the previous Streamlit implementation with:

- **Better performance**: No Python overhead in browser
- **More responsive**: Real-time updates without page reloads
- **Customizable**: Full control over styling and behavior
- **Lightweight**: No heavy dependencies like Streamlit

The data format and API endpoints remain compatible with the original implementation.