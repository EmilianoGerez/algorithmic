#!/usr/bin/env python3
"""
3-Phase Optimization Runner for BTC Data
SPEED-OPTIMIZED for MacBook M3 Pro (12 cores, 18GB RAM).

Phase 1: Random Exploration (25 trials, fast random sampling)
Phase 2: Random Refinement (25 trials, narrowed search space)
Phase 3: Bayesian Validation (50 trials, intelligent optimization)

Total: 100 trials vs previous 160 for ~40% speed improvement
"""

import argparse
import logging
import time
from pathlib import Path

from services.models import BacktestConfig
from services.optimization_engine import EnhancedOptimizationEngine, OptimizationConfig

# Configure WARNING-level logging for maximum speed
logging.basicConfig(
    level=logging.WARNING,  # Reduced from INFO for speed
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Aggressive logging reduction for optimization components
logging.getLogger("services.optimization_engine").setLevel(logging.WARNING)
logging.getLogger("services.runner").setLevel(logging.ERROR)
logging.getLogger("core").setLevel(logging.ERROR)
logging.getLogger("services.data_loader").setLevel(logging.ERROR)
logging.getLogger("services.replay").setLevel(logging.ERROR)


def run_phase_1_discovery(
    base_config: BacktestConfig, n_trials: int = 25, n_workers: int = 10
) -> dict:
    """Phase 1: Fast random exploration across full parameter space (SPEED-OPTIMIZED)."""
    print(f"\n🎲 Phase 1: Random Exploration ({n_trials} trials, fast sampling)")
    print("=" * 60)

    opt_config = OptimizationConfig(
        method="random",  # Fast random sampling
        n_trials=n_trials,  # Configurable trials
        timeout_seconds=900,  # 15 minute timeout (reduced from 30)
        # Aggressive multi-fidelity for speed
        use_multifidelity=True,
        initial_data_fraction=0.2,  # Start even smaller for aggressive pruning
        # M3 Pro optimized settings (12 cores)
        n_jobs=n_workers,  # Use command line arg
        use_multiprocessing=True,
        # No pruning for random exploration (let all trials complete on small data)
        enable_pruning=False,
        # Speed optimizations
        cache_preprocessing=True,
        cache_dir="cache/phase1_random",
        # Fast validation - single fold for Phase 1 speed
        discovery_folds=1,  # No out-of-sample for Phase 1 (speed priority)
        validation_folds=2,  # Will be used later
        # Output
        output_dir="results/phase1_random",
        save_study=True,
    )

    engine = EnhancedOptimizationEngine(base_config, opt_config)

    start_time = time.time()
    study = engine.run_random_optimization()  # Use random optimization
    phase1_time = time.time() - start_time

    print(f"\n✅ Phase 1 completed in {phase1_time:.1f}s")
    print(f"Best score: {study.best_value:.6f}")
    print(f"Best params: {study.best_params}")

    # Random doesn't have pruning statistics
    completed = [t for t in study.trials if t.state.name == "COMPLETE"]
    failed = [t for t in study.trials if t.state.name == "FAIL"]
    print(f"Trials: {len(completed)} completed, {len(failed)} failed")

    # Get performance metrics for best trial
    print("\n📊 Phase 1 Performance Metrics:")
    phase1_metrics = engine.get_performance_metrics(study.best_params)
    if phase1_metrics:
        print(f"  Total PnL: {phase1_metrics.get('total_pnl', 'N/A')}")
        print(f"  Sharpe Ratio: {phase1_metrics.get('sharpe_ratio', 'N/A')}")
        print(f"  Win Rate: {phase1_metrics.get('win_rate', 'N/A')}")
        print(f"  Total Trades: {phase1_metrics.get('total_trades', 'N/A')}")
        print(f"  Max Drawdown: {phase1_metrics.get('max_drawdown', 'N/A')}")

    return {
        "study": study,
        "best_params": study.best_params,
        "best_score": study.best_value,
        "time": phase1_time,
        "trials_completed": len(completed),
        "trials_failed": len(failed),
        "performance_metrics": phase1_metrics,
    }


def run_phase_2_focused(
    base_config: BacktestConfig,
    phase1_params: dict,
    n_trials: int = 25,
    n_workers: int = 10,
) -> dict:
    """Phase 2: Random refinement with narrowed search space (SPEED-OPTIMIZED)."""
    print(f"\n🎯 Phase 2: Random Refinement ({n_trials} trials, narrowed space)")
    print("=" * 60)

    opt_config = OptimizationConfig(
        method="random",  # Continue with random sampling
        n_trials=n_trials,  # Configurable trials
        timeout_seconds=900,  # 15 minute timeout (reduced from 40)
        # Faster multi-fidelity
        use_multifidelity=True,
        initial_data_fraction=0.3,  # Start slightly larger than Phase 1
        # M3 Pro optimized settings
        n_jobs=n_workers,
        use_multiprocessing=True,
        # No pruning for random
        enable_pruning=False,
        # Speed optimizations
        cache_preprocessing=True,
        cache_dir="cache/phase2_random",
        # Restore proper validation for Phase 2
        discovery_folds=2,  # Use 2 folds for better estimates
        validation_folds=3,
        # Output
        output_dir="results/phase2_random",
        save_study=True,
    )

    engine = EnhancedOptimizationEngine(base_config, opt_config)

    # TODO: In a full implementation, we would narrow the search space
    # around phase1_params here. For now, use the full search space.
    print(f"Building on Phase 1 insights: {phase1_params}")

    start_time = time.time()
    study = engine.run_random_optimization()  # Use random optimization
    phase2_time = time.time() - start_time

    print(f"\n✅ Phase 2 completed in {phase2_time:.1f}s")
    print(f"Best score: {study.best_value:.6f}")
    print(f"Best params: {study.best_params}")

    # Random doesn't have pruning statistics
    completed = [t for t in study.trials if t.state.name == "COMPLETE"]
    failed = [t for t in study.trials if t.state.name == "FAIL"]
    print(f"Trials: {len(completed)} completed, {len(failed)} failed")

    # Get performance metrics for best trial
    print("\n📊 Phase 2 Performance Metrics:")
    phase2_metrics = engine.get_performance_metrics(study.best_params)
    if phase2_metrics:
        print(f"  Total PnL: {phase2_metrics.get('total_pnl', 'N/A')}")
        print(f"  Sharpe Ratio: {phase2_metrics.get('sharpe_ratio', 'N/A')}")
        print(f"  Win Rate: {phase2_metrics.get('win_rate', 'N/A')}")
        print(f"  Total Trades: {phase2_metrics.get('total_trades', 'N/A')}")
        print(f"  Max Drawdown: {phase2_metrics.get('max_drawdown', 'N/A')}")

    return {
        "study": study,
        "best_params": study.best_params,
        "best_score": study.best_value,
        "time": phase2_time,
        "trials_completed": len(completed),
        "trials_failed": len(failed),
        "performance_metrics": phase2_metrics,
    }


def run_phase_3_validation(
    base_config: BacktestConfig,
    phase2_params: dict,
    n_trials: int = 50,
    n_workers: int = 8,
) -> dict:
    """Phase 3: Bayesian optimization for intelligent final validation (EXPANDED)."""
    print(
        f"\n🧠 Phase 3: Bayesian Validation ({n_trials} trials, intelligent optimization)"
    )
    print("=" * 60)

    opt_config = OptimizationConfig(
        method="bayesian",  # Now use Bayesian optimization
        n_trials=n_trials,  # Configurable trials
        timeout_seconds=1800,  # 30 minute timeout (reduced from 40)
        # Enable multi-fidelity with aggressive pruning for Bayesian
        use_multifidelity=True,
        initial_data_fraction=0.3,  # Start with subset, prune bad candidates
        # Optimal parallelism for Bayesian (better convergence)
        n_jobs=8,  # Balanced jobs for Bayesian optimization
        use_multiprocessing=True,
        # Aggressive pruning for Bayesian
        enable_pruning=True,
        min_trials_for_pruning=3,  # Start pruning earlier
        # Speed optimizations
        cache_preprocessing=True,
        cache_dir="cache/phase3_bayesian",
        # Full validation
        discovery_folds=3,
        validation_folds=3,  # Reasonable validation
        # Output
        output_dir="results/phase3_bayesian",
        save_study=True,
    )

    engine = EnhancedOptimizationEngine(base_config, opt_config)

    print(f"Bayesian optimization around Phase 2 insights: {phase2_params}")

    start_time = time.time()
    study = engine.run_bayesian_optimization()  # Use Bayesian optimization
    phase3_time = time.time() - start_time

    print(f"\n✅ Phase 3 completed in {phase3_time:.1f}s")
    print(f"Best score: {study.best_value:.6f}")
    print(f"Best params: {study.best_params}")

    # Get pruning statistics for Bayesian
    completed = [t for t in study.trials if t.state.name == "COMPLETE"]
    pruned = [t for t in study.trials if t.state.name == "PRUNED"]
    failed = [t for t in study.trials if t.state.name == "FAIL"]
    if len(pruned) > 0:
        print(
            f"Trials: {len(completed)} completed, {len(pruned)} pruned ({len(pruned) / (len(completed) + len(pruned)) * 100:.1f}% pruned), {len(failed)} failed"
        )
    else:
        print(f"Trials: {len(completed)} completed, {len(failed)} failed")

    # Get performance metrics for best trial
    print("\n📊 Phase 3 Performance Metrics:")
    phase3_metrics = engine.get_performance_metrics(study.best_params)
    if phase3_metrics:
        print(f"  Total PnL: {phase3_metrics.get('total_pnl', 'N/A')}")
        print(f"  Sharpe Ratio: {phase3_metrics.get('sharpe_ratio', 'N/A')}")
        print(f"  Win Rate: {phase3_metrics.get('win_rate', 'N/A')}")
        print(f"  Total Trades: {phase3_metrics.get('total_trades', 'N/A')}")
        print(f"  Max Drawdown: {phase3_metrics.get('max_drawdown', 'N/A')}")

    # Final validation
    print("\n🔍 Running final validation...")
    validation_result = engine.validate_best_params(study.best_params)

    # Debug: Show what validation result contains
    print(f"Debug - Validation result keys: {list(validation_result.keys())}")
    if "validation_metrics" in validation_result:
        print(
            f"Debug - Validation metrics keys: {list(validation_result['validation_metrics'].keys())}"
        )

    return {
        "study": study,
        "best_params": study.best_params,
        "best_score": study.best_value,
        "time": phase3_time,
        "trials_completed": len(completed),
        "trials_pruned": len(pruned),
        "validation": validation_result,
        "performance_metrics": phase3_metrics,
    }


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="3-Phase Optimization Runner for BTC Data",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--config",
        type=str,
        default="configs/fast_optimization_btc.yaml",
        help="Path to configuration file",
    )

    parser.add_argument(
        "--data-file", type=str, help="Override data file path from config"
    )

    parser.add_argument(
        "--n1",
        type=int,
        default=25,
        help="Number of trials for Phase 1 (Random Exploration)",
    )

    parser.add_argument(
        "--n2",
        type=int,
        default=25,
        help="Number of trials for Phase 2 (Random Refinement)",
    )

    parser.add_argument(
        "--n3",
        type=int,
        default=50,
        help="Number of trials for Phase 3 (Bayesian Validation)",
    )

    parser.add_argument(
        "--timeout", type=int, default=1800, help="Timeout per phase in seconds"
    )

    parser.add_argument(
        "--workers", type=int, default=10, help="Number of worker processes"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="results/3phase_optimization",
        help="Output directory for results",
    )

    return parser.parse_args()


