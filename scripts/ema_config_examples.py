"""
Configuration Examples for EMA Improvements

This file demonstrates how to configure the new EMA tolerance buffer and
touch-&-reclaim parameters through YAML configuration files.
"""

# ========================================
# Example 1: Conservative Configuration
# ========================================

conservative_config = """
# configs/conservative_ema.yaml
candidate:
  expiry_minutes: 120
  filters:
    ema_alignment: true
    ema_tolerance_pct: 0.001  # 0.1% tolerance (very tight)
    linger_minutes: 3         # Short 3-minute linger window
    reclaim_requires_ema: true # Strict EMA reclaim required
    volume_multiple: 1.5      # Higher volume requirement
    killzone: ["01:00", "18:00"]
    regime: ["bull", "neutral"]

# Use case: High-confidence, low-noise signals
# - Minimal EMA flexibility (0.1%)
# - Short linger window reduces false positives
# - Higher volume filter for quality
"""

# ========================================
# Example 2: Aggressive Configuration
# ========================================

aggressive_config = """
# configs/aggressive_ema.yaml
candidate:
  expiry_minutes: 180  # Longer expiry for more opportunities
  filters:
    ema_alignment: true
    ema_tolerance_pct: 0.003  # 0.3% tolerance (more flexible)
    linger_minutes: 8         # Longer 8-minute linger window
    reclaim_requires_ema: true
    volume_multiple: 1.0      # Lower volume requirement
    killzone: ["00:00", "23:59"]  # All-day trading
    regime: ["bull", "neutral", "bear"]  # All regimes

# Use case: Maximum trade capture
# - Higher EMA tolerance (0.3%)
# - Longer linger window captures more patterns
# - Relaxed filters for more opportunities
"""

# ========================================
# Example 3: Touch-&-Reclaim Only
# ========================================

touch_reclaim_only = """
# configs/touch_reclaim_only.yaml
candidate:
  expiry_minutes: 120
  filters:
    ema_alignment: true
    ema_tolerance_pct: 0.0    # No tolerance buffer
    linger_minutes: 5         # Enable touch-&-reclaim only
    reclaim_requires_ema: true
    volume_multiple: 1.2
    killzone: ["01:00", "18:00"]
    regime: ["bull", "neutral"]

# Use case: Spring/stop-hunt pattern focus
# - No tolerance buffer (strict EMA alignment initially)
# - Touch-&-reclaim captures liquidity sweeps
# - Clean pattern recognition
"""

# ========================================
# Example 4: Tolerance Buffer Only
# ========================================

tolerance_only = """
# configs/tolerance_only.yaml
candidate:
  expiry_minutes: 120
  filters:
    ema_alignment: true
    ema_tolerance_pct: 0.002  # 0.2% tolerance buffer
    linger_minutes: 0         # No touch-&-reclaim
    reclaim_requires_ema: true
    volume_multiple: 1.2
    killzone: ["01:00", "18:00"]
    regime: ["bull", "neutral"]

# Use case: Simple EMA lag compensation
# - Tolerance buffer handles EMA lag
# - No complex touch-&-reclaim logic
# - Direct alignment improvements
"""

# ========================================
# Example 5: Disabled (Legacy Behavior)
# ========================================

legacy_config = """
# configs/legacy_behavior.yaml
candidate:
  expiry_minutes: 120
  filters:
    ema_alignment: true
    ema_tolerance_pct: 0.0    # No tolerance (original behavior)
    linger_minutes: 0         # No touch-&-reclaim (original behavior)
    reclaim_requires_ema: true
    volume_multiple: 1.2
    killzone: ["01:00", "18:00"]
    regime: ["bull", "neutral"]

# Use case: Maintain exact legacy behavior
# - All new features disabled
# - Perfect backward compatibility
# - Original signal validation logic
"""

# ========================================
# Sweep Configuration for Optimization
# ========================================

sweep_config = """
# configs/sweeps/ema_optimization.yaml
# Comprehensive parameter sweep for EMA improvements

candidate.filters.ema_tolerance_pct:
  - 0.0     # Legacy behavior
  - 0.0005  # 0.05% (very conservative)
  - 0.001   # 0.1% (conservative)
  - 0.0015  # 0.15% (moderate-conservative)
  - 0.002   # 0.2% (recommended baseline)
  - 0.0025  # 0.25% (moderate-aggressive)
  - 0.003   # 0.3% (aggressive)
  - 0.004   # 0.4% (very aggressive)

candidate.filters.linger_minutes:
  - 0   # No touch-&-reclaim
  - 2   # Very short window
  - 3   # Short window
  - 5   # Recommended baseline
  - 8   # Medium window
  - 10  # Long window
  - 15  # Very long window

# Combinations to test:
# 1. Conservative: tolerance=0.001, linger=3
# 2. Balanced: tolerance=0.002, linger=5
# 3. Aggressive: tolerance=0.003, linger=8
"""

print("📋 EMA Improvements Configuration Guide")
print("=" * 50)
print()
print("🎯 **Quick Start Recommendations:**")
print("• Conservative: ema_tolerance_pct=0.001, linger_minutes=3")
print("• Balanced: ema_tolerance_pct=0.002, linger_minutes=5")
print("• Aggressive: ema_tolerance_pct=0.003, linger_minutes=8")
print()
print("⚙️  **Parameter Explanation:**")
print("• ema_tolerance_pct: Flexibility around EMA alignment (0.0-0.5%)")
print("• linger_minutes: Time window for touch-&-reclaim pattern (0-15 min)")
print("• reclaim_requires_ema: Require strict EMA flip after zone touch")
print()
print("📈 **Use Cases:**")
print("• High-frequency scalping: Conservative settings")
print("• Swing trading: Aggressive settings")
print("• Backtesting optimization: Use sweep configurations")
print()
print("🔧 **Implementation Notes:**")
print("• Set ema_tolerance_pct=0.0 and linger_minutes=0 for legacy behavior")
print("• Both mechanisms can be used together or independently")
print("• Higher tolerance captures more trades but may increase noise")
print("• Longer linger windows capture more patterns but may delay signals")
