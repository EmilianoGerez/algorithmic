#!/usr/bin/env python3
"""Debug FVG detection."""

from datetime import UTC, datetime, timedelta

from core.detectors.fvg import FVGDetector
from core.entities import Candle


def debug_fvg():
    print("=== FVG Debug ===")
    detector = FVGDetector("H1", min_gap_atr=0.1, min_gap_pct=0.01, min_rel_vol=0.8)

    base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
    candles = [
        Candle(base_time, 100.0, 102.0, 99.0, 101.0, 1000),  # prev: high=102
        Candle(
            base_time + timedelta(hours=1), 101.0, 103.0, 100.0, 102.0, 1000
        ),  # curr
        Candle(
            base_time + timedelta(hours=2), 110.0, 115.0, 108.0, 112.0, 2000
        ),  # next: low=108 > prev.high=102 - GAP!
    ]

    atr_value = 5.0
    vol_sma_value = 1000.0

    print(f"ATR: {atr_value}, Volume SMA: {vol_sma_value}")
    print(f"Gap size: {108 - 102} = 6")
    print(f"Gap size ATR: {(108 - 102) / atr_value} = {6 / 5} = 1.2")
    print(f"Gap size %: {(108 - 102) / 101} = {6 / 101:.4f}")
    print(f"Volume ratio: {2000 / 1000} = 2.0")

    events = []
    for i, candle in enumerate(candles):
        print(f"\nProcessing candle {i}: {candle}")
        new_events = detector.update(candle, atr_value, vol_sma_value)
        events.extend(new_events)
        print(f"  Events generated: {len(new_events)}")
        for event in new_events:
            print(f"    {event}")

    print(f"\nTotal events: {len(events)}")


if __name__ == "__main__":
    debug_fvg()
