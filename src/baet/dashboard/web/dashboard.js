// BAET Dashboard - JavaScript Implementation
// Handles data loading, chart rendering, and real-time updates

class BAETDashboard {
    constructor() {
        this.refreshInterval = 10000; // 10 seconds
        this.lastRefresh = 0;
        this.charts = {};
        this.data = {
            portfolio: {},
            equity: [],
            trades: [],
            positions: [],
            logs: [],
            ohlcv: {},
            performance: {},
            engine: null,
            marketSummary: null,
            binanceTrades: [],
            tickers: [],
        };

        this.initializeCharts();
        this.startAutoRefresh();
        this.bindEvents();
    }

    // Initialize Chart.js charts
    initializeCharts() {
        const gridColor = '#1e2d3d';
        const tickColor = '#556677';

        // OHLCV Candlestick Chart
        const ohlcvCtx = document.getElementById('ohlcv-chart').getContext('2d');
        this.charts.ohlcv = new Chart(ohlcvCtx, {
            type: 'candlestick',
            data: {
                datasets: [{
                    label: 'OHLCV',
                    data: [],
                    color: {
                        up: '#22c55e',
                        down: '#ef4444',
                        unchanged: '#556677'
                    },
                    borderColor: {
                        up: '#22c55e',
                        down: '#ef4444',
                        unchanged: '#556677'
                    }
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#151d28',
                        titleColor: '#e8edf2',
                        bodyColor: '#8899aa',
                        borderColor: '#1e2d3d',
                        borderWidth: 1,
                        callbacks: {
                            label: (ctx) => {
                                const d = ctx.raw;
                                return [
                                    `O: ${d.o?.toLocaleString()}`,
                                    `H: ${d.h?.toLocaleString()}`,
                                    `L: ${d.l?.toLocaleString()}`,
                                    `C: ${d.c?.toLocaleString()}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'hour' },
                        grid: { color: gridColor },
                        ticks: { color: tickColor, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }
                    },
                    y: {
                        position: 'right',
                        grid: { color: gridColor },
                        ticks: { color: tickColor, callback: (v) => v.toLocaleString() }
                    }
                }
            }
        });

        // Equity Curve Chart
        const equityCtx = document.getElementById('equity-chart').getContext('2d');
        this.charts.equity = new Chart(equityCtx, {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Equity',
                    data: [],
                    borderColor: '#22c55e',
                    backgroundColor: 'rgba(34, 197, 94, 0.08)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHitRadius: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#151d28',
                        titleColor: '#e8edf2',
                        bodyColor: '#8899aa',
                        borderColor: '#1e2d3d',
                        borderWidth: 1,
                        callbacks: {
                            label: (ctx) => `$${ctx.parsed.y?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'hour' },
                        grid: { color: gridColor },
                        ticks: { color: tickColor, maxRotation: 0, autoSkip: true, maxTicksLimit: 6 }
                    },
                    y: {
                        position: 'right',
                        grid: { color: gridColor },
                        ticks: { color: tickColor, callback: (v) => '$' + v.toLocaleString() }
                    }
                }
            }
        });
    }

    // Bind UI events
    bindEvents() {
        document.getElementById('symbol-select').addEventListener('change', () => {
            this.loadOHLCVData();
            this.loadBinanceTrades();
            const sym = document.getElementById('symbol-select').value;
            const label = document.getElementById('live-trade-symbol');
            if (label) label.textContent = sym;
            // Sync order panel symbol
            const orderSym = document.getElementById('order-symbol');
            if (orderSym) orderSym.value = sym;
        });

        document.getElementById('timeframe-select').addEventListener('change', () => {
            this.loadOHLCVData();
        });

        // Sync order symbol back to chart symbol
        document.getElementById('order-symbol')?.addEventListener('change', () => {
            const orderSym = document.getElementById('order-symbol').value;
            const chartSym = document.getElementById('symbol-select');
            if (chartSym && chartSym.value !== orderSym) {
                chartSym.value = orderSym;
                this.loadOHLCVData();
                this.loadBinanceTrades();
            }
        });
    }

    // Start auto-refresh
    startAutoRefresh() {
        setInterval(() => {
            this.refreshData();
        }, this.refreshInterval);
    }

    // Main data refresh method
    async refreshData() {
        try {
            await Promise.all([
                this.loadStatusData(),
                this.loadOHLCVData(),
                this.loadMarketSummary(),
                this.loadBinanceTrades(),
                this.loadEngineStatus(),
                this.loadEquityData(),
                this.loadTrades(),
                this.loadLogs(),
                this.loadPerformance(),
            ]);

            this.updateUI();
            this.lastRefresh = Date.now();
        } catch (error) {
            console.error('Error refreshing data:', error);
        }
    }

    // Load status data (includes live tickers)
    async loadStatusData() {
        try {
            const response = await fetch('/api/status');
            if (response.ok) {
                this.data.status = await response.json();
                this.updateStatusStrip();
            }
        } catch (error) {
            console.error('Error loading status data:', error);
        }
    }

    // Load OHLCV data from Binance
    async loadOHLCVData() {
        const symbol = document.getElementById('symbol-select').value;
        const timeframe = document.getElementById('timeframe-select').value;

        try {
            const response = await fetch(`/api/ohlcv/${symbol}?timeframe=${timeframe}&limit=500`);
            if (response.ok) {
                this.data.ohlcv[symbol] = await response.json();
                this.updateOHLCVChart();
            }
        } catch (error) {
            console.error('Error loading OHLCV data:', error);
        }
    }

    // Load market summary (all tickers)
    async loadMarketSummary() {
        try {
            const response = await fetch('/api/market-summary');
            if (response.ok) {
                this.data.marketSummary = await response.json();
                this.updateMarketSummary();
            }
        } catch (error) {
            console.error('Error loading market summary:', error);
        }
    }

    // Load recent trades from Binance
    async loadBinanceTrades() {
        const symbol = document.getElementById('symbol-select').value;
        try {
            const response = await fetch(`/api/binance-trades/${symbol}?limit=50`);
            if (response.ok) {
                this.data.binanceTrades = await response.json();
                this.updateBinanceTradesTable();
            }
        } catch (error) {
            console.error('Error loading binance trades:', error);
        }
    }

    // Load equity curve data
    async loadEquityData() {
        try {
            const response = await fetch('/api/equity');
            if (response.ok) {
                const result = await response.json();
                this.data.equity = result.equity || [];
            }
        } catch (error) {
            console.error('Error loading equity data:', error);
        }
    }

    // Load trades data
    async loadTrades() {
        try {
            const response = await fetch('/api/trades');
            if (response.ok) {
                this.data.trades = await response.json();
            }
        } catch (error) {
            console.error('Error loading trades data:', error);
        }
    }

    // Load logs data
    async loadLogs() {
        try {
            const response = await fetch('/api/logs?limit=50');
            if (response.ok) {
                this.data.logs = await response.json();
            }
        } catch (error) {
            console.error('Error loading logs data:', error);
        }
    }

    // Load performance metrics
    async loadPerformance() {
        try {
            const response = await fetch('/api/performance');
            if (response.ok) {
                this.data.performance = await response.json();
            }
        } catch (error) {
            console.error('Error loading performance data:', error);
        }
    }

    // Update market summary display
    updateMarketSummary() {
        const summary = this.data.marketSummary;
        if (!summary || !summary.tickers) return;

        summary.tickers.forEach(t => {
            const priceEl = document.getElementById(`price-${t.symbol}`);
            const changeEl = document.getElementById(`change-${t.symbol}`);
            if (priceEl) {
                priceEl.textContent = '$' + t.last_price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            }
            if (changeEl) {
                const sign = t.price_change_pct >= 0 ? '+' : '';
                changeEl.textContent = sign + t.price_change_pct.toFixed(2) + '%';
                changeEl.style.color = t.price_change_pct >= 0 ? 'var(--green)' : 'var(--red)';
            }
        });
    }

    // Update Binance trades table
    updateBinanceTradesTable() {
        const trades = this.data.binanceTrades || [];
        const container = document.getElementById('binance-trades-content');
        if (!container) return;

        if (trades.length === 0) {
            container.innerHTML = '<div class="no-data">No recent trades</div>';
            return;
        }

        container.innerHTML = trades.slice(0, 20).map(t => {
            const sideClass = t.side === 'BUY' ? 'pnl-positive' : 'pnl-negative';
            const time = new Date(t.time).toLocaleTimeString();
            return `<div class="log-entry" style="justify-content:space-between; gap:8px;">
                <span class="log-time" style="flex-shrink:0">${time}</span>
                <span class="${sideClass}" style="font-weight:700; flex-shrink:0">${t.side}</span>
                <span style="flex-shrink:0">$${t.price.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</span>
                <span style="color:var(--text-muted)">${t.qty.toFixed(6)}</span>
            </div>`;
        }).join('');
    }

    // Update UI elements
    updateUI() {
        this.updateStatusStrip();
        this.updateEngineDisplay();
        this.updatePortfolioOverview();
        this.updatePositionsDisplay();
        this.updateEquityChart();
        this.updateTradesTable();
        this.updateLogsDisplay();
        this.updatePerformanceMetrics();
    }

    // Update top status strip from status API (includes live tickers)
    updateStatusStrip() {
        const s = this.data.status;
        if (!s) return;

        const lastUpdateEl = document.getElementById('last-update');
        if (lastUpdateEl) {
            lastUpdateEl.textContent = s.last_update
                ? new Date(s.last_update).toLocaleTimeString()
                : new Date().toLocaleTimeString();
        }

        // Update live ticker prices from status response
        if (s.tickers && Array.isArray(s.tickers)) {
            s.tickers.forEach(t => {
                const priceEl = document.getElementById(`price-${t.symbol}`);
                const changeEl = document.getElementById(`change-${t.symbol}`);
                if (priceEl) {
                    priceEl.textContent = '$' + t.last_price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                }
                if (changeEl) {
                    const sign = t.price_change_pct >= 0 ? '+' : '';
                    changeEl.textContent = sign + t.price_change_pct.toFixed(2) + '%';
                    changeEl.style.color = t.price_change_pct >= 0 ? 'var(--green)' : 'var(--red)';
                }
            });
        }
    }

    // Engine control methods
    onModeChange() {
        const mode = document.getElementById('trading-mode-select').value;
        const badge = document.getElementById('order-mode-badge');
        if (badge) {
            badge.textContent = mode.toUpperCase();
            badge.className = mode === 'paper' ? 'badge badge-paper' : 'badge badge-live';
        }
    }

    async startEngine() {
        const mode = document.getElementById('trading-mode-select').value;
        try {
            const response = await fetch('/api/engine/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mode})
            });
            const data = await response.json();
            if (data.status === 'started') {
                document.getElementById('btn-start').disabled = true;
                document.getElementById('btn-stop').disabled = false;
                const engEl = document.getElementById('engine-status');
                engEl.textContent = 'RUNNING';
                engEl.className = 'status-value bullish';
                this.onModeChange();
            } else {
                alert('Failed to start: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error starting engine:', error);
            alert('Error starting engine: ' + error.message);
        }
    }

    async stopEngine() {
        try {
            const response = await fetch('/api/engine/stop', {method: 'POST'});
            const data = await response.json();
            if (data.status === 'stopped') {
                document.getElementById('btn-start').disabled = false;
                document.getElementById('btn-stop').disabled = true;
                const engEl = document.getElementById('engine-status');
                engEl.textContent = 'STOPPED';
                engEl.className = 'status-value';
            }
        } catch (error) {
            console.error('Error stopping engine:', error);
        }
    }

    async placeOrder(side) {
        const symbol = document.getElementById('order-symbol').value;
        const qty = parseFloat(document.getElementById('order-qty').value);
        const resultEl = document.getElementById('order-result');

        if (!qty || qty <= 0) {
            resultEl.textContent = '❌ Invalid quantity';
            resultEl.style.color = 'var(--red)';
            return;
        }

        resultEl.textContent = '⏳ Placing order...';
        resultEl.style.color = 'var(--text-muted)';

        try {
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol, side, qty})
            });
            const data = await response.json();
            if (data.status === 'filled') {
                resultEl.textContent = `✅ ${side} ${qty} ${symbol} filled (${data.mode})`;
                resultEl.style.color = 'var(--green)';
            } else {
                resultEl.textContent = `❌ ${data.error || 'Order failed'}`;
                resultEl.style.color = 'var(--red)';
            }
        } catch (error) {
            resultEl.textContent = `❌ ${error.message}`;
            resultEl.style.color = 'var(--red)';
        }
    }

    async loadEngineStatus() {
        try {
            const response = await fetch('/api/engine/status');
            if (response.ok) {
                this.data.engine = await response.json();
            }
        } catch (error) {
            console.error('Error loading engine status:', error);
        }
    }

    updateEngineDisplay() {
        const eng = this.data.engine;
        if (!eng) return;

        const statusEl = document.getElementById('engine-status');
        const startBtn = document.getElementById('btn-start');
        const stopBtn = document.getElementById('btn-stop');

        if (eng.running) {
            statusEl.textContent = '● ' + (eng.mode || 'UNKNOWN').toUpperCase();
            statusEl.className = 'status-value ' + (eng.mode === 'live' ? 'bearish' : 'bullish');
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            statusEl.textContent = 'STOPPED';
            statusEl.className = 'status-value';
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }

        // Update equity/pnl from engine portfolio
        if (eng.portfolio) {
            const p = eng.portfolio;
            const equity = p.total_value || 0;
            const pnl = p.daily_pnl || 0;
            document.getElementById('equity').textContent = this.formatCurrency(equity);
            const pnlEl = document.getElementById('daily-pnl');
            pnlEl.textContent = (pnl >= 0 ? '+' : '') + this.formatCurrency(pnl);
            pnlEl.className = 'status-value ' + (pnl >= 0 ? 'bullish' : 'bearish');
        }
    }

    updatePositionsDisplay() {
        const eng = this.data.engine;
        const container = document.getElementById('positions-content');
        const badge = document.getElementById('positions-count-badge');
        if (!container) return;

        const positions = (eng && eng.positions) ? eng.positions : [];

        if (badge) badge.textContent = positions.length + ' open';

        if (positions.length === 0) {
            container.innerHTML = '<div class="no-data" style="padding:10px;">No open positions</div>';
            return;
        }

        container.innerHTML = positions.map(pos => {
            const pnl = pos.current_price && pos.avg_price && pos.units
                ? (pos.current_price - pos.avg_price) * pos.units : 0;
            const pnlClass = pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
            return `<div class="log-entry" style="justify-content:space-between; gap:8px;">
                <span style="font-weight:700; flex-shrink:0">${pos.symbol}</span>
                <span style="color:var(--text-muted); flex-shrink:0">${pos.units?.toFixed(6) || 0}</span>
                <span style="flex-shrink:0">$${pos.avg_price?.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}) || 0}</span>
                <span class="${pnlClass}" style="flex-shrink:0">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</span>
            </div>`;
        }).join('');
    }

    // Update portfolio overview
    updatePortfolioOverview() {
        const eng = this.data.engine;
        const s = this.data.status || {};
        const initialBalance = (eng && eng.portfolio && eng.portfolio.initial_balance)
            || s.initial_balance || 10000;
        const totalValue = (eng && eng.portfolio && eng.portfolio.total_value) || 0;
        const positionsValue = totalValue;
        const totalReturn = initialBalance > 0 ? (totalValue - initialBalance) / initialBalance : 0;

        const totalReturnEl = document.getElementById('total-return');
        document.getElementById('total-value').textContent = this.formatCurrency(totalValue);
        document.getElementById('positions-value').textContent = this.formatCurrency(positionsValue);
        if (totalReturnEl) {
            totalReturnEl.textContent = (totalReturn >= 0 ? '+' : '') + (totalReturn * 100).toFixed(2) + '%';
            totalReturnEl.style.color = totalReturn >= 0 ? 'var(--green)' : 'var(--red)';
        }
    }

    // Update OHLCV chart
    updateOHLCVChart() {
        const symbol = document.getElementById('symbol-select').value;
        const data = this.data.ohlcv[symbol] || [];

        if (data.length === 0) return;

        const candlestickData = data.map(item => ({
            x: new Date(item.timestamp).getTime(),
            o: item.open,
            h: item.high,
            l: item.low,
            c: item.close
        }));

        this.charts.ohlcv.data.datasets[0].label = symbol;
        this.charts.ohlcv.data.datasets[0].data = candlestickData;
        this.charts.ohlcv.update('none');
    }

    // Update equity chart
    updateEquityChart() {
        const data = this.data.equity;

        if (data.length === 0) return;

        this.charts.equity.data.datasets[0].data = data.map(item => ({
            x: new Date(item.timestamp).getTime(),
            y: item.total_value
        }));
        this.charts.equity.update('none');
    }

        // Update trades table
    updateTradesTable() {
        const tbody = document.getElementById('trades-tbody');
        const trades = this.data.trades;

        if (trades.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="no-data">No recent trades</td></tr>';
            return;
        }

        tbody.innerHTML = trades.slice(-10).reverse().map(trade => {
            const actionClass = trade.action === 'BUY' ? 'pnl-positive' : 'pnl-negative';
            const actionIcon = trade.action === 'BUY' ? '🟢' : '🔴';

            return `
                <tr>
                    <td>${new Date(trade.timestamp).toLocaleTimeString()}</td>
                    <td class="${actionClass}">${actionIcon} ${trade.action}</td>
                    <td>${trade.symbol}</td>
                    <td>${this.formatCurrency(trade.cash_after || 0)}</td>
                    <td>${this.formatCurrency(trade.total_value_after || 0)}</td>
                </tr>
            `;
        }).join('');
    }

    // Update logs display
    updateLogsDisplay() {
        const logsContainer = document.getElementById('logs-content');
        const logs = this.data.logs.slice(-20); // Show last 20 entries

        if (logs.length === 0) {
            logsContainer.innerHTML = '<div class="log-entry">No logs available</div>';
            return;
        }

        logsContainer.innerHTML = logs.map(log => {
            const ts = log.timestamp ? new Date(log.timestamp) : null;
            const timestamp = ts && !isNaN(ts.getTime()) ? ts.toLocaleTimeString() : '';
            const typeClass = (log.type || '').toLowerCase().replace('_', '-');
            const message = log.message || (log.type !== 'LOG_ENTRY' ? JSON.stringify(log) : '');

            return `
                <div class="log-entry ${typeClass}">
                    <span class="log-time">[${timestamp}]</span>
                    <span class="log-type">[${log.type || 'LOG'}]</span>
                    <span class="log-message">${message}</span>
                </div>
            `;
        }).join('');
    }

    // Update performance metrics
    updatePerformanceMetrics() {
        const perf = this.data.performance;
        const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
        const setMetric = (id, val, isPct) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.textContent = isPct ? this.formatPercentage(val) : (val?.toFixed(2) || '0.00');
            el.style.color = val > 0 ? 'var(--green)' : val < 0 ? 'var(--red)' : '';
        };

        setMetric('sharpe-ratio', perf.sharpe_ratio || 0, false);
        setMetric('sortino-ratio', perf.sortino_ratio || 0, false);
        setText('max-drawdown', this.formatPercentage(Math.abs(perf.max_drawdown || 0)));
        document.getElementById('max-drawdown').style.color = 'var(--red)';
        setMetric('win-rate', perf.win_rate || 0, true);
        setMetric('annual-return', perf.annualized_return || 0, true);
        setText('volatility', this.formatPercentage(perf.volatility || 0));
        setText('total-trades', perf.trade_count || 0);
        setMetric('ai-score', perf.ai_score || 0, false);
    }

    // Utility methods
    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value || 0);
    }

    formatPercentage(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'percent',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value || 0);
    }

    formatTimestamp(timestamp) {
        return new Date(timestamp).toLocaleString();
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new BAETDashboard();
    dashboard.refreshData();
});
