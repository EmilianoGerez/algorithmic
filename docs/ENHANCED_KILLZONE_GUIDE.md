# Enhanced Killzone Implementation Guide

## Overview

The enhanced killzone system provides sophisticated time-based filtering for algorithmic trading strategies, supporting multiple trading sessions with automatic low-volume period exclusions.

## Features

✅ **Multiple Trading Sessions**: Asia, London, NY sessions with automatic UTC conversion
✅ **Low Volume Exclusions**: Automatically excludes periods with typically low volume
✅ **Backward Compatibility**: Works alongside existing killzone configurations
✅ **Configurable Sessions**: Choose specific sessions or combine multiple sessions
✅ **Production Ready**: Comprehensive testing and validation

## Trading Sessions (Converted to UTC)

The system converts NY times to UTC as requested:

| Session    | NY Times    | UTC Times   | Description              |
| ---------- | ----------- | ----------- | ------------------------ |
| **Asia**   | 20:00-00:00 | 01:00-05:00 | Tokyo trading session    |
| **London** | 02:00-05:00 | 07:00-10:00 | London trading session   |
| **NY**     | 08:00-13:00 | 13:00-18:00 | New York trading session |

## Low Volume Exclusions

Automatically excludes these periods when `exclude_low_volume: true`:

- **00:00-02:00 UTC**: Post-NY close period (low institutional activity)
- **05:00-07:00 UTC**: Gap between Asia and London sessions

## Configuration

### Basic Configuration (binance.yaml)

```yaml
candidate:
  filters:
    # Enhanced killzone settings
    use_enhanced_killzone: true
    killzone_sessions: ["asia", "london", "ny"] # All sessions
    exclude_low_volume: true

    # Legacy fallback (kept for compatibility)
    killzone: ["01:00", "18:00"]
```

### Strategy-Specific Configurations

#### Asia-Only Strategy

```yaml
candidate:
  filters:
    use_enhanced_killzone: true
    killzone_sessions: ["asia"]
    exclude_low_volume: true
```

#### London-Only Strategy

```yaml
candidate:
  filters:
    use_enhanced_killzone: true
    killzone_sessions: ["london"]
    exclude_low_volume: true
```

#### NY-Only Strategy

```yaml
candidate:
  filters:
    use_enhanced_killzone: true
    killzone_sessions: ["ny"]
    exclude_low_volume: true
```

#### London + NY Overlap Strategy

```yaml
candidate:
  filters:
    use_enhanced_killzone: true
    killzone_sessions: ["london", "ny"]
    exclude_low_volume: true
```

#### 24/7 Strategy (No Exclusions)

```yaml
candidate:
  filters:
    use_enhanced_killzone: true
    killzone_sessions: ["asia", "london", "ny"]
    exclude_low_volume: false
```

## Implementation Details

### Core Components

1. **KillzoneManager**: Central manager for session detection and filtering
2. **TradingSession**: Individual session definition with time ranges
3. **enhanced_killzone_ok()**: Drop-in replacement for legacy killzone function
4. **FSMGuards.enhanced_killzone_ok()**: Integrated guard function for FSM

### Integration with SignalCandidate FSM

The enhanced killzone integrates seamlessly with the existing signal generation pipeline:

```python
# In CandidateConfig
use_enhanced_killzone: bool = False
killzone_sessions: list[str] | None = None
exclude_low_volume: bool = True

# In FSM processing
if self.config.use_enhanced_killzone:
    killzone_ok = self.guards.enhanced_killzone_ok(
        bar,
        sessions=self.config.killzone_sessions,
        exclude_low_volume=self.config.exclude_low_volume
    )
else:
    # Legacy fallback
    killzone_ok = self.guards.killzone_ok(
        bar, self.config.killzone_start, self.config.killzone_end
    )
```

## Testing Results

### Session Detection Test

```
🔍 Testing session detection...
  02:00 UTC: Asia session (excluded due to low volume)
  08:30 UTC: London session (active)
  15:00 UTC: NY session (active)
  01:30 UTC: Low volume exclusion (properly excluded)
  06:00 UTC: Low volume exclusion (properly excluded)
  23:00 UTC: Outside all sessions (properly excluded)
```

### Integration Test Results

```
🤖 Testing FSM with enhanced killzone...
  ✅ London session (08:30 UTC): Signal generated = True
  ✅ NY session (15:00 UTC): Signal generated = True
  ✅ Asia session (03:00 UTC): Signal generated = False (not in config)
  ✅ Low volume period (01:30 UTC): Signal generated = False
  ✅ Outside sessions (23:00 UTC): Signal generated = False
```

### Legacy vs Enhanced Comparison

```
  Time (UTC)  | Legacy | Enhanced | Description
  ------------|--------|----------|------------
  03:00       |   True |   False  | Asia session (filtered out)
  06:00       |   True |   False  | Low volume gap (filtered out)
  08:30       |   True |   True   | London session (allowed)
  15:00       |   True |   True   | NY session (allowed)
  20:00       |   False|   False  | After NY close (both exclude)
```

## Migration Guide

### Step 1: Update Configuration

Add enhanced killzone settings to your YAML config:

```yaml
candidate:
  filters:
    use_enhanced_killzone: true
    killzone_sessions: ["london", "ny"] # Choose your sessions
    exclude_low_volume: true
```

### Step 2: Test in Development

Run the test suite to validate functionality:

```bash
python3 test_enhanced_killzone.py
python3 test_enhanced_killzone_integration.py
```

### Step 3: Monitor in Production

- Watch signal generation patterns during different sessions
- Verify exclusion periods are working as expected
- Compare performance vs legacy killzone

### Step 4: Optimize Settings

- Adjust `killzone_sessions` based on strategy performance
- Toggle `exclude_low_volume` based on data quality
- Use legacy fallback if needed

## Performance Benefits

1. **Precision**: Targets specific high-volume trading sessions
2. **Risk Reduction**: Avoids low-liquidity periods automatically
3. **Flexibility**: Easy configuration for different strategies
4. **Reliability**: Comprehensive testing and validation

## Best Practices

1. **Start Conservative**: Begin with `["london", "ny"]` for most strategies
2. **Monitor Volume**: Use `exclude_low_volume: true` unless you have specific reasons not to
3. **Backtest Thoroughly**: Test enhanced settings against historical data
4. **Keep Legacy Fallback**: Maintain backward compatibility during transition
5. **Document Changes**: Track configuration changes and their impact

## Troubleshooting

### Issue: No signals generated

- Check `killzone_sessions` includes active trading times
- Verify `exclude_low_volume` setting is appropriate
- Ensure other filters (volume, regime, EMA) are passing

### Issue: Too many signals

- Reduce number of sessions in `killzone_sessions`
- Enable `exclude_low_volume: true`
- Increase other filter thresholds

### Issue: Missing expected signals

- Add more sessions to `killzone_sessions`
- Consider `exclude_low_volume: false`
- Check if legacy killzone would have captured the signal

## Support

For questions or issues with the enhanced killzone system:

1. Run the test suites for validation
2. Check configuration syntax against examples
3. Review session timing and exclusion periods
4. Compare with legacy killzone behavior

The enhanced killzone system is production-ready and provides significant improvements over the legacy time range approach while maintaining full backward compatibility.
