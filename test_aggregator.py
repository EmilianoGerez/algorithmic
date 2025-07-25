"""Test suite for multi-timeframe aggregation components."""

from datetime import UTC, datetime, timedelta

import pytest

from core.entities import Candle
from core.strategy.aggregator import MultiTimeframeAggregator, TimeAggregator
from core.strategy.ring_buffer import CandleBuffer
from core.strategy.timeframe import TimeframeConfig, get_bucket_id, get_bucket_start


class TestTimeframeUtils:
    """Test timeframe utility functions."""

    def test_bucket_id_calculation(self):
        """Test Unix epoch bucket ID calculation."""
        # Test H1 bucket IDs
        dt_1 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)  # 10:00
        dt_2 = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)  # 10:30
        dt_3 = datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC)  # 11:00

        bucket_1 = get_bucket_id(dt_1, TimeframeConfig.H1.minutes)
        bucket_2 = get_bucket_id(dt_2, TimeframeConfig.H1.minutes)
        bucket_3 = get_bucket_id(dt_3, TimeframeConfig.H1.minutes)

        # Same hour should have same bucket
        assert bucket_1 == bucket_2
        # Different hour should have different bucket
        assert bucket_1 != bucket_3
        assert bucket_3 == bucket_1 + 1

    def test_bucket_start_calculation(self):
        """Test bucket start timestamp calculation."""
        dt = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)

        # H1 bucket should start at 10:00
        start_h1 = get_bucket_start(dt, TimeframeConfig.H1.minutes)
        expected_h1 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        assert start_h1 == expected_h1

        # D1 bucket should start at 00:00
        start_d1 = get_bucket_start(dt, TimeframeConfig.D1.minutes)
        expected_d1 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert start_d1 == expected_d1


class TestCandleBuffer:
    """Test ring buffer for candle storage."""

    def test_buffer_basic_operations(self):
        """Test basic append and OHLCV calculation."""
        buffer = CandleBuffer(maxsize=3)

        # Add test candles
        candle1 = Candle(datetime.now(), 100.0, 110.0, 95.0, 105.0, 1000)
        candle2 = Candle(datetime.now(), 105.0, 115.0, 100.0, 110.0, 1500)

        buffer.append(candle1)
        buffer.append(candle2)

        assert len(buffer) == 2

        # Test OHLCV calculation
        open_price, high_price, low_price, close_price, volume = buffer.get_ohlcv()
        assert open_price == 100.0  # First open
        assert high_price == 115.0  # Highest high
        assert low_price == 95.0  # Lowest low
        assert close_price == 110.0  # Last close
        assert volume == 2500  # Sum of volumes

    def test_buffer_overflow(self):
        """Test ring buffer behavior when maxsize exceeded."""
        buffer = CandleBuffer(maxsize=2)

        candle1 = Candle(datetime.now(), 100.0, 110.0, 95.0, 105.0, 1000)
        candle2 = Candle(datetime.now(), 105.0, 115.0, 100.0, 110.0, 1500)
        candle3 = Candle(datetime.now(), 110.0, 120.0, 105.0, 115.0, 2000)

        buffer.append(candle1)
        buffer.append(candle2)
        buffer.append(candle3)  # Should evict candle1

        assert len(buffer) == 2

        # Should only include candle2 and candle3
        open_price, high_price, low_price, close_price, volume = buffer.get_ohlcv()
        assert open_price == 105.0  # candle2 open
        assert close_price == 115.0  # candle3 close
        assert volume == 3500  # candle2 + candle3 volumes


