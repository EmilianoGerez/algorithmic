"""
Enhanced Analysis Module for HTF Liquidity Strategy Backtests

This module provides comprehensive analysis and visualization capabilities for backtest results,
including interactive plotting, trade analysis, and data export functionality.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_enhanced_trading_plot(
    data_df: pd.DataFrame,
    trades_data: list[dict[str, Any]] | None = None,
    open_positions: list[dict[str, Any]] | None = None,
    events_df: pd.DataFrame | None = None,
    title: str = "HTF Liquidity Strategy Analysis",
    output_dir: Path | None = None,
) -> go.Figure:
    """Create enhanced interactive trading plot with comprehensive analysis.

    Args:
        data_df: Market data DataFrame with OHLCV columns
        trades_data: List of executed trades
        open_positions: List of open positions
        events_df: Events DataFrame (FVG, pools, etc.)
        title: Plot title
        output_dir: Output directory for saving plot

    Returns:
        Plotly Figure object
    """
    # Prepare data
    if "timestamp" not in data_df.columns:
        # Try to find timestamp-like column
        timestamp_cols = [col for col in data_df.columns if "time" in col.lower()]
        if timestamp_cols:
            data_df["timestamp"] = data_df[timestamp_cols[0]]
        else:
            # Create index-based timestamp
            data_df["timestamp"] = range(len(data_df))

    # Convert timestamp to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(data_df["timestamp"]):
        try:
            data_df["timestamp"] = pd.to_datetime(data_df["timestamp"])
        except Exception:
            # Use range if conversion fails
            data_df["timestamp"] = pd.date_range(
                start="2025-01-01", periods=len(data_df), freq="5min"
            )

    # Create subplot figure
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.7, 0.15, 0.15],
        subplot_titles=("Price Chart", "Volume", "P&L"),
    )

    # Add candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=data_df["timestamp"],
            open=data_df["open"],
            high=data_df["high"],
            low=data_df["low"],
            close=data_df["close"],
            name="Price",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # Add volume bars
    fig.add_trace(
        go.Bar(
            x=data_df["timestamp"],
            y=data_df["volume"],
            name="Volume",
            marker_color="rgba(0,100,200,0.3)",
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    # Process trades data
    if trades_data:
        # Separate buy and sell trades
        buy_trades = [t for t in trades_data if t.get("side") == "buy"]
        sell_trades = [t for t in trades_data if t.get("side") == "sell"]

        # Add buy markers
        if buy_trades:
            buy_times = []
            buy_prices = []
            buy_texts = []

            for trade in buy_trades:
                try:
                    timestamp = pd.to_datetime(
                        trade.get("entry_time", trade.get("timestamp", ""))
                    )
                    price = float(trade.get("entry_price", trade.get("price", 0)))
                    trade_id = trade.get("trade_id", "Unknown")

                    buy_times.append(timestamp)
                    buy_prices.append(price)
                    buy_texts.append(f"BUY {trade_id}<br>Price: {price:.2f}")
                except (ValueError, TypeError):
                    continue

            if buy_times:
                fig.add_trace(
                    go.Scatter(
                        x=buy_times,
                        y=buy_prices,
                        mode="markers",
                        marker={
                            "symbol": "triangle-up",
                            "size": 12,
                            "color": "green",
                            "line": {"color": "darkgreen", "width": 2},
                        },
                        name="Buy Orders",
                        text=buy_texts,
                        hovertemplate="%{text}<extra></extra>",
                    ),
                    row=1,
                    col=1,
                )

        # Add sell markers
        if sell_trades:
            sell_times = []
            sell_prices = []
            sell_texts = []

            for trade in sell_trades:
                try:
                    timestamp = pd.to_datetime(
                        trade.get("exit_time", trade.get("timestamp", ""))
                    )
                    price = float(trade.get("exit_price", trade.get("price", 0)))
                    trade_id = trade.get("trade_id", "Unknown")
                    pnl = trade.get("pnl", 0)

                    sell_times.append(timestamp)
                    sell_prices.append(price)
                    sell_texts.append(
                        f"SELL {trade_id}<br>Price: {price:.2f}<br>P&L: ${pnl:.2f}"
                    )
                except (ValueError, TypeError):
                    continue

            if sell_times:
                fig.add_trace(
                    go.Scatter(
                        x=sell_times,
                        y=sell_prices,
                        mode="markers",
                        marker={
                            "symbol": "triangle-down",
                            "size": 12,
                            "color": "red",
                            "line": {"color": "darkred", "width": 2},
                        },
                        name="Sell Orders",
                        text=sell_texts,
                        hovertemplate="%{text}<extra></extra>",
                    ),
                    row=1,
                    col=1,
                )

        # Calculate and plot cumulative P&L
        pnl_data = []
        cumulative_pnl = 0.0
        pnl_times = []

        for trade in sorted(
            trades_data,
            key=lambda x: x.get("exit_time", x.get("timestamp", "1970-01-01")),
        ):
            try:
                pnl = float(trade.get("pnl", 0))
                cumulative_pnl += pnl
                timestamp = pd.to_datetime(
                    trade.get("exit_time", trade.get("timestamp", ""))
                )

                pnl_times.append(timestamp)
                pnl_data.append(cumulative_pnl)
            except (ValueError, TypeError):
                continue

        if pnl_data:
            fig.add_trace(
                go.Scatter(
                    x=pnl_times,
                    y=pnl_data,
                    mode="lines+markers",
                    name="Cumulative P&L",
                    line={"color": "blue", "width": 2},
                    showlegend=False,
                ),
                row=3,
                col=1,
            )

    # Add open positions
    if open_positions:
        open_times = []
        open_prices = []
        open_texts = []

        for pos in open_positions:
            try:
                timestamp = pd.to_datetime(
                    pos.get("entry_time", pos.get("timestamp", ""))
                )
                price = float(pos.get("entry_price", pos.get("price", 0)))
                pos_id = pos.get("position_id", "Unknown")
                side = pos.get("side", "unknown")

                open_times.append(timestamp)
                open_prices.append(price)
                open_texts.append(f"OPEN {side.upper()} {pos_id}<br>Price: {price:.2f}")
            except (ValueError, TypeError):
                continue

        if open_times:
            fig.add_trace(
                go.Scatter(
                    x=open_times,
                    y=open_prices,
                    mode="markers",
                    marker={
                        "symbol": "diamond",
                        "size": 10,
                        "color": "orange",
                        "line": {"color": "darkorange", "width": 2},
                    },
                    name="Open Positions",
                    text=open_texts,
                    hovertemplate="%{text}<extra></extra>",
                ),
                row=1,
                col=1,
            )

    # Add events (FVG zones, pools, etc.)
    if events_df is not None and not events_df.empty:
        # Group events by type
        event_types: list[str] = (
            events_df.get("event_type", pd.Series()).unique().tolist()
            if "event_type" in events_df.columns
            else []
        )

        colors = ["purple", "cyan", "yellow", "pink", "lightblue"]

        for i, event_type in enumerate(event_types):
            event_subset = events_df[events_df["event_type"] == event_type]

            if not event_subset.empty:
                try:
                    times = pd.to_datetime(
                        event_subset.get("timestamp", event_subset.index)
                    )
                    prices = event_subset.get("price", event_subset.get("close", 0))

                    fig.add_trace(
                        go.Scatter(
                            x=times,
                            y=prices,
                            mode="markers",
                            marker={
                                "symbol": "star",
                                "size": 8,
                                "color": colors[i % len(colors)],
                            },
                            name=f"{event_type} Events",
                            hovertemplate=f"{event_type}<br>Time: %{{x}}<br>Price: %{{y}}<extra></extra>",
                        ),
                        row=1,
                        col=1,
                    )
                except Exception:
                    continue

    # Update layout
    fig.update_layout(
        title=title,
        height=800,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )

    # Update axes
    fig.update_xaxes(title_text="Time", row=3, col=1)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="P&L ($)", row=3, col=1)

    # Save plot if output directory provided
    if output_dir:
        output_path = Path(output_dir) / "enhanced_trading_plot.html"
        fig.write_html(str(output_path))
        print(f"   → Plot saved to: {output_path.name}")

    return fig


def export_trade_summary(
    trades_data: list[dict[str, Any]] | None = None,
    open_positions: list[dict[str, Any]] | None = None,
    output_dir: Path | None = None,
    formats: list[str] | None = None,
) -> dict[str, Path]:
    """Export comprehensive trade summary in multiple formats.

    Args:
        trades_data: List of executed trades
        open_positions: List of open positions
        output_dir: Output directory for files
        formats: List of export formats ('csv', 'json', 'excel')

    Returns:
        Dictionary mapping format to output file path
    """
    if formats is None:
        formats = ["csv", "json", "excel"]

    if output_dir is None:
        output_dir = Path(".")

    output_dir = Path(output_dir)
    exported_files = {}

    # Prepare summary data
    summary_data = {
        "trades": trades_data or [],
        "open_positions": open_positions or [],
        "analysis_timestamp": pd.Timestamp.now().isoformat(),
        "summary_stats": _calculate_summary_stats(trades_data),
    }

    # Export as JSON
    if "json" in formats:
        json_path = output_dir / "trade_summary.json"
        with open(json_path, "w") as f:
            json.dump(summary_data, f, indent=2, default=str)
        exported_files["json"] = json_path
        print(f"   → JSON exported: {json_path.name}")

    # Export as CSV
    if "csv" in formats and trades_data:
        csv_path = output_dir / "trades_detailed.csv"
        trades_df = pd.DataFrame(trades_data)
        trades_df.to_csv(csv_path, index=False)
        exported_files["csv"] = csv_path
        print(f"   → CSV exported: {csv_path.name}")

    # Export as Excel
    if "excel" in formats:
        excel_path = output_dir / "backtest_analysis.xlsx"

        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            # Trades sheet
            if trades_data:
                trades_df = pd.DataFrame(trades_data)
                trades_df.to_excel(writer, sheet_name="Trades", index=False)

            # Open positions sheet
            if open_positions:
                positions_df = pd.DataFrame(open_positions)
                positions_df.to_excel(writer, sheet_name="Open_Positions", index=False)

            # Summary stats sheet
            stats_df = pd.DataFrame([summary_data["summary_stats"]])
            stats_df.to_excel(writer, sheet_name="Summary_Stats", index=False)

        exported_files["excel"] = excel_path
        print(f"   → Excel exported: {excel_path.name}")

    return exported_files


def _calculate_summary_stats(
    trades_data: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Calculate summary statistics from trades data.

    Args:
        trades_data: List of executed trades

    Returns:
        Dictionary of summary statistics
    """
    if not trades_data:
        return {
            "total_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
        }

    # Extract trade metrics
    pnls = []
    win_count = 0

    for trade in trades_data:
        try:
            pnl = float(trade.get("pnl", 0))
            pnls.append(pnl)

            if pnl > 0:
                win_count += 1
        except (ValueError, TypeError):
            continue

    if not pnls:
        return _calculate_summary_stats(None)

    # Calculate statistics
    total_pnl = sum(pnls)
    total_trades = len(pnls)
    win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

    # Calculate max drawdown
    cumulative_pnl = 0.0
    peak = 0.0
    max_drawdown = 0.0

    for pnl in pnls:
        cumulative_pnl += pnl
        peak = max(peak, cumulative_pnl)
        drawdown = peak - cumulative_pnl
        max_drawdown = max(max_drawdown, drawdown)

    # Calculate profit factor
    total_profit = sum(pnl for pnl in pnls if pnl > 0)
    total_loss = abs(sum(pnl for pnl in pnls if pnl < 0))
    profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")

    return {
        "total_trades": total_trades,
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 2),
        "avg_pnl": round(avg_pnl, 2),
        "max_drawdown": round(max_drawdown, 2),
        "profit_factor": round(profit_factor, 2),
        "winning_trades": win_count,
        "losing_trades": total_trades - win_count,
        "total_profit": round(total_profit, 2),
        "total_loss": round(total_loss, 2),
    }


