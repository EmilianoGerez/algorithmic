#!/usr/bin/env python3
"""Debug script for pivot detector."""

from datetime import UTC, datetime, timedelta

from core.detectors.pivot import PivotDetector
from core.entities import Candle


def debug_pivot() -> None:
    detector = PivotDetector("H1", lookback_periods=2, min_sigma=0.1)

    base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

    # Major strength pivot (>1 ATR distance)
    candles = [
        Candle(base_time + timedelta(hours=0), 100.0, 102.0, 99.0, 101.0, 1000),
        Candle(base_time + timedelta(hours=1), 101.0, 103.0, 100.0, 102.0, 1000),
        Candle(
            base_time + timedelta(hours=2), 102.0, 120.0, 101.0, 115.0, 1000
        ),  # Major high
        Candle(base_time + timedelta(hours=3), 114.0, 116.0, 113.0, 115.0, 1000),
        Candle(base_time + timedelta(hours=4), 113.0, 115.0, 112.0, 114.0, 1000),
    ]

    # ATR = 10.0 (so 120-103 = 17 = 1.7 ATR distance)
    atr_value = 10.0

    events = []
    for i, candle in enumerate(candles):
        print(f"\nProcessing candle {i}: {candle}")
        new_events = detector.update(candle, atr_value)
        events.extend(new_events)
        for event in new_events:
            print(
                f"  Event: {event.side} at {event.price}, strength={event.strength}, atr_dist={event.atr_distance}"
            )

    print(f"\nTotal events: {len(events)}")
    high_events = [e for e in events if e.side == "high"]
    print(f"High events: {len(high_events)}")

    if high_events:
        event = high_events[0]
        print(
            f"First high event: strength={event.strength}, atr_distance={event.atr_distance}"
        )
        print("Expected: strength='major' (atr_distance >= 1.0)")


if __name__ == "__main__":
    debug_pivot()