class TestTimeAggregator:
    """Test single timeframe aggregator."""

    def create_test_candles(self, start_time: datetime, count: int) -> list[Candle]:
        """Create sequence of test candles at 1-minute intervals."""
        from datetime import timedelta

        candles = []
        for i in range(count):
            timestamp = start_time + timedelta(minutes=i)
            candle = Candle(
                ts=timestamp,
                open=100.0 + i,
                high=110.0 + i,
                low=95.0 + i,
                close=105.0 + i,
                volume=1000 + i * 100,
            )
            candles.append(candle)
        return candles

    def test_h1_aggregation_basic(self):
        """Test basic H1 aggregation from 1-minute candles."""
        aggregator = TimeAggregator(tf_minutes=60)

        # Create 121 1-minute candles (2 complete hours + 1 minute)
        start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        candles = self.create_test_candles(start_time, 121)

        completed_h1_candles = []

        # Process all candles
        for candle in candles:
            result = aggregator.update(candle)
            completed_h1_candles.extend(result)

        # Should have exactly 2 completed H1 candles
        assert len(completed_h1_candles) == 2

        # Verify first H1 candle (minutes 0-59)
        h1_candle_1 = completed_h1_candles[0]
        assert h1_candle_1.ts == datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        assert h1_candle_1.open == 100.0  # First minute open
        assert h1_candle_1.close == 164.0  # Last minute (59) close: 105 + 59
        assert h1_candle_1.high == 169.0  # Highest high: 110 + 59
        assert h1_candle_1.low == 95.0  # Lowest low: 95 + 0

        # Verify second H1 candle (minutes 60-119)
        h1_candle_2 = completed_h1_candles[1]
        assert h1_candle_2.ts == datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC)
        assert h1_candle_2.open == 160.0  # Minute 60 open: 100 + 60
        assert h1_candle_2.close == 224.0  # Minute 119 close: 105 + 119

    def test_aggregation_properties(self):
        """Test aggregator properties and metadata."""
        aggregator = TimeAggregator(tf_minutes=240)  # H4

        assert aggregator.name == "H4"
        assert aggregator.candles_per_period == 240  # 240 minutes / 1 minute
        assert aggregator.tf_minutes == 240
        assert aggregator.source_tf_minutes == 1

    def test_incomplete_period_not_emitted(self):
        """Test that incomplete periods are not emitted."""
        aggregator = TimeAggregator(tf_minutes=60)

        # Create only 30 minutes of data (incomplete hour)
        start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        candles = self.create_test_candles(start_time, 30)

        completed_candles = []
        for candle in candles:
            result = aggregator.update(candle)
            completed_candles.extend(result)

        # No complete periods yet
        assert len(completed_candles) == 0

    def test_flush_complete_period(self):
        """Test flushing complete periods at stream end."""
        aggregator = TimeAggregator(tf_minutes=60)

        # Create exactly 60 minutes (complete period)
        start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        candles = self.create_test_candles(start_time, 60)

        # Process candles (should not emit during processing)
        for candle in candles:
            result = aggregator.update(candle)
            assert len(result) == 0

        # Flush should emit the complete period
        flushed = aggregator.flush()
        assert len(flushed) == 1

        h1_candle = flushed[0]
        assert h1_candle.open == 100.0
        assert h1_candle.close == 164.0  # 105 + 59

    def test_flush_incomplete_period_discarded(self):
        """Test that incomplete periods are discarded on flush."""
        aggregator = TimeAggregator(tf_minutes=60)

        # Create 30 minutes (incomplete period)
        start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        candles = self.create_test_candles(start_time, 30)

        for candle in candles:
            aggregator.update(candle)

        # Flush should not emit incomplete period
        flushed = aggregator.flush()
        assert len(flushed) == 0

    def test_reset_clears_state(self):
        """Test reset functionality."""
        aggregator = TimeAggregator(tf_minutes=60)

        # Add some data
        start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        candles = self.create_test_candles(start_time, 30)

        for candle in candles:
            aggregator.update(candle)

        # Reset should clear all state
        aggregator.reset()

        # Should be able to start fresh
        new_candles = self.create_test_candles(start_time, 60)
        for candle in new_candles:
            aggregator.update(candle)

        flushed = aggregator.flush()
        assert len(flushed) == 1  # Should work normally after reset

    def test_validation_errors(self):
        """Test input validation."""
        with pytest.raises(ValueError, match="tf_minutes must be positive"):
            TimeAggregator(tf_minutes=0)

        with pytest.raises(ValueError, match="source_tf_minutes must be positive"):
            TimeAggregator(tf_minutes=60, source_tf_minutes=0)

        with pytest.raises(ValueError, match="Target timeframe must be >= source"):
            TimeAggregator(tf_minutes=30, source_tf_minutes=60)


