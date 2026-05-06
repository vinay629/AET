"""Script to analyze paper trading logs."""

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def parse_log_file(log_file: Path) -> list[dict]:
    """Parse a JSON-formatted log file.
    
    Args:
        log_file: Path to the log file
        
    Returns:
        List of log entries as dictionaries
    """
    entries = []
    
    with open(log_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse line: {line[:100]}")
    
    return entries


def filter_by_type(entries: list[dict], entry_type: str) -> list[dict]:
    """Filter log entries by type.
    
    Args:
        entries: List of log entries
        entry_type: Type to filter by (SIGNAL, RISK, ORDER, etc.)
        
    Returns:
        Filtered list of entries
    """
    return [e for e in entries if e.get("type") == entry_type]


def print_summary(entries: list[dict]):
    """Print a summary of log entries.
    
    Args:
        entries: List of log entries
    """
    # Count by type
    type_counts = defaultdict(int)
    for entry in entries:
        type_counts[entry.get("type", "UNKNOWN")] += 1
    
    print("\n=== Log Summary ===")
    print(f"Total entries: {len(entries)}")
    print("\nEntries by type:")
    for entry_type, count in sorted(type_counts.items()):
        print(f"  {entry_type}: {count}")
    
    # Time range
    if entries:
        timestamps = [e.get("timestamp") for e in entries if e.get("timestamp")]
        if timestamps:
            print(f"\nTime range:")
            print(f"  First: {min(timestamps)}")
            print(f"  Last: {max(timestamps)}")
    
    # Signal summary
    signals = filter_by_type(entries, "SIGNAL_RECEIVED")
    if signals:
        print(f"\n=== Signal Summary ({len(signals)} signals) ===")
        symbol_counts = defaultdict(int)
        for signal in signals:
            symbol = signal.get("symbol", "unknown")
            symbol_counts[symbol] += 1
        
        for symbol, count in sorted(symbol_counts.items()):
            print(f"  {symbol}: {count} signals")
    
    # Risk evaluation summary
    risk_evals = filter_by_type(entries, "RISK_EVALUATION")
    if risk_evals:
        print(f"\n=== Risk Evaluation Summary ({len(risk_evals)} evaluations) ===")
        passed = sum(1 for e in risk_evals if e.get("result", {}).get("passed", True))
        failed = len(risk_evals) - passed
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
    
    # Order simulation summary
    orders = filter_by_type(entries, "ORDER_SIMULATED")
    if orders:
        print(f"\n=== Order Simulation Summary ({len(orders)} orders) ===")
        buys = [o for o in orders if o.get("side") == "BUY"]
        sells = [o for o in orders if o.get("side") == "SELL"]
        print(f"  Buy orders: {len(buys)}")
        print(f"  Sell orders: {len(sells)}")
        
        if orders:
            total_slippage = sum(o.get("slippage", 0) for o in orders)
            avg_slippage = total_slippage / len(orders)
            print(f"  Average slippage: {avg_slippage:.4f}")
    
    # Portfolio updates summary
    portfolio_updates = filter_by_type(entries, "PORTFOLIO_UPDATE")
    if portfolio_updates:
        print(f"\n=== Portfolio Update Summary ({len(portfolio_updates)} updates) ===")
        final_update = portfolio_updates[-1]
        print(f"  Final cash: {final_update.get('cash', 0):.2f}")
        print(f"  Final value: {final_update.get('total_value', 0):.2f}")
        print(f"  Final positions: {len(final_update.get('positions', {}))}")


def export_to_csv(entries: list[dict], output_file: Path, entry_type: str | None = None):
    """Export log entries to CSV.
    
    Args:
        entries: List of log entries
        output_file: Path to output CSV file
        entry_type: Optional type filter
    """
    import csv
    
    if entry_type:
        entries = filter_by_type(entries, entry_type)
    
    if not entries:
        print(f"No entries to export")
        return
    
    # Flatten entries
    flattened = []
    for entry in entries:
        flat = {
            "timestamp": entry.get("timestamp"),
            "type": entry.get("type"),
        }
        
        # Add type-specific fields
        if entry.get("type") == "SIGNAL_RECEIVED":
            flat["symbol"] = entry.get("symbol")
            signal = entry.get("signal", {})
            flat["direction"] = signal.get("direction")
            flat["strength"] = signal.get("strength")
        
        elif entry.get("type") == "RISK_EVALUATION":
            flat["symbol"] = entry.get("symbol")
            result = entry.get("result", {})
            flat["passed"] = result.get("passed")
            flat["violations"] = len(result.get("violations", []))
        
        elif entry.get("type") == "ORDER_SIMULATED":
            flat["symbol"] = entry.get("symbol")
            flat["side"] = entry.get("side")
            flat["requested_price"] = entry.get("requested_price")
            flat["filled_price"] = entry.get("filled_price")
            flat["units"] = entry.get("units")
            flat["fee"] = entry.get("fee")
            flat["slippage"] = entry.get("slippage")
        
        elif entry.get("type") == "PORTFOLIO_UPDATE":
            flat["action"] = entry.get("action")
            flat["symbol"] = entry.get("symbol")
            flat["cash"] = entry.get("cash")
            flat["total_value"] = entry.get("total_value")
        
        flattened.append(flat)
    
    # Write to CSV
    if flattened:
        fieldnames = set()
        for entry in flattened:
            fieldnames.update(entry.keys())
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
            writer.writeheader()
            writer.writerows(flattened)
        
        print(f"Exported {len(flattened)} entries to {output_file}")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_paper_logs.py <log_file> [--type TYPE] [--export-csv FILE]")
        print("\nExamples:")
        print("  python analyze_paper_logs.py logs/paper/paper_trading_2024-01-15.log")
        print("  python analyze_paper_logs.py logs/paper/paper_trading_2024-01-15.log --type ORDER_SIMULATED")
        print("  python analyze_paper_logs.py logs/paper/paper_trading_2024-01-15.log --export-csv output.csv")
        sys.exit(1)
    
    log_file = Path(sys.argv[1])
    
    if not log_file.exists():
        print(f"Error: Log file not found: {log_file}")
        sys.exit(1)
    
    # Parse arguments
    entry_type = None
    export_file = None
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--type" and i + 1 < len(sys.argv):
            entry_type = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--export-csv" and i + 1 < len(sys.argv):
            export_file = Path(sys.argv[i + 1])
            i += 2
        else:
            i += 1
    
    # Parse log file
    print(f"Parsing log file: {log_file}")
    entries = parse_log_file(log_file)
    
    # Filter by type if specified
    if entry_type:
        entries = filter_by_type(entries, entry_type)
        print(f"Filtered to {len(entries)} entries of type '{entry_type}'")
    
    # Print summary
    print_summary(entries)
    
    # Export to CSV if requested
    if export_file:
        export_to_csv(entries, export_file, entry_type)


if __name__ == "__main__":
    main()
