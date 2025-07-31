#!/usr/bin/env python3
"""
Debug script to identify the FSM parameter issue causing the 'close' attribute error.
"""

import sys
import traceback
from datetime import UTC, datetime, timezone
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, ".")

from core.entities import Candle
from core.indicators.snapshot import IndicatorSnapshot
from core.strategy.signal_candidate import (
    CandidateConfig,
    CandidateState,
    SignalCandidateFSM,
)
from core.strategy.signal_models import SignalCandidate, SignalDirection, ZoneType


def create_mock_candle(close_price: float = 105000.0):
    """Create a mock candle with the given close price."""
    return Candle(
        ts=datetime(2025, 5, 20, 14, 20, tzinfo=UTC),
        open=close_price - 10,
        high=close_price + 20,
        low=close_price - 30,
        close=close_price,
        volume=1000.0,
    )


def create_mock_snapshot():
    """Create a mock indicator snapshot."""
    return IndicatorSnapshot(
        timestamp=datetime(2025, 5, 20, 14, 20, tzinfo=UTC),
        ema21=104900.0,
        ema50=104800.0,
        volume_sma=500.0,
        atr=100.0,
        regime=None,
        regime_with_slope=None,
        current_volume=1000.0,
        current_close=105000.0,
    )


def create_test_candidate():
    """Create a test candidate in WAIT_EMA state."""
    return SignalCandidate(
        candidate_id="test_candidate_001",
        zone_id="test_zone_H4",
        zone_type=ZoneType.POOL,
        direction=SignalDirection.LONG,
        entry_price=104950.0,
        strength=0.75,
        state=CandidateState.WAIT_EMA,
        created_at=datetime(2025, 5, 20, 14, 15, tzinfo=UTC),
        expires_at=datetime(2025, 5, 20, 16, 15, tzinfo=UTC),
        last_bar_timestamp=None,
    )


def test_fsm_call():
    """Test the FSM process method to identify parameter order issues."""
    print("=== FSM Debug Test ===")

    # Create test objects
    config = CandidateConfig(
        expiry_minutes=120,
        ema_alignment=True,
        ema_tolerance_pct=0.0,
        linger_minutes=30,
        reclaim_requires_ema=True,
        volume_multiple=0,
        killzone_start="01:00",
        killzone_end="18:00",
        regime_allowed=["bull", "neutral", "bear"],
    )

    fsm = SignalCandidateFSM(config, symbol="BTCUSDT", timeframe="5m")
    candidate = create_test_candidate()
    candle = create_mock_candle()
    snapshot = create_mock_snapshot()

    print(f"FSM created with symbol: {fsm.symbol}, timeframe: {fsm.timeframe}")
    print(f"Candidate state: {candidate.state}")
    print(f"Candle close: {candle.close}")
    print(f"Snapshot EMA21: {snapshot.ema21}")

    try:
        # Call the FSM process method
        print("\nCalling fsm.process()...")
        result = fsm.process(candidate, candle, snapshot)
        print(f"✅ FSM process successful! New state: {result.updated_candidate.state}")

    except Exception as e:
        print(f"❌ FSM process failed: {e}")
        print("\nFull stack trace:")
        traceback.print_exc()

        # Try to identify where the error comes from
        print(f"\nError type: {type(e).__name__}")
        if "'IndicatorSnapshot' object has no attribute 'close'" in str(e):
            print("🔍 This is the exact error we're looking for!")
            print(
                "The issue is that an IndicatorSnapshot is being passed where a Candle is expected."
            )


if __name__ == "__main__":
    test_fsm_call()