class TestMultiTimeframeAggregator:
    """Test multi-timeframe aggregator."""

    def create_test_candles(self, start_time: datetime, count: int) -> list[Candle]:
        """Create sequence of test candles at 1-minute intervals."""
        from datetime import timedelta

        candles = []
        for i in range(count):
            timestamp = start_time + timedelta(minutes=i)
            candle = Candle(
                ts=timestamp,
                open=100.0 + i,
                high=110.0 + i,
                low=95.0 + i,
                close=105.0 + i,
                volume=1000,
            )
            candles.append(candle)
        return candles

    def test_multiple_timeframes(self):
        """Test aggregation across multiple timeframes."""
        # H1 and H4 aggregation
        multi_agg = MultiTimeframeAggregator([60, 240])

        assert "H1" in multi_agg.timeframe_names
        assert "H4" in multi_agg.timeframe_names

        # Create 5 hours of data (300 minutes)
        start_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)  # Start at 8:00
        candles = self.create_test_candles(start_time, 300)

        all_results = []
        for candle in candles:
            results = multi_agg.update(candle)
            all_results.append(results)

        # Count completed candles by timeframe
        h1_count = sum(len(results.get("H1", [])) for results in all_results)
        h4_count = sum(len(results.get("H4", [])) for results in all_results)

        # Should have 4 complete H1 candles (hours 8, 9, 10, 11)
        # 12:00-12:59 is incomplete
        assert h1_count == 4

        # Should have 1 complete H4 candle (8:00-11:59)
        # 12:00-15:59 is incomplete
        assert h4_count == 1

    def test_flush_all(self):
        """Test flushing all timeframes."""
        multi_agg = MultiTimeframeAggregator([60, 240])

        # Create exactly 4 hours of data
        start_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)
        candles = self.create_test_candles(start_time, 240)  # 4 hours

        for candle in candles:
            multi_agg.update(candle)

        # Flush should emit final complete periods
        final_results = multi_agg.flush_all()

        # Should have final candles for both timeframes
        assert len(final_results["H1"]) == 1  # Final H1 (11:00-11:59)
        assert len(final_results["H4"]) == 1  # Final H4 (8:00-11:59)

    def test_reset_all(self):
        """Test resetting all aggregators."""
        multi_agg = MultiTimeframeAggregator([60, 240])

        # Add some data
        start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        candles = self.create_test_candles(start_time, 60)

        for candle in candles:
            multi_agg.update(candle)

        # Reset all
        multi_agg.reset_all()

        # Should be able to start fresh
        for candle in candles:
            multi_agg.update(candle)

        results = multi_agg.flush_all()
        assert len(results["H1"]) == 1  # Should work normally after reset

    def test_validation_errors(self):
        """Test multi-aggregator validation."""
        with pytest.raises(
            ValueError, match="At least one timeframe must be specified"
        ):
            MultiTimeframeAggregator([])


