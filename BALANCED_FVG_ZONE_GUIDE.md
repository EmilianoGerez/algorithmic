# Balanced FVG and Zone Watcher Configuration Guide

## 🎯 Executive Summary

Your current configuration is **VERY SENSITIVE** and may be generating too many weak signals. This guide provides balanced alternatives that focus on **quality over quantity**.

## 📊 Current Configuration Analysis

### FVG Detection - VERY HIGH Sensitivity ⚠️

```yaml
Current Settings (VERY SENSITIVE):
  min_gap_atr: 0.05 # Catches micro-gaps (1/20th of ATR)
  min_gap_pct: 0.01 # 1% price gaps (tiny movements)
  min_rel_vol: 0.0 # Volume filtering DISABLED
  strength_threshold: 0.35 # LOW quality filter

Issues:
  - Catches every tiny price gap (noise)
  - No volume confirmation (weak signals)
  - May overwhelm with too many low-quality signals
```

### Zone Watcher - VERY HIGH Sensitivity ⚠️

```yaml
Current Settings (VERY SENSITIVE):
  price_tolerance: 0.0 # Exact hits only
  min_strength: 0.01 # Tracks very weak zones
  expiry_minutes: 120 # 2 hours (might be too short)

Issues:
  - min_strength too low (FVG strengths are 0.07-0.53)
  - No tolerance for normal market noise
  - Short expiry may miss slower developments
```

## 🎯 Recommended Balanced Configuration

### Option 1: BALANCED (Recommended for most users)

```yaml
detectors:
  fvg:
    min_gap_atr: 0.2 # 4x more selective (20% of ATR)
    min_gap_pct: 0.03 # 3x more selective (3% gaps)
    min_rel_vol: 1.5 # Enable volume filter (50% above average)

pools:
  strength_threshold: 0.4 # Slightly higher quality

zone_watcher:
  price_tolerance: 0.1 # Allow slight market noise
  min_strength: 0.3 # 30x higher (meaningful zones only)

candidate:
  expiry_minutes: 180 # 3 hours (50% longer)
  min_entry_spacing_minutes: 45 # More spacing
```

**Expected Impact:**

- 🔻 50-70% fewer FVG detections (but higher quality)
- 🔻 90% fewer zone triggers (only strong zones)
- 🔺 Better signal-to-noise ratio
- 🔺 More reliable entries

### Option 2: CONSERVATIVE (High quality, fewer signals)

```yaml
detectors:
  fvg:
    min_gap_atr: 0.25 # Even more selective
    min_gap_pct: 0.04 # 4% minimum gaps
    min_rel_vol: 1.8 # High volume requirement

zone_watcher:
  min_strength: 0.4 # Only strong zones
  price_tolerance: 0.05 # Tight tolerance
```

### Option 3: AGGRESSIVE (More signals, some noise)

```yaml
detectors:
  fvg:
    min_gap_atr: 0.15 # More sensitive than balanced
    min_gap_pct: 0.025 # 2.5% gaps
    min_rel_vol: 1.2 # Moderate volume filter

zone_watcher:
  min_strength: 0.2 # Lower strength threshold
  price_tolerance: 0.15 # More tolerance
```

## 🔧 Implementation Options

### Quick Update (Recommended)

```bash
# Apply balanced settings (creates automatic backup)
python update_fvg_zone_config.py --profile balanced

# See what would change first (dry run)
python update_fvg_zone_config.py --profile balanced --dry-run

# Apply conservative settings instead
python update_fvg_zone_config.py --profile conservative
```

### Manual Update

Copy the balanced settings into your `configs/binance.yaml` file, replacing the existing `detectors`, `pools`, `zone_watcher`, and `candidate` sections.

### Rollback if Needed

```bash
# Rollback to previous configuration
python update_fvg_zone_config.py --rollback

# Or restore specific backup
cp configs/backups/binance_backup_TIMESTAMP.yaml configs/binance.yaml
```

## 📈 Parameter Explanations

### FVG Parameters

