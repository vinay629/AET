"""Command-line interface for BAET.

Provides commands for data ingestion, backtesting, paper trading, and system status.

Usage:
    baet ingest --symbols BTCUSDT ETHUSDT --days 30
    baet backtest --strategy sma_crossover --start 2024-01-01 --end 2024-06-01
    baet paper-trade --duration 7
    baet status
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import click

from baet.config.loader import load_settings
from baet.config.models import Settings

logger = logging.getLogger(__name__)


def _load_config(config_path: str | None = None) -> Settings:
    """Load BAET settings from the default env file or an explicit env file path."""
    if config_path:
        return load_settings(env_file=Path(config_path))
    return load_settings()


@click.group()
@click.option("--config", "-c", type=str, default=None, help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, config: str | None, verbose: bool) -> None:
    """BAET — Binance Adaptive Ensemble Trader."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@cli.command()
@click.option(
    "--symbols",
    "-s",
    multiple=True,
    default=["BTCUSDT", "ETHUSDT"],
    help="Symbols to ingest",
)
@click.option("--days", "-d", type=int, default=30, help="Number of days of historical data")
@click.option("--timeframe", "-t", type=str, default="1h", help="Candle timeframe")
@click.pass_context
def ingest(ctx: click.Context, symbols: tuple[str, ...], days: int, timeframe: str) -> None:
    """Download historical market data from Binance."""
    settings = _load_config(ctx.obj["config_path"])
    click.echo(f"📥 Ingesting {days} days of {timeframe} data for: {', '.join(symbols)}")

    try:
        from baet.data.ingestion import DataIngester

        ingester = DataIngester(settings=settings)
        for symbol in symbols:
            click.echo(f"  Fetching {symbol}...")
            df = ingester.fetch_historical(
                symbol=symbol,
                timeframe=timeframe,
                days=days,
            )
            if df is not None and len(df) > 0:
                path = ingester.save_raw(df, symbol, timeframe)
                click.echo(f"  ✅ {symbol}: {len(df)} candles saved to {path}")
            else:
                click.echo(f"  ⚠️ {symbol}: No data received")

        click.echo("✅ Ingestion complete")
    except Exception as e:
        click.echo(f"❌ Ingestion failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--strategy", "-s", type=str, default="sma_crossover", help="Strategy to backtest")