# Additional utility functions for compatibility


def load_backtest_results(results_dir: Path) -> dict[str, Any]:
    """Load all backtest results from directory.

    Args:
        results_dir: Path to results directory

    Returns:
        Dictionary containing all loaded data
    """
    results = {}

    # Load market data
    data_path = results_dir / "data.csv"
    if data_path.exists():
        results["data_df"] = pd.read_csv(data_path)

    # Load trades (try multiple filenames)
    trades_path = results_dir / "all_trades.json"
    if not trades_path.exists():
        trades_path = results_dir / "trades.json"

    if trades_path.exists():
        with open(trades_path) as f:
            results["trades_data"] = json.load(f)

    # Load open positions
    positions_path = results_dir / "open_positions.json"
    if positions_path.exists():
        with open(positions_path) as f:
            results["open_positions"] = json.load(f)

    # Load events
    events_path = results_dir / "events.parquet"
    if events_path.exists():
        with contextlib.suppress(Exception):
            results["events_df"] = pd.read_parquet(events_path)

    return results


def create_quick_analysis(results_dir: Path) -> go.Figure:
    """Create quick analysis plot from results directory.

    Args:
        results_dir: Path to results directory

    Returns:
        Plotly Figure object
    """
    data = load_backtest_results(results_dir)

    return create_enhanced_trading_plot(
        data_df=data.get("data_df", pd.DataFrame()),
        trades_data=data.get("trades_data"),
        open_positions=data.get("open_positions"),
        events_df=data.get("events_df"),
        title=f"Quick Analysis - {results_dir.name}",
        output_dir=results_dir,
    )