class TestRealWorldScenarios:
    """Test realistic trading scenarios."""

    def test_market_hours_aggregation(self):
        """Test aggregation during typical market hours."""
        from datetime import timedelta

        # 9:30 AM to 4:00 PM ET market hours (6.5 hours = 390 minutes)
        aggregator = TimeAggregator(tf_minutes=60)

        start_time = datetime(2024, 1, 1, 14, 30, 0, tzinfo=UTC)  # 9:30 AM ET

        candles = []
        for i in range(390):  # 6.5 hours of minutes
            timestamp = start_time + timedelta(minutes=i)

            candle = Candle(
                ts=timestamp,
                open=100.0 + (i * 0.1),
                high=101.0 + (i * 0.1),
                low=99.0 + (i * 0.1),
                close=100.5 + (i * 0.1),
                volume=1000,
            )
            candles.append(candle)

        completed_candles = []
        for candle in candles:
            result = aggregator.update(candle)
            completed_candles.extend(result)

        # Should complete 6 full hours
        assert len(completed_candles) == 6

    def test_weekend_gap_handling(self):
        """Test handling gaps in data (weekends, holidays)."""
        aggregator = TimeAggregator(tf_minutes=60)

        # Friday data
        friday = datetime(2024, 1, 5, 20, 0, 0, tzinfo=UTC)  # Friday 8 PM
        friday_candles = []
        for i in range(60):
            candle = Candle(
                ts=friday.replace(minute=i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
            )
            friday_candles.append(candle)

        # Monday data (gap over weekend)
        monday = datetime(2024, 1, 8, 1, 0, 0, tzinfo=UTC)  # Monday 1 AM
        monday_candles = []
        for i in range(60):
            candle = Candle(
                ts=monday.replace(minute=i),
                open=102.0,
                high=103.0,
                low=101.0,
                close=102.5,
                volume=1500,
            )
            monday_candles.append(candle)

        completed_candles = []

        # Process Friday data
        for candle in friday_candles:
            result = aggregator.update(candle)
            completed_candles.extend(result)

        # Process Monday data (should trigger Friday completion)
        for candle in monday_candles:
            result = aggregator.update(candle)
            completed_candles.extend(result)

        # Should have Friday H1 candle completed when Monday starts
        assert len(completed_candles) >= 1
        friday_h1 = completed_candles[0]
        assert friday_h1.open == 100.0
        assert friday_h1.close == 100.5

    def test_weekend_gap_d1_aggregation(self):
        """Test D1 aggregation with weekend gap produces single wide candle."""
        aggregator = TimeAggregator(tf_minutes=1440)  # D1 aggregator

        # Friday data - create a full day of data
        friday = datetime(2024, 1, 5, 0, 0, 0, tzinfo=UTC)  # Friday
        friday_candles = []
        for i in range(1440):  # Full day = 1440 minutes
            timestamp = friday + timedelta(minutes=i)
            candle = Candle(
                ts=timestamp,
                open=100.0 + (i * 0.001),  # Gradual price movement
                high=100.5 + (i * 0.001),
                low=99.5 + (i * 0.001),
                close=100.2 + (i * 0.001),
                volume=1000,
            )
            friday_candles.append(candle)

        # Monday data - after 48-hour weekend gap
        monday = datetime(2024, 1, 8, 0, 0, 0, tzinfo=UTC)  # Monday
        monday_candles = []
        for i in range(1440):  # Full day
            timestamp = monday + timedelta(minutes=i)
            candle = Candle(
                ts=timestamp,
                open=102.0 + (i * 0.001),
                high=102.5 + (i * 0.001),
                low=101.5 + (i * 0.001),
                close=102.2 + (i * 0.001),
                volume=1200,
            )
            monday_candles.append(candle)

        completed_candles = []

        # Process Friday (should not complete until Monday starts)
        for candle in friday_candles:
            result = aggregator.update(candle)
            completed_candles.extend(result)

        # No D1 should be completed yet
        assert len(completed_candles) == 0

        # Process Monday data - should trigger Friday D1 completion
        for candle in monday_candles:
            result = aggregator.update(candle)
            completed_candles.extend(result)

        # Should have exactly one Friday D1 candle despite weekend gap
        assert len(completed_candles) == 1

        friday_d1 = completed_candles[0]
        # Should represent Friday's date (2024-01-05)
        assert friday_d1.ts.date() == datetime(2024, 1, 5).date()

        # OHLCV should reflect full Friday trading session
        assert friday_d1.open == 100.0  # First minute open
        assert abs(friday_d1.close - 101.639) < 1e-10  # Last minute close (100.2 + 1439*0.001)
        assert friday_d1.volume == 1440000  # Sum of all Friday volumes

        # The weekend gap doesn't create an artificial wide candle
        # - it's just one complete D1 period for Friday

    def test_dst_fallback_hour_handling(self):
        """Test DST fall-back hour with repeated timestamps (UTC epoch prevents issues)."""
        aggregator = TimeAggregator(tf_minutes=60)  # H1 aggregator

        # Simulate the DST "fall back" scenario where local time repeats
        # but UTC epoch time is always increasing
        # November 3, 2024 - DST ends at 2:00 AM, clocks "fall back" to 1:00 AM

        base_utc = datetime(2024, 11, 3, 6, 0, 0, tzinfo=UTC)  # 6:00 UTC

        # Create 180 minutes of data crossing the problematic local time period
        # This represents 3 hours of UTC time, should produce 3 H1 candles
        candles = []
        for i in range(180):
            timestamp = base_utc + timedelta(minutes=i)
            candle = Candle(
                ts=timestamp,
                open=100.0 + i * 0.01,
                high=101.0 + i * 0.01,
                low=99.0 + i * 0.01,
                close=100.5 + i * 0.01,
                volume=1000
            )
            candles.append(candle)

        completed_candles = []
        for candle in candles:
            result = aggregator.update(candle)
            completed_candles.extend(result)

        # Should get exactly 2 complete H1 candles (hours 6-7 and 7-8 UTC)
        # The third hour (8-9) is incomplete with only 60 minutes
        assert len(completed_candles) == 2

        # Verify proper UTC-based bucketing (not affected by local DST)
        h1_candle_1 = completed_candles[0]
        h1_candle_2 = completed_candles[1]

        assert h1_candle_1.ts == datetime(2024, 11, 3, 6, 0, 0, tzinfo=UTC)
        assert h1_candle_2.ts == datetime(2024, 11, 3, 7, 0, 0, tzinfo=UTC)

        # OHLCV should be correctly aggregated despite any local time ambiguity
        assert h1_candle_1.open == 100.0  # First minute
        assert h1_candle_1.close == 101.09  # 60th minute: 100.5 + 59*0.01
        assert h1_candle_1.volume == 60000  # 60 minutes * 1000 volume

    def test_out_of_order_bars_policy(self):
        """Test handling of out-of-order bars (late delivery from WebSocket reconnect)."""
        aggregator = TimeAggregator(tf_minutes=60)  # H1 aggregator

        # Create a normal sequence of bars
        base_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)

        # Send bars 0-58 in order
        in_order_candles = []
        for i in range(60):  # 0 to 59
            timestamp = base_time + timedelta(minutes=i)
            candle = Candle(
                ts=timestamp,
                open=100.0 + i,
                high=110.0 + i,
                low=95.0 + i,
                close=105.0 + i,
                volume=1000
            )
            in_order_candles.append(candle)

        # Now send a late bar from earlier in the same bucket (out of order)
        late_candle = Candle(
            ts=base_time + timedelta(minutes=30),  # Bar for 10:30, arrives late
            open=130.5,  # Different values from the "in-order" bar 30
            high=140.5,
            low=125.5,
            close=135.5,
            volume=1200
        )

        completed_candles = []

        # Process in-order bars (all 60 candles)
        for candle in in_order_candles:
            result = aggregator.update(candle)
            completed_candles.extend(result)

        # Send one bar from next hour to trigger completion
        next_hour_candle = Candle(
            ts=base_time + timedelta(minutes=60),  # 11:00 (next hour)
            open=200.0,
            high=210.0,
            low=195.0,
            close=205.0,
            volume=1000
        )
        result = aggregator.update(next_hour_candle)
        completed_candles.extend(result)

        # Should have 1 completed H1 candle after crossing to next hour
        assert len(completed_candles) == 1
        h1_candle = completed_candles[0]

        # Record the OHLCV before late bar
        original_open = h1_candle.open
        original_high = h1_candle.high
        original_low = h1_candle.low
        original_close = h1_candle.close
        original_volume = h1_candle.volume

        # Now send the late bar (POLICY DECISION: DROP OUT-OF-ORDER BARS)
        # This prevents re-aggregation complexity and maintains deterministic results
        result_late = aggregator.update(late_candle)

        # Late bar should be dropped (no new completions, existing candle unchanged)
        assert len(result_late) == 0
        assert len(completed_candles) == 1  # Still only 1 candle

        # Original H1 candle should be unchanged (late bar dropped)
        assert h1_candle.open == original_open
        assert h1_candle.high == original_high
        assert h1_candle.low == original_low
        assert h1_candle.close == original_close
        assert h1_candle.volume == original_volume

        # POLICY JUSTIFICATION:
        # - Prevents unbounded memory growth tracking "still open" historical buckets
        # - Maintains deterministic output regardless of delivery order
        # - Simplifies downstream processing (no need to handle candle "updates")
        # - Trading systems should handle feed reliability at the connection layer

    def test_stream_termination_mid_bucket(self):
        """Test that incomplete buckets are discarded on stream termination."""
        aggregator = TimeAggregator(tf_minutes=60)  # H1 aggregator

        # Send exactly 59 bars (1 minute short of complete H1)
        base_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        incomplete_candles = []

        for i in range(59):  # 0 to 58 (missing minute 59)
            timestamp = base_time + timedelta(minutes=i)
            candle = Candle(
                ts=timestamp,
                open=100.0 + i,
                high=110.0 + i,
                low=95.0 + i,
                close=105.0 + i,
                volume=1000
            )
            incomplete_candles.append(candle)

        completed_during_stream = []

        # Process all 59 bars
        for candle in incomplete_candles:
            result = aggregator.update(candle)
            completed_during_stream.extend(result)

        # Should have NO completed H1 candles during processing
        assert len(completed_during_stream) == 0

        # Simulate stream termination - try to flush incomplete period
        flushed_candles = aggregator.flush()

        # Should have NO candles from flush (incomplete period discarded)
        assert len(flushed_candles) == 0

        # Total candles emitted should be 0
        total_emitted = len(completed_during_stream) + len(flushed_candles)
        assert total_emitted == 0

        # POLICY VERIFICATION:
        # - Incomplete periods are never emitted (prevents look-ahead bias)
        # - Stream termination doesn't force emission of partial data
        # - Trading systems get clean, complete candles only