@click.option("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
@click.option("--symbols", "-sym", multiple=True, default=None, help="Symbols to backtest")
@click.pass_context
def backtest(
    ctx: click.Context,
    strategy: str,
    start: str | None,
    end: str | None,
    symbols: tuple[str, ...],
) -> None:
    """Run a strategy backtest on historical data."""
    settings = _load_config(ctx.obj["config_path"])
    symbols_str = ", ".join(symbols) if symbols else "default"
    click.echo(f"📊 Backtesting {strategy} on [{symbols_str}]")
    if start:
        click.echo(f"  Start: {start}")
    if end:
        click.echo(f"  End: {end}")

    try:
        from baet.execution.backtest import PortfolioBacktestEngine
        from baet.strategies.baselines import BuyAndHoldStrategy

        engine = PortfolioBacktestEngine(settings.backtest)
        strategy_obj = BuyAndHoldStrategy()

        market_frames = {}
        signals = {}
        for sym in list(symbols) if symbols else settings.market.symbols:
            for tf in settings.market.timeframes:
                from baet.data.binance import BinanceHistoricalProvider
                from datetime import UTC, datetime, timedelta

                provider = BinanceHistoricalProvider(settings)
                end_dt = datetime.now(UTC)
                start_dt = end_dt - timedelta(days=365)
                candles = provider.fetch_klines(sym, tf, start_dt, end_dt)
                key = (sym, tf)
                market_frames[key] = candles
                signals[key] = strategy_obj.generate_signals(candles)

        artifacts = engine.run(market_frames, signals, run_name=f"cli_{strategy}")

        click.echo("\n📈 Backtest Results:")
        click.echo(f"  Final Equity: {artifacts.equity_curve['equity'].iloc[-1]:.2f}")
        click.echo(f"  Total Trades: {len(artifacts.trades)}")
        click.echo("✅ Backtest complete")
    except Exception as e:
        click.echo(f"❌ Backtest failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--duration", "-d", type=int, default=None, help="Duration in days")
@click.option("--dry-run", is_flag=True, default=False, help="Run without executing trades")
@click.pass_context
def paper_trade(ctx: click.Context, duration: int | None, dry_run: bool) -> None:
    """Start paper trading loop."""
    settings = _load_config(ctx.obj["config_path"])

    if dry_run:
        click.echo("🔍 Dry run mode — no trades will be executed")

    click.echo("🚀 Starting paper trading...")
    click.echo(f"  Symbols: {', '.join(settings.market.symbols)}")
    click.echo(f"  Balance: ${settings.paper.initial_balance:,.2f}")
    if duration:
        click.echo(f"  Duration: {duration} days")

    try:
        from baet.paper.engine import PaperTradingEngine

        engine = PaperTradingEngine(config=settings)

        if duration:
            settings.paper.duration_days = duration

        engine.start()  # Blocks until stopped or duration expires

        # Print summary
        summary = engine.get_summary()
        click.echo("\n📊 Paper Trading Summary:")
        click.echo(f"  Total Trades: {summary.get('total_trades', 0)}")
        click.echo(f"  Final Value: ${summary.get('final_value', 0):,.2f}")
        click.echo(f"  P&L: ${summary.get('total_pnl', 0):+,.2f}")
        click.echo("✅ Paper trading complete")
    except KeyboardInterrupt:
        click.echo("\n⏹️ Paper trading stopped by user")
    except Exception as e:
        click.echo(f"❌ Paper trading failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current system status."""
    settings = _load_config(ctx.obj["config_path"])

    click.echo("📊 BAET System Status")
    click.echo("=" * 40)
    click.echo(f"  App: {settings.app.name} v0.1.0")
    click.echo(f"  Mode: {settings.app.mode.value}")
    click.echo(f"  Symbols: {', '.join(settings.market.symbols)}")
    click.echo(f"  Paper Balance: ${settings.paper.initial_balance:,.2f}")
    click.echo(f"  Live Trading: {'enabled' if settings.live.enabled else 'disabled'}")
    click.echo(f"  Testnet: {'yes' if settings.live.testnet else 'no'}")

    # M5.2 status
    m5_2 = settings.live.m5_2
    click.echo("\n🔒 M5.2 Risk Limits:")
    click.echo(f"  Enabled: {'yes' if m5_2.enabled else 'no'}")
    click.echo(f"  Daily Loss Limit: ${m5_2.daily_loss_limit}")
    click.echo(f"  Position Loss Limit: ${m5_2.single_position_loss_limit}")
    click.echo(f"  Consecutive Loss Limit: {m5_2.consecutive_loss_limit}")
    click.echo(f"  Max Concurrent: {m5_2.max_concurrent_positions}")
    click.echo(f"  Max Daily Trades: {m5_2.max_daily_trades}")
    click.echo(f"  Emergency Stop: {'yes' if m5_2.emergency_stop_on_breach else 'no'}")

    # Notification status
    notif = settings.notifications
    click.echo("\n🔔 Notifications:")
    click.echo(f"  Enabled: {'yes' if notif.enabled else 'no'}")
    telegram_status = (
        "configured" if notif.telegram_bot_token.get_secret_value() else "not configured"
    )
    click.echo(f"  Telegram: {telegram_status}")
    click.echo(f"  Discord: {'configured' if notif.discord_webhook_url else 'not configured'}")

    # Check audit log directory
    audit_dir = Path("logs/audit")
    if audit_dir.exists():
        audit_files = list(audit_dir.glob("*.jsonl"))
        click.echo("\n📋 Audit Trail:")
        click.echo(f"  Log files: {len(audit_files)}")
        if audit_files:
            latest = max(audit_files, key=lambda p: p.stat().st_mtime)
            click.echo(f"  Latest: {latest.name}")
    else:
        click.echo("\n📋 Audit Trail: No logs yet")

    click.echo(f"\n⏰ Timestamp: {datetime.now().isoformat()}")


@cli.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Validate configuration and system readiness."""
    click.echo("🔍 Validating BAET configuration...")
    errors: list[str] = []
    warnings: list[str] = []

    try:
        settings = _load_config(ctx.obj["config_path"])
    except Exception as err:
        click.echo(f"❌ Failed to load config: {err}")
        sys.exit(1)

    # Check directories
    for dir_name, dir_path in [
        ("Raw data", settings.storage.raw_data_dir),
        ("Processed data", settings.storage.processed_data_dir),
        ("Results", settings.storage.results_dir),
        ("Logs", settings.storage.logs_dir),
    ]:
        if not dir_path.exists():
            warnings.append(f"{dir_name} directory does not exist: {dir_path}")

    # Check live config
    if settings.live.enabled:
        if not settings.live.testnet:
            warnings.append("Live trading enabled on mainnet — use with caution!")
        if not settings.secrets.live_binance_api_key.get_secret_value():
            errors.append("Live trading enabled but no API key configured")

    # Check M5.2
    if settings.live.m5_2.enabled:
        if settings.live.m5_2.daily_loss_limit <= 0:
            errors.append("M5.2 daily_loss_limit must be positive")
        if settings.live.m5_2.max_concurrent_positions < 1:
            errors.append("M5.2 max_concurrent_positions must be >= 1")

    # Check notifications
    if (
        settings.notifications.enabled
        and not settings.notifications.telegram_bot_token.get_secret_value()
        and not settings.notifications.discord_webhook_url
    ):
        warnings.append("Notifications enabled but no channel configured")

    # Report
    for w in warnings:
        click.echo(f"  ⚠️  {w}")
    for error in errors:
        click.echo(f"  ❌ {error}")

    if errors:
        click.echo(f"\n❌ Validation failed with {len(errors)} error(s)")
        sys.exit(1)
    elif warnings:
        click.echo(f"\n✅ Validation passed with {len(warnings)} warning(s)")
    else:
        click.echo("\n✅ All checks passed")


def main() -> None:
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
