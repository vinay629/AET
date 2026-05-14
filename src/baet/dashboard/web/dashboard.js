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
        // OHLCV Chart
        const ohlcvCtx = document.getElementById('ohlcv-chart').getContext('2d');
        this.charts.ohlcv = new Chart(ohlcvCtx, {
            type: 'candlestick',
            data: {
                datasets: [{
                    label: 'BTCUSDT',
                    data: [],
                    borderColor: '#22c55e',
                    backgroundColor: '#22c55e'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'hour'
                        },
                        grid: {
                            color: '#233041'
                        },
                        ticks: {
                            color: '#8ea0b5'
                        }
                    },
                    y: {
                        grid: {
                            color: '#233041'
                        },
                        ticks: {
                            color: '#8ea0b5'
                        }
                    }
                }
            }
        });

        // Equity Chart
        const equityCtx = document.getElementById('equity-chart').getContext('2d');
        this.charts.equity = new Chart(equityCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Equity',
                    data: [],
                    borderColor: '#22c55e',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'hour'
                        },
                        grid: {
                            color: '#233041'
                        },
                        ticks: {
                            color: '#8ea0b5'
                        }
                    },
                    y: {
                        grid: {
                            color: '#233041'
                        },
                        ticks: {
                            color: '#8ea0b5'
                        }
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
        // Update top status strip
        this.updateTopStrip();
        
        // Update portfolio overview
        this.updatePortfolioOverview();
    }

    // Update top status strip
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
        const totalReturn = initialBalance > 0 ? ((totalValue - initialBalance) / initialBalance) * 100 : 0;
        
        document.getElementById('total-value').textContent = this.formatCurrency(totalValue);
        document.getElementById('positions-value').textContent = this.formatCurrency(positionsValue);
        document.getElementById('total-return').textContent = this.formatPercentage(totalReturn);
    }

    // Update OHLCV chart
    updateOHLCVChart() {
        const symbol = document.getElementById('symbol-select').value;
        const data = this.data.ohlcv[symbol] || [];
        
        if (data.length === 0) return;
        
        // Convert to Chart.js candlestick format
        const candlestickData = data.map(item => ({
            x: item.timestamp,
            o: item.open,
            h: item.high,
            l: item.low,
            c: item.close
        }));
        
        this.charts.ohlcv.data.datasets[0].data = candlestickData;
        this.charts.ohlcv.update();
    }

    // Update equity chart
    updateEquityChart() {
        const data = this.data.equity;
        
        if (data.length === 0) return;
        
        const labels = data.map(item => item.timestamp);
        const values = data.map(item => item.total_value);
        
        this.charts.equity.data.labels = labels;
        this.charts.equity.data.datasets[0].data = values;
        this.charts.equity.update();
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
        
        document.getElementById('sharpe-ratio').textContent = perf.sharpe_ratio?.toFixed(2) || '0.00';
        document.getElementById('sortino-ratio').textContent = perf.sortino_ratio?.toFixed(2) || '0.00';
        document.getElementById('max-drawdown').textContent = this.formatPercentage(perf.max_drawdown || 0);
        document.getElementById('win-rate').textContent = this.formatPercentage(perf.win_rate || 0);
        document.getElementById('annual-return').textContent = this.formatPercentage(perf.annualized_return || 0);
        document.getElementById('volatility').textContent = this.formatPercentage(perf.volatility || 0);
        document.getElementById('total-trades').textContent = perf.trade_count || 0;
        document.getElementById('ai-score').textContent = perf.ai_score || '0.00';
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
    
    // Initial data load
    dashboard.refreshData();
});

// Add Chart.js candlestick chart type
Chart.register({
    id: 'candlestick',
    beforeInit: function(chart) {
        chart.candlestick = {
            parse: function(data, index) {
                const value = data.datasets[0].data[index];
                return {
                    x: value.x,
                    o: value.o,
                    h: value.h,
                    l: value.l,
                    c: value.c
                };
            }
        };
    },
    afterDatasetsUpdate: function(chart) {
        const ctx = chart.ctx;
        const meta = chart.getDatasetMeta(0);
        
        meta.data.forEach((point, index) => {
            const candle = chart.candlestick.parse(chart.data, index);
            const x = point.x;
            const y = {
                high: candle.h,
                open: candle.o,
                close: candle.c,
                low: candle.l
            };
            
            // Draw candlestick
            ctx.beginPath();
            ctx.moveTo(x, y.high);
            ctx.lineTo(x, y.low);
            ctx.strokeStyle = y.close >= y.open ? '#22c55e' : '#ef4444';
            ctx.stroke();
            
            // Draw body
            ctx.beginPath();
            ctx.rect(x - 2, Math.min(y.open, y.close), 4, Math.abs(y.close - y.open));
            ctx.fillStyle = y.close >= y.open ? '#22c55e' : '#ef4444';
            ctx.fill();
        });
    }
});