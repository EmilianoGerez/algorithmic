# Clock-Skew Guardrails Implementation Summary

## Overview

Enhanced the TimeAggregator with configurable clock-skew and ordering guardrails to handle production edge cases like out-of-order candles and timestamp drift.

## New Features Added

### 1. CandleEvent Type Alias

- Added `CandleEvent = tuple[str, Candle]` for cleaner method signatures
- Updated `update_with_label()` method to use the new type alias
- Improves code readability and type annotations

### 2. Clock-Skew Guardrails

- **OutOfOrderPolicy Enum**: Configurable behavior for out-of-order candles

  - `DROP`: Silently ignore (default, prevents memory growth)
  - `RAISE`: Throw ClockSkewError exception
  - `RECALC`: Process anyway (expensive but most accurate)

- **ClockSkewError Exception**: Specific exception for timing violations

### 3. Configuration Parameters

- `out_of_order_policy`: How to handle out-of-order candles
- `max_clock_skew_seconds`: Maximum allowed timestamp drift (default: 300s/5min)
- `enable_strict_ordering`: Whether to enforce chronological order (default: True)

### 4. Validation Logic

- Future candle detection (excessive clock skew)
- Chronological ordering checks
- Configurable behavior for violations
- Type-safe timestamp conversion (datetime → unix timestamp)

## Configuration

Updated `configs/base.yaml` with new settings:

```yaml
aggregation:
  # Clock-skew and ordering policies
  out_of_order_policy: "drop" # "drop", "raise", or "recalc"
  max_clock_skew_seconds: 300 # Maximum allowed time drift (5 minutes)
  enable_strict_ordering: true # Enforce chronological order
```

## API Changes

- `TimeAggregator` constructor accepts new clock-skew parameters
- `TimeAggregator.from_timeframe()` accepts new clock-skew parameters
- `MultiTimeframeAggregator` passes through clock-skew settings to all timeframes
- `update_with_label()` returns `list[CandleEvent]` instead of `list[tuple[str, Candle]]`

## Testing

- Comprehensive test suite in `test_clock_skew_guardrails.py`
- Tests for DROP, RAISE, and disabled ordering policies
- Future candle detection validation
- All pre-commit hooks passing (ruff, mypy, formatting)

## Backward Compatibility

- All existing functionality preserved
- Default behavior unchanged (DROP policy maintains original logic)
- No breaking changes to existing APIs
- Optional parameters with sensible defaults

## Production Benefits

1. **Robust Error Handling**: Configurable responses to data quality issues
2. **Explicit Behavior**: No surprises with out-of-order data
3. **Memory Safety**: DROP policy prevents unbounded growth
4. **Type Safety**: Clean annotations with CandleEvent alias
5. **Configurability**: Easy to adjust behavior per environment

The implementation successfully adds production-grade guardrails while maintaining the high-performance characteristics and clean API design of the Phase 2 TimeAggregator.
