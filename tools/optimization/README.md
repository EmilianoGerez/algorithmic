# 🎯 Optimization Tools

Tools for running various optimization strategies and configurations.

## 🚀 Available Tools

### `run_3phase_optimization.py`
**Main 3-phase optimization runner** - The primary optimization tool.

```bash
python tools/optimization/run_3phase_optimization.py --n1 25 --n2 25 --n3 50
```

**Features:**
- Phase 1: Random exploration
- Phase 2: Random refinement
- Phase 3: Bayesian validation
- 11-parameter optimization space
- M3 Pro optimized for speed

### `run_ultra_fast_optimization.py`
**Quick optimization testing** - For rapid parameter testing.

### `run_optimization_demo.py`
**Demo optimization** - Simple demonstration of optimization capabilities.

### `production_optimization_demo.py`
**Production optimization** - Production-ready optimization with full validation.

### `test_real_optimization.py`
**Real optimization testing** - Test optimization with real data validation.

## 📊 Parameters Optimized

- **Risk Management** (3 params): risk_per_trade, tp_rr, sl_atr_multiple
- **Zone Detection** (2 params): zone_min_strength, pool_strength_threshold
- **FVG Detection** (3 params): min_gap_atr, min_gap_pct, min_rel_vol
- **Candidate Filtering** (3 params): ema_tolerance_pct, volume_multiple, min_entry_spacing

## 📈 Results

Optimization results are saved to:
- `results/phase1_random/`
- `results/phase2_random/`
- `results/phase3_bayesian/`