- **`min_gap_atr`**: Gap size in ATR units

  - 0.05 = Micro-gaps (current - too sensitive)
  - 0.2 = Meaningful gaps (balanced)
  - 0.3 = Significant gaps (conservative)

- **`min_gap_pct`**: Gap size as percentage

  - 0.01 = 1% gaps (current - catches noise)
  - 0.03 = 3% gaps (balanced)
  - 0.05 = 5% gaps (conservative)

- **`min_rel_vol`**: Volume requirement multiplier
  - 0.0 = Disabled (current - accepts weak moves)
  - 1.5 = 50% above average (balanced)
  - 2.0 = 100% above average (strict)

### Zone Watcher Parameters

- **`min_strength`**: Minimum zone strength

  - 0.01 = Very weak zones (current - too low)
  - 0.3 = Meaningful strength (balanced)
  - 0.5 = Strong zones only (conservative)

- **`price_tolerance`**: Price hit tolerance
  - 0.0 = Exact hits only (current - too strict)
  - 0.1 = Slight tolerance (balanced)
  - 0.2 = More tolerance (lenient)

## 🧪 Testing Strategy

### Phase 1: Validate Balance (1 week)

1. Apply **BALANCED** settings
2. Run backtest on recent data
3. Monitor signal count vs quality
4. Compare P&L and win rate

### Phase 2: Fine-tune (1 week)

1. If too few signals → try **AGGRESSIVE**
2. If too many false signals → try **CONSERVATIVE**
3. Adjust based on market conditions

### Phase 3: Market Adaptation

- **Volatile markets**: Increase volume requirements, decrease sensitivity
- **Ranging markets**: Decrease volume requirements, increase sensitivity
- **High-frequency trading**: Use **SCALPING** profile
- **Position trading**: Use **POSITION** profile

## ⚡ Quick Start Commands

```bash
# 1. See current analysis
python analyze_fvg_zone_config.py

# 2. View available profiles
python update_fvg_zone_config.py --list

# 3. Preview balanced changes
python update_fvg_zone_config.py --profile balanced --dry-run

# 4. Apply balanced settings
python update_fvg_zone_config.py --profile balanced

# 5. Test with small backtest
python -m scripts.backtest --config configs/binance.yaml --days 7

# 6. Rollback if needed
python update_fvg_zone_config.py --rollback
```

## 🎭 Profile Comparison

| Profile      | FVG Sensitivity | Zone Strength | Volume Filter | Use Case          |
| ------------ | --------------- | ------------- | ------------- | ----------------- |
| Current      | VERY HIGH       | VERY LOW      | DISABLED      | Testing/Debugging |
| Aggressive   | HIGH            | LOW           | MODERATE      | Active Trading    |
| **Balanced** | **MODERATE**    | **MODERATE**  | **BALANCED**  | **General Use**   |
| Conservative | LOW             | HIGH          | STRICT        | Quality Focus     |
| Scalping     | HIGH            | LOW           | MODERATE      | H1 Trading        |
| Position     | VERY LOW        | VERY HIGH     | VERY STRICT   | Daily Trading     |

## 🔍 Expected Results

### With Balanced Settings:

- **Signal Reduction**: 50-70% fewer FVG detections
- **Quality Improvement**: Higher win rate, better risk/reward
- **Less Noise**: Fewer false breakouts and weak zones
- **Better Spacing**: Reduced over-trading from rapid signals

### Warning Signs to Watch:

- ❌ **Too few signals**: Consider AGGRESSIVE profile
- ❌ **Still too noisy**: Consider CONSERVATIVE profile
- ❌ **Poor fill quality**: Increase price_tolerance
- ❌ **Missing opportunities**: Decrease strength thresholds

## 🚀 Recommended Next Steps

1. **Apply balanced settings** with the update script
2. **Run a 7-day backtest** to validate performance
3. **Monitor live performance** for signal quality
4. **Adjust profile** based on results after 1 week
5. **Document lessons learned** for future optimization

The balanced configuration should give you a much better signal-to-noise ratio while maintaining sufficient trading opportunities.