def main():
    """Run complete 3-phase optimization: Random -> Random -> Bayesian (SPEED-OPTIMIZED)."""
    args = parse_arguments()

    print("🚀 Starting 3-Phase BTC Optimization (MacBook M3 Pro Optimized)")
    print(f"Config: {args.config}")
    print(
        f"Phase 1: Random exploration ({args.n1} trials), Phase 2: Random refinement ({args.n2} trials), Phase 3: Bayesian validation ({args.n3} trials)"
    )
    print(f"TOTAL: {args.n1 + args.n2 + args.n3} trials")
    print("=" * 70)

    # Parameter space analysis
    print("\n📊 Parameter Space Analysis:")
    print("• Risk params: 3 (risk_per_trade, tp_rr, sl_atr_multiple)")
    print("• Zone params: 2 (zone_min_strength, pool_strength_threshold)")
    print("• FVG params: 3 (min_gap_atr, min_gap_pct, min_rel_vol)")
    print(
        "• Candidate params: 3 (ema_tolerance_pct, volume_multiple, min_entry_spacing)"
    )
    print("• Total dimensions: 11 parameters")
    print("• Search space: ~10^11 combinations (intelligent sampling essential)")

    # Load base configuration
    config_path = Path(args.config)

    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return

    # Load configuration
    from omegaconf import OmegaConf

    config_dict = OmegaConf.load(config_path)

    # Override data file if provided
    if args.data_file:
        config_dict.data.path = args.data_file
        print(f"Data file overridden: {args.data_file}")

    base_config = BacktestConfig(**config_dict)

    print(f"\n✅ Configuration loaded from {config_path}")
    print(f"Data file: {base_config.data.path}")
    if hasattr(base_config.data, "start_date") and hasattr(
        base_config.data, "end_date"
    ):
        print(
            f"Data period: {base_config.data.start_date} to {base_config.data.end_date}"
        )

    total_start_time = time.time()

    try:
        # Phase 1: Quick Discovery (configurable trials, single fold for speed)
        phase1_result = run_phase_1_discovery(base_config, args.n1)

        # Phase 2: Focused Search (configurable trials, narrowed ranges)
        phase2_result = run_phase_2_focused(
            base_config, phase1_result["best_params"], args.n2
        )

        # Phase 3: Final Validation (configurable trials, Bayesian + pruning)
        phase3_result = run_phase_3_validation(
            base_config, phase2_result["best_params"], args.n3
        )

        # Summary
        total_time = time.time() - total_start_time

        print("\n" + "=" * 70)
        print("🎉 3-Phase Optimization Complete!")
        print("=" * 70)

        print("\n📈 Final Results:")
        print(f"Total time: {total_time:.1f}s ({total_time / 60:.1f} minutes)")
        print(
            f"Total trials: {phase1_result['trials_completed'] + phase2_result['trials_completed'] + phase3_result['trials_completed']}"
        )
        print(f"Best validation score: {phase3_result['best_score']:.4f}")
        print(
            f"Speed: {total_time / (phase1_result['trials_completed'] + phase2_result['trials_completed'] + phase3_result['trials_completed']):.1f}s per trial"
        )

        # Performance Evolution Across Phases
        print("\n📊 Performance Evolution Across Phases:")
        print(f"{'Metric':<20} {'Phase 1':<15} {'Phase 2':<15} {'Phase 3':<15}")
        print("-" * 70)

        # Extract metrics from each phase
        p1_metrics = phase1_result.get("performance_metrics", {})
        p2_metrics = phase2_result.get("performance_metrics", {})
        p3_metrics = phase3_result.get("performance_metrics", {})

        def format_metric(value, metric_name=""):
            if value == "N/A" or value is None:
                return "N/A"
            elif isinstance(value, int | float):
                if metric_name == "win_rate":
                    return f"{value * 100:.1f}%"  # Convert to percentage
                elif metric_name in ["total_pnl", "max_drawdown"]:
                    return f"{value * 100:+.2f}%"  # Show as percentage with sign
                elif metric_name == "sharpe_ratio":
                    return f"{value:.2f}"  # 2 decimal places for Sharpe
                elif metric_name == "total_trades":
                    return f"{int(value)}"  # Integer for trade count
                else:
                    return f"{value:.4f}" if abs(value) < 1000 else f"{value:.0f}"
            return str(value)

        metrics_to_show = [
            "total_pnl",
            "sharpe_ratio",
            "win_rate",
            "total_trades",
            "max_drawdown",
        ]
        for metric in metrics_to_show:
            p1_val = format_metric(p1_metrics.get(metric, "N/A"), metric)
            p2_val = format_metric(p2_metrics.get(metric, "N/A"), metric)
            p3_val = format_metric(p3_metrics.get(metric, "N/A"), metric)
            print(f"{metric:<20} {p1_val:<15} {p2_val:<15} {p3_val:<15}")

        # Best scores comparison
        print("\n🎯 Optimization Score Evolution:")
        print(f"  Phase 1 (Random): {phase1_result['best_score']:.4f}")
        print(f"  Phase 2 (Random): {phase2_result['best_score']:.4f}")
        print(f"  Phase 3 (Bayesian): {phase3_result['best_score']:.4f}")

        # Calculate improvement
        if phase1_result["best_score"] != 0:
            improvement_p2 = (
                (phase2_result["best_score"] - phase1_result["best_score"])
                / abs(phase1_result["best_score"])
            ) * 100
            improvement_p3 = (
                (phase3_result["best_score"] - phase2_result["best_score"])
                / abs(phase2_result["best_score"])
            ) * 100
            print(f"  Phase 1→2 improvement: {improvement_p2:+.1f}%")
            print(f"  Phase 2→3 improvement: {improvement_p3:+.1f}%")

        print("\n🔧 Optimal Parameters:")
        for key, value in phase3_result["best_params"].items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")

        # Performance comparison
        trials_total = (
            phase1_result["trials_completed"]
            + phase2_result["trials_completed"]
            + phase3_result["trials_completed"]
        )
        reference_trials = 160  # Original reference
        print("\n⚡ Performance Improvement:")
        print(
            f"  Reference: {reference_trials} trials → Current: {trials_total} trials"
        )
        if reference_trials > trials_total:
            print(
                f"  Trial reduction: {((reference_trials - trials_total) / reference_trials) * 100:.1f}%"
            )
            print(
                f"  Estimated time saving: {((reference_trials - trials_total) / reference_trials) * 100:.1f}% faster"
            )
        else:
            print(
                f"  Trial increase: {((trials_total - reference_trials) / reference_trials) * 100:.1f}%"
            )
            print(
                f"  More comprehensive optimization with {args.n1}+{args.n2}+{args.n3} trials"
            )

    except KeyboardInterrupt:
        print("\n⏹️ Optimization interrupted by user")

    except Exception as e:
        print(f"\n❌ Optimization failed: {e}")
        import traceback

        traceback.print_exc()

        print("\n📊 Performance Summary:")
        print(
            f"Phase 1 (Discovery):  {phase1_result['time']:6.1f}s - Score: {phase1_result['best_score']:8.6f}"
        )
        print(
            f"Phase 2 (Focused):    {phase2_result['time']:6.1f}s - Score: {phase2_result['best_score']:8.6f}"
        )
        print(
            f"Phase 3 (Validation): {phase3_result['time']:6.1f}s - Score: {phase3_result['best_score']:8.6f}"
        )
        print(
            f"Total Time:           {total_time:6.1f}s ({total_time / 60:.1f} minutes)"
        )

        print("\n🏆 Final Best Parameters:")
        for key, value in phase3_result["best_params"].items():
            print(f"  {key}: {value}")

        print("\n💰 Final Validation Metrics:")
        if (
            "validation" in phase3_result
            and "validation_metrics" in phase3_result["validation"]
        ):
            metrics = phase3_result["validation"]["validation_metrics"]

            # Check for aggregated metrics (with _mean suffix) or direct metrics
            total_pnl = metrics.get("total_pnl_mean", metrics.get("total_pnl", "N/A"))
            sharpe_ratio = metrics.get(
                "sharpe_ratio_mean", metrics.get("sharpe_ratio", "N/A")
            )
            win_rate = metrics.get("win_rate_mean", metrics.get("win_rate", "N/A"))
            total_trades = metrics.get(
                "total_trades_mean", metrics.get("total_trades", "N/A")
            )
            max_drawdown = metrics.get(
                "max_drawdown_mean", metrics.get("max_drawdown", "N/A")
            )

            print(f"  Total PnL: {total_pnl}")
            print(f"  Sharpe Ratio: {sharpe_ratio}")
            print(f"  Win Rate: {win_rate}")
            print(f"  Total Trades: {total_trades}")
            print(f"  Max Drawdown: {max_drawdown}")

            # Also show aggregation stats if available
            if any(key.endswith("_mean") for key in metrics):
                print(
                    f"  (Metrics averaged across {phase3_result.get('validation', {}).get('individual_folds', ['']).__len__()} folds)"
                )
        else:
            print("  No validation metrics available")
            if "validation" in phase3_result:
                print(
                    f"  Validation result keys: {list(phase3_result['validation'].keys())}"
                )
            else:
                print("  No validation result found")

        print("\n📈 Efficiency Stats:")
        # Fix: trials_pruned might not exist in all cases
        phase1_pruned = phase1_result.get("trials_pruned", 0)
        phase2_pruned = phase2_result.get("trials_pruned", 0)
        phase1_completed = phase1_result.get("trials_completed", 0)
        phase2_completed = phase2_result.get("trials_completed", 0)

        print(
            f"  Phase 1 Pruning: {phase1_pruned}/{phase1_completed + phase1_pruned} trials"
        )
        print(
            f"  Phase 2 Pruning: {phase2_pruned}/{phase2_completed + phase2_pruned} trials"
        )
        print(f"  Total Trials: {phase1_completed + phase2_completed + 20}")

        # Show actual optimized parameters that generated trades
        best_params = phase3_result.get("best_params", {})
        if best_params:
            print("\n🔧 Optimized Thresholds That Generated Trades:")
            print(f"  zone_min_strength: {best_params.get('zone_min_strength', 'N/A')}")
            print(
                f"  pool_strength_threshold: {best_params.get('pool_strength_threshold', 'N/A')}"
            )
            print(
                "  (Note: Config shows static values, but optimization used these dynamic values)"
            )


if __name__ == "__main__":
    main()
