"""
Data export utilities for backtest visualization.

Generates the required data files for visualization:
- data.csv: Market data (OHLCV)
- trades.csv: Trade execution data
- events.parquet: Strategy events (FVG, Pivots, etc.)
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any


class BacktestDataExporter:
    """Export backtest data for visualization."""

    def __init__(self, output_dir: Path):
        """Initialize exporter with output directory.

        Args:
            output_dir: Directory to save visualization data files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.data_path = self.output_dir / "data.csv"
        self.trades_path = self.output_dir / "trades.csv"
        self.events_path = self.output_dir / "events.parquet"

        # Initialize files
        self._init_data_file()
        self._init_trades_file()
        self.events_data: list[dict[str, Any]] = []

    def _init_data_file(self) -> None:
        """Initialize market data CSV file."""
        with open(self.data_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])

    def _init_trades_file(self) -> None:
        """Initialize trades CSV file."""
        with open(self.trades_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "id",
                    "symbol",
                    "side",
                    "entry_ts",
                    "exit_ts",
                    "entry_price",
                    "exit_price",
                    "size",
                    "pnl",
                    "fees",
                    "duration_minutes",
                    "exit_reason",
                ]
            )

    def add_candle(
        self,
        timestamp: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float = 0.0,
    ) -> None:
        """Add market data candle to data.csv.

        Args:
            timestamp: Candle timestamp
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume (optional)
        """
        with open(self.data_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [timestamp.isoformat(), open_price, high, low, close, volume]
            )

    def add_trade(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        entry_ts: datetime,
        exit_ts: datetime,
        entry_price: float,
        exit_price: float,
        size: float,
        pnl: float,
        fees: float = 0.0,
        exit_reason: str = "",
    ) -> None:
        """Add trade to trades.csv.

        Args:
            trade_id: Unique trade identifier
            symbol: Trading symbol
            side: Trade side (BUY/SELL)
            entry_ts: Entry timestamp
            exit_ts: Exit timestamp
            entry_price: Entry price
            exit_price: Exit price
            size: Position size
            pnl: Profit/loss
            fees: Trading fees
            exit_reason: Reason for exit (take_profit, stop_loss, etc.)
        """
        duration_minutes = (exit_ts - entry_ts).total_seconds() / 60.0

        with open(self.trades_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    trade_id,
                    symbol,
                    side,
                    entry_ts.isoformat(),
                    exit_ts.isoformat(),
                    entry_price,
                    exit_price,
                    size,
                    pnl,
                    fees,
                    duration_minutes,
                    exit_reason,
                ]
            )

    def add_event(self, event_type: str, timestamp: datetime, **kwargs: Any) -> None:
        """Add strategy event for events.parquet.

        Args:
            event_type: Type of event (FVGEvent, PivotEvent, etc.)
            timestamp: Event timestamp
            **kwargs: Additional event data
        """
        event_data = {"type": event_type, "ts": timestamp.isoformat(), **kwargs}
        self.events_data.append(event_data)

    def add_fvg_event(
        self,
        timestamp: datetime,
        top: float,
        bottom: float,
        timeframe: str = "1m",
        strength: float = 1.0,
    ) -> None:
        """Add FVG (Fair Value Gap) event.

        Args:
            timestamp: FVG detection timestamp
            top: Top of FVG zone
            bottom: Bottom of FVG zone
            timeframe: Timeframe where FVG was detected
            strength: FVG strength/confidence
        """
        self.add_event(
            event_type="FVGEvent",
            timestamp=timestamp,
            top=top,
            bottom=bottom,
            timeframe=timeframe,
            strength=strength,
        )

    def add_pivot_event(
        self,
        timestamp: datetime,
        price: float,
        side: str,
        strength: float = 1.0,
        atr_distance: float = 0.0,
    ) -> None:
        """Add Pivot event.

        Args:
            timestamp: Pivot detection timestamp
            price: Pivot price level
            side: Pivot side (high/low)
            strength: Pivot strength
            atr_distance: Distance in ATR units
        """
        self.add_event(
            event_type="PivotEvent",
            timestamp=timestamp,
            price=price,
            side=side,
            strength=strength,
            atr_distance=atr_distance,
        )

    def finalize_events(self) -> None:
        """Save events data to parquet file."""
        if not self.events_data:
            return

        try:
            import pandas as pd

            # Convert to DataFrame
            events_df = pd.DataFrame(self.events_data)

            # Save to parquet
            events_df.to_parquet(self.events_path, index=False)

        except ImportError:
            print("Warning: pandas not available, events.parquet not created")
        except Exception as e:
            print(f"Warning: Could not save events.parquet: {e}")

    def get_file_paths(self) -> dict[str, Path]:
        """Get paths to all generated files.

        Returns:
            Dictionary with file paths
        """
        return {
            "data_path": self.data_path,
            "trades_path": self.trades_path,
            "events_path": self.events_path,
        }
