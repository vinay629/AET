// BAET Dashboard - JavaScript Implementation
// Handles data loading, chart rendering, and real-time updates

class BAETDashboard {
    constructor() {
        this.refreshInterval = 30000; // 30 seconds
        this.lastRefresh = 0;
        this.charts = {};
        this.data = {
            portfolio: {},
            equity: [],
            trades: [],
            positions: [],
            logs: [],
            ohlcv: {},
            performance: {}
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
        });

        document.getElementById('timeframe-select').addEventListener('change', () => {
            this.loadOHLCVData();
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
                this.loadPortfolioData(),
                this.loadEquityData(),
                this.loadTradesData(),
                this.loadPositionsData(),
                this.loadLogsData(),
                this.loadPerformanceData(),
                this.loadOHLCVData()
            ]);

            this.updateUI();
            this.lastRefresh = Date.now();
        } catch (error) {
            console.error('Error refreshing data:', error);
        }
    }

    // Load status data
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

    // Load portfolio data
    async loadPortfolioData() {
        try {
            const response = await fetch('/api/portfolio');
            if (response.ok) {
                this.data.portfolio = await response.json();
            }
        } catch (error) {
            console.error('Error loading portfolio data:', error);
        }
    }

    // Load equity curve data
    async loadEquityData() {
        try {
            const response = await fetch('/api/equity');
            if (response.ok) {
                this.data.equity = await response.json();
                this.updateEquityChart();
            }
        } catch (error) {
            console.error('Error loading equity data:', error);
        }
    }

    // Load trades data
    async loadTradesData() {
        try {
            const response = await fetch('/api/trades');
            if (response.ok) {
                this.data.trades = await response.json();
                this.updateTradesTable();
            }
        } catch (error) {
            console.error('Error loading trades data:', error);
        }
    }

    // Load positions data
    async loadPositionsData() {
        try {
            const response = await fetch('/api/positions');
            if (response.ok) {
                this.data.positions = await response.json();
                this.updatePositionsTable();
            }
        } catch (error) {
            console.error('Error loading positions data:', error);
        }
    }

    // Load logs data
    async loadLogsData() {
        try {
            const response = await fetch('/api/logs');
            if (response.ok) {
                this.data.logs = await response.json();
                this.updateLogsDisplay();
            }
        } catch (error) {
            console.error('Error loading logs data:', error);
        }
    }

    // Load performance metrics
    async loadPerformanceData() {
        try {
            const response = await fetch('/api/performance');
            if (response.ok) {
                this.data.performance = await response.json();
                this.updatePerformanceMetrics();
            }
        } catch (error) {
            console.error('Error loading performance data:', error);
        }
    }

    // Load OHLCV data
    async loadOHLCVData() {
        const symbol = document.getElementById('symbol-select').value;
        const timeframe = document.getElementById('timeframe-select').value;

        try {
            const response = await fetch(`/api/ohlcv/${symbol}?timeframe=${timeframe}`);
            if (response.ok) {
                this.data.ohlcv[symbol] = await response.json();
                this.updateOHLCVChart();
            }
        } catch (error) {
            console.error('Error loading OHLCV data:', error);
        }
    }

    // Update UI elements
    updateUI() {
        this.updateStatusStrip();
        this.updateTopStrip();
        this.updatePortfolioOverview();
        this.updateAISignal();
    }

    // Update AI signal display
    updateAISignal() {
        const perf = this.data.performance;
        const signalEl = document.getElementById('ai-signal');
        if (!signalEl) return;

        const score = perf.ai_score || 0;
        let signal = 'NEUTRAL';
        let cls = '';

        if (score > 0.3) { signal = 'BULLISH'; cls = 'bullish'; }
        else if (score < -0.3) { signal = 'BEARISH'; cls = 'bearish'; }

        signalEl.textContent = signal;
        signalEl.className = 'status-value ' + cls;
    }

    // Update top status strip from status API
    updateStatusStrip() {
        const s = this.data.status;
        if (!s) return;

        const modeEl = document.getElementById('mode');
        const statusEl = document.getElementById('status');
        const equityEl = document.getElementById('equity');
        const dailyPnlEl = document.getElementById('daily-pnl');
        const positionsEl = document.getElementById('positions-count');
        const lastUpdateEl = document.getElementById('last-update');

        if (modeEl) {
            modeEl.textContent = (s.mode || 'UNKNOWN').toUpperCase();
            modeEl.className = 'status-value info';
        }
        if (statusEl) {
            statusEl.textContent = s.status || 'UNKNOWN';
            statusEl.className = 'status-value ' + (s.status === 'RUNNING' ? 'bullish' : s.status === 'WARNING' ? 'warning' : 'bearish');
        }
        if (equityEl) equityEl.textContent = this.formatCurrency(s.equity || 0);
        if (dailyPnlEl) {
            const pnl = s.daily_pnl || 0;
            dailyPnlEl.textContent = this.formatCurrency(pnl);
            dailyPnlEl.className = 'status-value ' + (pnl >= 0 ? 'bullish' : 'bearish');
        }
        if (positionsEl) positionsEl.textContent = s.positions_count || 0;
        if (lastUpdateEl) {
            lastUpdateEl.textContent = s.last_update
                ? new Date(s.last_update).toLocaleTimeString()
                : new Date().toLocaleTimeString();
        }
    }

    // Update top status strip (fallback from portfolio data)
    updateTopStrip() {
        const portfolio = this.data.portfolio;
        const equity = portfolio.total_value || 0;
        const cash = portfolio.cash || 0;
        const positions = portfolio.positions || {};
        const positionsCount = Object.keys(positions).length;

        document.getElementById('equity').textContent = this.formatCurrency(equity);
        document.getElementById('cash').textContent = this.formatCurrency(cash);
        document.getElementById('positions-count').textContent = positionsCount;
        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
    }

    // Update portfolio overview
    updatePortfolioOverview() {
        const portfolio = this.data.portfolio;
        const initialBalance = portfolio.initial_balance || 10000;
        const totalValue = portfolio.total_value || 0;
        const cash = portfolio.cash || 0;
        const positionsValue = totalValue - cash;
        const totalReturn = initialBalance > 0 ? (totalValue - initialBalance) / initialBalance : 0;

        document.getElementById('total-value').textContent = this.formatCurrency(totalValue);
        document.getElementById('positions-value').textContent = this.formatCurrency(positionsValue);
        document.getElementById('total-return').textContent = this.formatPercentage(totalReturn);
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

    // Update positions table
    updatePositionsTable() {
        const tbody = document.getElementById('positions-tbody');
        const positions = this.data.positions;

        if (Object.keys(positions).length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="no-data">No open positions</td></tr>';
            return;
        }

        tbody.innerHTML = Object.entries(positions).map(([symbol, pos]) => {
            const pnl = pos.pnl || 0;
            const pnlPercent = pos.pnl_percent || 0;
            const pnlClass = pnl >= 0 ? 'pnl-positive' : 'pnl-negative';

            return `
                <tr>
                    <td>${symbol}</td>
                    <td>${pos.units || 0}</td>
                    <td>${this.formatCurrency(pos.avg_price || 0)}</td>
                    <td>${this.formatCurrency(pos.current_price || 0)}</td>
                    <td>${this.formatCurrency(pos.market_value || 0)}</td>
                    <td class="${pnlClass}">${this.formatCurrency(pnl)}</td>
                    <td class="${pnlClass}">${this.formatPercentage(pnlPercent)}</td>
                </tr>
            `;
        }).join('');
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
            const timestamp = new Date(log.timestamp).toLocaleTimeString();
            const typeClass = log.type.toLowerCase().replace('_', '-');

            return `
                <div class="log-entry ${typeClass}">
                    <span class="log-time">[${timestamp}]</span>
                    <span class="log-type">[${log.type}]</span>
                    <span class="log-message">${log.message || JSON.stringify(log)}</span>
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
