#!/usr/bin/env python3
"""
Static backtest visualization script using mplfinance.

Creates candlestick charts with FVG zones and trade markers from the latest
backtest results. Automatically finds the most recent results directory.

Usage:
    python scripts/plot_static.py
    python scripts/plot_static.py --run-dir results/backtest_20250727_123456

Requirements:
    pip install mplfinance pandas
"""

import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Generate static backtest visualization")
    parser.add_argument(
        "run_dir",
        nargs="?",
        type=str,
        help="Results directory to plot (default: latest if not specified)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: save in results directory)"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="2h",
        help="FVG zone duration (default: 2h)"
    )
    
    args = parser.parse_args()
    
    try:
        import pandas as pd
        import mplfinance as mpf
        import datetime as dt
    except ImportError as e:
        print(f"Error: Required packages not installed. Run: pip install mplfinance pandas")
        print(f"Import error: {e}")
        sys.exit(1)
    
    # Find results directory
    results_base = Path('results')
    if not results_base.exists():
        print("Error: 'results' directory not found. Run from project root.")
        sys.exit(1)
    
    if args.run_dir:
        run_dir = Path(args.run_dir)
        if not run_dir.exists():
            print(f"Error: Specified directory '{args.run_dir}' does not exist")
            sys.exit(1)
    else:
        # Find latest run directory
        run_dirs = [d for d in results_base.iterdir() if d.is_dir()]
        if not run_dirs:
            print("Error: No backtest result directories found in 'results/'")
            sys.exit(1)
        run_dir = max(run_dirs, key=lambda x: x.stat().st_mtime)
    
    print(f"Using results from: {run_dir}")
    
    # Check for required files
    data_file = run_dir / 'data.csv'
    trades_file = run_dir / 'trades.csv'
    events_file = run_dir / 'events.parquet'
    
    if not data_file.exists():
        print(f"Error: data.csv not found in {run_dir}")
        print("Ensure backtest was run with data export enabled")
        sys.exit(1)
    
    try:
        # Load market data
        print("Loading market data...")
        bars = pd.read_csv(data_file, index_col='timestamp', parse_dates=True)
        print(f"Loaded {len(bars)} candles")
        
        # Handle large datasets by sampling if necessary
        MAX_CANDLES = 1000  # Reasonable limit for mplfinance
        original_length = len(bars)
        
        if len(bars) > MAX_CANDLES:
            print(f"Dataset has {len(bars)} candles, sampling to {MAX_CANDLES} for visualization")
            # Sample every nth row to get approximately MAX_CANDLES
            step = len(bars) // MAX_CANDLES
            bars = bars.iloc[::step].copy()
            print(f"Sampled to {len(bars)} candles")
        
        # Load trades if available
        additional_plots = []
        if trades_file.exists():
            print("Loading trades...")
            trades = pd.read_csv(trades_file)
            print(f"Loaded {len(trades)} trades")
            
            # Only process trades if we actually have trade data (not just headers)
            if len(trades) > 0 and 'entry_price' in trades.columns and 'entry_ts' in trades.columns:
                # Convert timestamps to match the data index
                try:
                    trades['entry_ts'] = pd.to_datetime(trades['entry_ts'])
                    trades['exit_ts'] = pd.to_datetime(trades['exit_ts'])
                    
                    # Create entry signals aligned with price data
                    entry_signals = pd.Series(index=bars.index, dtype=float)
                    exit_signals = pd.Series(index=bars.index, dtype=float)
                    
                    for _, trade in trades.iterrows():
                        # Find the closest timestamp in our data for entry
                        entry_idx = bars.index.get_indexer([trade['entry_ts']], method='nearest')[0]
                        if 0 <= entry_idx < len(bars):
                            entry_signals.iloc[entry_idx] = trade['entry_price']
                        
                        # Find the closest timestamp in our data for exit
                        if pd.notna(trade['exit_ts']):
                            exit_idx = bars.index.get_indexer([trade['exit_ts']], method='nearest')[0]
                            if 0 <= exit_idx < len(bars):
                                exit_signals.iloc[exit_idx] = trade['exit_price']
                    
                    # Only add plots if we have signals to show
                    if entry_signals.notna().any():
                        additional_plots.append(
                            mpf.make_addplot(
                                entry_signals, 
                                type='scatter', 
                                marker='^', 
                                color='lime', 
                                markersize=70
                            )
                        )
                    
                    if exit_signals.notna().any():
                        additional_plots.append(
                            mpf.make_addplot(
                                exit_signals, 
                                type='scatter', 
                                marker='x', 
                                color='red', 
                                markersize=70
                            )
                        )
                except Exception as e:
                    print(f"Warning: Could not process trade signals: {e}")
            else:
                print("No trade data to plot (empty file or missing columns)")
        
        # Load FVG events if available
        fvg_rects = []
        if events_file.exists():
            try:
                print("Loading events...")
                events = pd.read_parquet(events_file)
                fvg_events = events[events['type'] == 'FVGEvent'] if 'type' in events.columns else pd.DataFrame()
                
                fvg_rects = [
                    dict(
                        x0=row.ts,
                        x1=pd.to_datetime(row.ts) + pd.Timedelta(args.timeframe),
                        y0=row.bottom, 
                        y1=row.top,
                        facecolor='cornflowerblue', 
                        alpha=0.15
                    )
                    for _, row in fvg_events.iterrows()
                ]
                print(f"Loaded {len(fvg_rects)} FVG zones")
                
            except Exception as e:
                print(f"Warning: Could not load events: {e}")
        
        # Create the plot
        print("Generating chart...")
        
        plot_kwargs = {
            'type': 'candle',
            'style': 'yahoo',
            'figratio': (16, 9),
            'tight_layout': True,
            'title': f"{run_dir.name} – FVG & Trades",
            'warn_too_much_data': len(bars) + 100  # Silence warning for our data size
        }
        
        if additional_plots:
            plot_kwargs['addplot'] = additional_plots
        
        if fvg_rects:
            plot_kwargs['alines'] = fvg_rects
        
        if args.output:
            plot_kwargs['savefig'] = args.output
            print(f"Saving chart to: {args.output}")
        else:
            print("Displaying chart...")
        
        mpf.plot(bars, **plot_kwargs)
        
        if args.output:
            print(f"Chart saved to: {args.output}")
        
    except Exception as e:
        print(f"Error generating chart: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
