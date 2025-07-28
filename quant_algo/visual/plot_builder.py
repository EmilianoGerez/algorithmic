"""
Plot builder for creating interactive and static charts from backtest results.

This module provides unified plotting interface for:
1. Candlestick charts with overlays (FVG, Pivots, Trades)
2. Interactive Plotly charts
3. Static mplfinance charts
4. ChatGPT-compatible inline visualization
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go


def build_plotly(run_ctx: Any) -> go.Figure:
    """Build interactive Plotly chart from backtest run context.

    Args:
        run_ctx: Backtest run context with data paths

    Returns:
        Plotly Figure object
    """
    # Load data files
    data_path = (
        getattr(run_ctx, "data_path", None)
        or getattr(run_ctx, "out_dir", Path(".")) / "data.csv"
    )
    trades_path = (
        getattr(run_ctx, "trades_path", None)
        or getattr(run_ctx, "out_dir", Path(".")) / "trades.csv"
    )
    events_path = (
        getattr(run_ctx, "events_path", None)
        or getattr(run_ctx, "out_dir", Path(".")) / "events.parquet"
    )

    # Check if files exist
    if not Path(data_path).exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    # Load market data
    bars = pd.read_csv(data_path)

    # Create candlestick chart
    fig = go.Figure(
        data=go.Candlestick(
            x=bars["timestamp"],
            open=bars["open"],
            high=bars["high"],
            low=bars["low"],
            close=bars["close"],
            name="Price",
        )
    )

    # Add FVG zones if events file exists
    if Path(events_path).exists():
        try:
            import pyarrow  # Check if parquet support available

            events = pd.read_parquet(events_path)

            # Add FVG rectangles
            fvg_events = (
                events[events["type"] == "FVGEvent"]
                if "type" in events.columns
                else pd.DataFrame()
            )
            for _, event in fvg_events.iterrows():
                fig.add_shape(
                    type="rect",
                    x0=event["ts"],
                    x1=pd.to_datetime(event["ts"]) + pd.Timedelta("2H"),
                    y0=event["bottom"],
                    y1=event["top"],
                    fillcolor="rgba(100, 149, 237, 0.15)",  # cornflowerblue
                    line={"width": 0},
                    name=f"FVG {event.get('id', '')}",
                )

            # Add Pivot lines if available
            pivot_events = (
                events[events["type"] == "PivotEvent"]
                if "type" in events.columns
                else pd.DataFrame()
            )
            for _, event in pivot_events.iterrows():
                fig.add_hline(
                    y=event["price"],
                    line_dash="dot",
                    line_color="orange",
                    annotation_text=f"Pivot {event.get('side', '')}",
                    annotation_position="bottom right",
                )
        except ImportError:
            print("Warning: pyarrow not available, skipping events visualization")
        except Exception as e:
            print(f"Warning: Could not load events file: {e}")

    # Add trades if trades file exists
    if Path(trades_path).exists():
        try:
            trades = pd.read_csv(trades_path)

            # Entry points
            if "entry_ts" in trades.columns and "entry_price" in trades.columns:
                fig.add_trace(
                    go.Scatter(
                        x=trades["entry_ts"],
                        y=trades["entry_price"],
                        mode="markers",
                        name="Entry",
                        marker={"symbol": "triangle-up", "size": 12, "color": "lime"},
                    )
                )

            # Exit points
            if "exit_ts" in trades.columns and "exit_price" in trades.columns:
                fig.add_trace(
                    go.Scatter(
                        x=trades["exit_ts"],
                        y=trades["exit_price"],
                        mode="markers",
                        name="Exit",
                        marker={"symbol": "x", "size": 12, "color": "red"},
                    )
                )
        except Exception as e:
            print(f"Warning: Could not load trades file: {e}")

    # Update layout
    fig.update_layout(
        height=800,
        title="Interactive Back-test Chart",
        xaxis_title="Time",
        yaxis_title="Price",
        showlegend=True,
        xaxis_rangeslider_visible=False,  # Remove range slider for cleaner look
    )

    return fig


def build_static_chart(run_ctx: Any, output_path: Path | None = None) -> Path:
    """Build static mplfinance chart from backtest run context.

    Args:
        run_ctx: Backtest run context with data paths
        output_path: Optional output path for the chart

    Returns:
        Path to the saved chart
    """
    try:
        import mplfinance as mpf
    except ImportError as e:
        raise ImportError(
            "mplfinance required for static plotting. Install with: pip install mplfinance"
        ) from e

    # Load data files (similar to build_plotly)
    data_path = (
        getattr(run_ctx, "data_path", None)
        or getattr(run_ctx, "out_dir", Path(".")) / "data.csv"
    )
    trades_path = (
        getattr(run_ctx, "trades_path", None)
        or getattr(run_ctx, "out_dir", Path(".")) / "trades.csv"
    )
    events_path = (
        getattr(run_ctx, "events_path", None)
        or getattr(run_ctx, "out_dir", Path(".")) / "events.parquet"
    )

    if not Path(data_path).exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    # Load and prepare data
    bars = pd.read_csv(data_path, index_col="timestamp", parse_dates=True)

    # Prepare additional plots
    additional_plots = []

    # Add trades if available
    if Path(trades_path).exists():
        try:
            trades = pd.read_csv(trades_path)
            if "entry_price" in trades.columns:
                additional_plots.append(
                    mpf.make_addplot(
                        trades["entry_price"],
                        type="scatter",
                        marker="^",
                        color="lime",
                        markersize=70,
                    )
                )
            if "exit_price" in trades.columns:
                additional_plots.append(
                    mpf.make_addplot(
                        trades["exit_price"],
                        type="scatter",
                        marker="x",
                        color="red",
                        markersize=70,
                    )
                )
        except Exception as e:
            print(f"Warning: Could not load trades for static chart: {e}")

    # Prepare FVG rectangles
    fvg_rects = []
    if Path(events_path).exists():
        try:
            events = pd.read_parquet(events_path)
            fvg_events = (
                events[events["type"] == "FVGEvent"]
                if "type" in events.columns
                else pd.DataFrame()
            )

            fvg_rects = [
                {
                    "x0": row.ts,
                    "x1": pd.to_datetime(row.ts) + pd.Timedelta("2h"),
                    "y0": row.bottom,
                    "y1": row.top,
                    "facecolor": "cornflowerblue",
                    "alpha": 0.15,
                }
                for _, row in fvg_events.iterrows()
            ]
        except Exception as e:
            print(f"Warning: Could not load events for static chart: {e}")

    # Set output path
    if output_path is None:
        output_path = getattr(run_ctx, "out_dir", Path(".")) / "backtest_chart.png"

    # Create the plot
    mpf.plot(
        bars,
        type="candle",
        addplot=additional_plots if additional_plots else None,
        alines=fvg_rects if fvg_rects else None,
        style="yahoo",
        figratio=(16, 9),
        tight_layout=True,
        title=f"Backtest Chart - {getattr(run_ctx, 'symbol', 'Unknown')}",
        savefig=str(output_path),
    )

    return output_path


def display_chart_in_chatgpt(fig: go.Figure) -> None:
    """Display Plotly chart in ChatGPT environment.

    Args:
        fig: Plotly Figure to display
    """
    if os.getenv("CHATGPT_ENV") == "1":
        try:
            from python_user_visible import display_plotly

            display_plotly(fig)
        except ImportError:
            print("Warning: python_user_visible not available in this environment")
    else:
        print(
            "Not in ChatGPT environment, use fig.show() or fig.write_html() to view chart"
        )


# =============================================================================
# DataFrame-based helper functions for direct data visualization
# =============================================================================


def build_plotly_from_data(
    data_df: pd.DataFrame,
    trades_df: pd.DataFrame | None = None,
    events_df: pd.DataFrame | None = None,
    title: str = "Trading Chart",
) -> go.Figure:
    """Build interactive Plotly chart from DataFrames directly.

    Args:
        data_df: Market data with OHLCV columns
        trades_df: Optional trades data
        events_df: Optional events data (FVG, pivots)
        title: Chart title

    Returns:
        Plotly Figure object
    """
    # Create candlestick chart
    fig = go.Figure(
        data=go.Candlestick(
            x=data_df["timestamp"] if "timestamp" in data_df.columns else data_df.index,
            open=data_df["open"],
            high=data_df["high"],
            low=data_df["low"],
            close=data_df["close"],
            name="Price",
        )
    )

    # Add trades if provided
    if trades_df is not None and not trades_df.empty:
        # Entry points
        fig.add_trace(
            go.Scatter(
                x=trades_df["entry_time"],
                y=trades_df["entry_price"],
                mode="markers",
                marker={"symbol": "triangle-up", "size": 10, "color": "green"},
                name="Trade Entry",
                hovertemplate="Entry: %{y:.2f}<br>Time: %{x}<extra></extra>",
            )
        )

        # Exit points
        fig.add_trace(
            go.Scatter(
                x=trades_df["exit_time"],
                y=trades_df["exit_price"],
                mode="markers",
                marker={"symbol": "triangle-down", "size": 10, "color": "red"},
                name="Trade Exit",
                hovertemplate="Exit: %{y:.2f}<br>PnL: %{customdata}<extra></extra>",
                customdata=trades_df["pnl"] if "pnl" in trades_df.columns else None,
            )
        )

    # Add FVG events if provided
    if events_df is not None and not events_df.empty:
        fvg_events = (
            events_df[events_df["type"] == "fvg"]
            if "type" in events_df.columns
            else events_df
        )

        for _, event in fvg_events.iterrows():
            color = (
                "rgba(0,255,0,0.3)"
                if event.get("direction") == "bullish"
                else "rgba(255,0,0,0.3)"
            )

            fig.add_shape(
                type="rect",
                x0=event["timestamp"],
                x1=event["timestamp"],  # Will be extended by plotly
                y0=event.get("low", event.get("price", 0)),
                y1=event.get("high", event.get("price", 0)),
                fillcolor=color,
                line={"color": color},
                name=f"FVG {event.get('direction', '')}",
            )

    # Update layout
    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Price",
        template="plotly_dark",
        height=600,
        showlegend=True,
    )

    return fig


def build_static_chart_from_data(
    data_df: pd.DataFrame,
    trades_df: pd.DataFrame | None = None,
    events_df: pd.DataFrame | None = None,
    output_path: str = "chart.png",
    title: str = "Trading Chart",
) -> str:
    """Build static mplfinance chart from DataFrames directly.

    Args:
        data_df: Market data with OHLCV columns
        trades_df: Optional trades data
        events_df: Optional events data
        output_path: Output file path for PNG
        title: Chart title

    Returns:
        Path to saved chart
    """
    try:
        import matplotlib.pyplot as plt
        import mplfinance as mpf
    except ImportError:
        raise ImportError(
            "mplfinance required for static charts. Install with: pip install mplfinance"
        ) from None

    # Prepare data for mplfinance (requires DatetimeIndex)
    df = data_df.copy()
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")

    # Ensure we have the required OHLCV columns
    required_cols = ["open", "high", "low", "close"]
    if not all(col in df.columns for col in required_cols):
        raise ValueError(f"Data must contain columns: {required_cols}")

    # Create additional plots for trades and events
    add_plots = []

    if trades_df is not None and not trades_df.empty:
        # Create trade markers
        trades = trades_df.copy()
        trades["entry_time"] = pd.to_datetime(trades["entry_time"])
        trades["exit_time"] = pd.to_datetime(trades["exit_time"])

        # Add entry/exit points as scatter plots
        for _, trade in trades.iterrows():
            # Find closest data points for entry/exit
            entry_idx = df.index.get_indexer([trade["entry_time"]], method="nearest")[0]
            df.index.get_indexer([trade["exit_time"]], method="nearest")[0]

            if 0 <= entry_idx < len(df):
                add_plots.append(
                    mpf.make_addplot(
                        [trade["entry_price"]] * len(df),
                        type="scatter",
                        markersize=50,
                        marker="^",
                        color="green",
                        alpha=0.7,
                    )
                )

    # Create the plot
    save_config = {"fname": output_path, "dpi": 300, "bbox_inches": "tight"}

    # Use a simpler style configuration
    style = mpf.make_mpf_style(base_mpl_style="dark_background")

    mpf.plot(
        df,
        type="candle",
        style=style,
        title=title,
        ylabel="Price",
        volume=False,
        addplot=add_plots if add_plots else None,
        savefig=save_config,
        show_nontrading=False,
    )

    return output_path


def display_chart_in_chatgpt_from_data(
    data_df: pd.DataFrame,
    trades_df: pd.DataFrame | None = None,
    events_df: pd.DataFrame | None = None,
    title: str = "Trading Chart",
) -> bool:
    """Display chart in ChatGPT environment or fallback to file export.

    Args:
        data_df: Market data with OHLCV columns
        trades_df: Optional trades data
        events_df: Optional events data
        title: Chart title

    Returns:
        True if displayed successfully, False otherwise
    """
    try:
        # Build the chart
        fig = build_plotly_from_data(data_df, trades_df, events_df, title)

        # Check if we're in ChatGPT environment
        if "CHATGPT_ENVIRONMENT" in os.environ:
            try:
                from python_user_visible import display_plotly

                display_plotly(fig)
                return True
            except ImportError:
                print("ChatGPT display not available, saving as HTML...")
                fig.write_html("temp_chart.html")
                print("Chart saved as temp_chart.html")
                return False
        else:
            # Standard environment - show in browser
            fig.show()
            return True

    except Exception as e:
        print(f"Chart display failed: {e}")
        return False
