#!/usr/bin/env python3
"""Debug DetectorManager integration."""

from datetime import UTC, datetime, timedelta

from core.detectors.manager import DetectorConfig, DetectorManager
from core.entities import Candle


def debug_manager():
    print("=== DetectorManager Debug ===")

    config = DetectorConfig(
        enabled_timeframes=["H1"],
        fvg_min_gap_atr=0.1,
        fvg_min_gap_pct=0.01,
        fvg_min_rel_vol=0.8,
        atr_period=3,
        volume_sma_period=3,
    )

    manager = DetectorManager(config)

    base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
    candles = [
        Candle(base_time, 100.0, 102.0, 99.0, 101.0, 1000),  # prev: high=102
        Candle(
            base_time + timedelta(hours=1), 101.0, 103.0, 100.0, 102.0, 1000
        ),  # curr
        Candle(
            base_time + timedelta(hours=2), 110.0, 115.0, 108.0, 112.0, 2000
        ),  # next: low=108 > prev.high=102 - GAP!
        Candle(
            base_time + timedelta(hours=3), 111.0, 114.0, 110.0, 113.0, 1800
        ),  # trigger analysis
    ]

    events = []
    for i, candle in enumerate(candles):
        print(f"\nProcessing candle {i+1}: {candle}")

        # Check indicator status
        atr_ind = manager._atr_indicators["H1"]
        vol_ind = manager._volume_sma_indicators["H1"]

        print(
            f"  Before update - ATR ready: {atr_ind.is_ready}, Vol ready: {vol_ind.is_ready}"
        )
        if atr_ind.is_ready:
            print(f"  ATR value: {atr_ind.value}")
        if vol_ind.is_ready:
            print(f"  Vol SMA value: {vol_ind.value}")

        new_events = manager.update("H1", candle)
        events.extend(new_events)

        print(
            f"  After update - ATR ready: {atr_ind.is_ready}, Vol ready: {vol_ind.is_ready}"
        )
        if atr_ind.is_ready:
            print(f"  ATR value: {atr_ind.value}")
        if vol_ind.is_ready:
            print(f"  Vol SMA value: {vol_ind.value}")

        print(f"  Events generated: {len(new_events)}")
        for event in new_events:
            print(f"    {event}")

        # Debug FVG detector directly
        if atr_ind.is_ready and vol_ind.is_ready:
            fvg_detector = manager._fvg_detectors["H1"]
            print(f"  FVG buffer size: {len(fvg_detector._buffer)}")
            if len(fvg_detector._buffer) >= 3:
                prev, _, next_candle = (
                    fvg_detector._buffer[-3],
                    fvg_detector._buffer[-2],
                    fvg_detector._buffer[-1],
                )
                print(
                    f"    Analyzing: prev.high={prev.high}, next.low={next_candle.low}"
                )
                print(
                    f"    Gap exists: {prev.high < next_candle.low} ({prev.high} < {next_candle.low})"
                )
                if prev.high < next_candle.low:
                    gap_size = next_candle.low - prev.high
                    gap_size_atr = gap_size / atr_ind.value
                    gap_size_pct = gap_size / prev.close
                    rel_vol = next_candle.volume / vol_ind.value
                    print(
                        f"    Gap size: {gap_size}, ATR: {gap_size_atr:.3f}, Pct: {gap_size_pct:.3f}, Vol: {rel_vol:.3f}"
                    )
                    print(
                        f"    Thresholds: ATR>={config.fvg_min_gap_atr}, Pct>={config.fvg_min_gap_pct}, Vol>={config.fvg_min_rel_vol}"
                    )
                    print(f"    Pass ATR: {gap_size_atr >= config.fvg_min_gap_atr}")
                    print(f"    Pass Pct: {gap_size_pct >= config.fvg_min_gap_pct}")
                    print(f"    Pass Vol: {rel_vol >= config.fvg_min_rel_vol}")
                    print(
                        f"    Pass OR logic: {gap_size_atr >= config.fvg_min_gap_atr or gap_size_pct >= config.fvg_min_gap_pct}"
                    )
                    print(
                        f"    Pass overall: {(gap_size_atr >= config.fvg_min_gap_atr or gap_size_pct >= config.fvg_min_gap_pct) and rel_vol >= config.fvg_min_rel_vol}"
                    )

    print(f"\nTotal events: {len(events)}")


if __name__ == "__main__":
    debug_manager()
