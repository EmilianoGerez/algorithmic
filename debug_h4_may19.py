#!/usr/bin/env python3
"""Debug H4 FVG detection on May 19 data."""

from datetime import UTC, datetime, timezone

import pandas as pd

from core.detectors.fvg import FVGDetector
from core.entities import Candle


def test_h4_fvg_may19():
    """Test H4 FVG detection on May 19 using actual aggregated data."""
    print("=== H4 FVG Debug for May 19 ===")

    # Load the actual data
    df = pd.read_csv("data/BTCUSDT_5m_may19-20_fvg_analysis.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Aggregate to H4 manually to see what the strategy sees
    df_h4 = df.set_index('timestamp').resample('4H').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()

    print(f"H4 candles available: {len(df_h4)}")
    print("H4 candle data:")
    for i, (ts, row) in enumerate(df_h4.iterrows()):
        print(f"  {i}: {ts} | O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f} C:{row['close']:.2f} V:{row['volume']:.0f}")

    if len(df_h4) < 3:
        print("❌ Not enough H4 candles for FVG detection")
        return

    # Create FVG detector with same settings as config
    detector = FVGDetector("H4", min_gap_atr=0.05, min_gap_pct=0.01, min_rel_vol=0.0)

    # Convert to Candle objects
    candles = []
    for ts, row in df_h4.iterrows():
        candle = Candle(
            ts=ts.tz_localize(UTC) if ts.tz is None else ts,
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close'],
            volume=row['volume']
        )
        candles.append(candle)

    # Process candles through detector
    events = []
    for i, candle in enumerate(candles):
        print(f"\nProcessing H4 candle {i}: {candle.ts}")
        print(f"  OHLCV: {candle.open:.2f}/{candle.high:.2f}/{candle.low:.2f}/{candle.close:.2f}/{candle.volume:.0f}")

        # Use dummy ATR and volume SMA since min_rel_vol=0.0
        atr_value = 1000.0  # Large enough to not block detection
        vol_sma_value = 1000.0  # Not used since min_rel_vol=0.0

        new_events = detector.update(candle, atr_value, vol_sma_value)
        events.extend(new_events)

        print(f"  Events generated: {len(new_events)}")
        for event in new_events:
            print(f"    FVG: {event.side} [{event.bottom:.2f}, {event.top:.2f}] strength={event.strength:.3f}")

    print("\n=== SUMMARY ===")
    print(f"Total H4 FVGs detected: {len(events)}")
    if events:
        print("FVG Details:")
        for i, event in enumerate(events):
            print(f"  {i+1}. {event.ts} {event.side} [{event.bottom:.2f}, {event.top:.2f}] strength={event.strength:.3f}")
    else:
        print("❌ No H4 FVGs detected - this explains why backtesting shows 0 trades")

        # Check for potential issues
        print("\nDiagnostics:")
        if len(candles) >= 3:
            for i in range(2, len(candles)):
                prev = candles[i-2]
                curr = candles[i-1]
                next_candle = candles[i]

                # Check bullish gap: prev.high < next.low
                if prev.high < next_candle.low:
                    gap_size = next_candle.low - prev.high
                    gap_pct = gap_size / prev.close
                    print(f"  Potential bullish FVG at {next_candle.ts}: gap={gap_size:.2f} ({gap_pct*100:.2f}%)")

                # Check bearish gap: prev.low > next.high
                if prev.low > next_candle.high:
                    gap_size = prev.low - next_candle.high
                    gap_pct = gap_size / prev.close
                    print(f"  Potential bearish FVG at {next_candle.ts}: gap={gap_size:.2f} ({gap_pct*100:.2f}%)")

if __name__ == "__main__":
    test_h4_fvg_may19()
