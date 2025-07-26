# HTF Detectors Configuration Guide

## Out-of-Order Policy Configuration

The HTF detectors support configurable handling of out-of-sequence candles through the `out_of_order_policy` setting:

```yaml
detectors:
  # Ordering policy for out-of-sequence HTF candles
  out_of_order_policy: "drop"  # "drop" or "raise"

  # Other detector settings...
  fvg:
    min_gap_atr: 0.3
    min_gap_pct: 0.05
    min_rel_vol: 1.2

  pivot:
    lookback: 5
    min_sigma: 0.5
```

### Policy Options:

- **`"drop"`** (default): Silently ignore out-of-order candles
  - ✅ Robust for production environments with clock skew
  - ✅ Matches aggregator behavior for consistency
  - ⚠️ May miss some patterns if data feed has issues

- **`"raise"`**: Throw exception on out-of-order candles
  - ✅ Strict validation for development/testing
  - ✅ Immediate feedback on data quality issues
  - ⚠️ May crash in production with minor clock drift

### Example Usage:

```python
from core.detectors import DetectorManager, DetectorConfig

# Development setup with strict ordering
dev_config = DetectorConfig(
    out_of_order_policy="raise",  # Fail fast on data issues
    enabled_timeframes=["H1"]
)

# Production setup with robust handling
prod_config = DetectorConfig(
    out_of_order_policy="drop",   # Ignore minor clock skew
    enabled_timeframes=["H1", "H4", "D1"]
)

manager = DetectorManager(prod_config)
```

### Performance Notes:

- Out-of-order checking adds minimal overhead (~0.1% performance impact)
- Validation occurs before indicator updates for efficiency
- Logging is conditional and only activates when DEBUG level is enabled

### Related Settings:

The aggregator has similar policies that work in coordination:

```yaml
aggregation:
  out_of_order_policy: "drop"  # Should match detector policy
  max_clock_skew_seconds: 300   # 5-minute tolerance
  enable_strict_ordering: true  # Enable chronological checks
```
