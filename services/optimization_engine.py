#!/usr/bin/env python3
"""
Enhanced HTF Strategy Optimization Engine

Implements modern hyperparameter optimization strategies:
- Bayesian optimization via Optuna
- Multi-fidelity optimization
- Parallel execution with caching
- Early stopping for unpromising trials
"""

import hashlib
import json
import logging
import pickle
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

try:
    import optuna  # type: ignore[import-not-found]
    from optuna.pruners import MedianPruner  # type: ignore[import-not-found]
    from optuna.samplers import TPESampler  # type: ignore[import-not-found]

    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False

try:
    from joblib import Parallel, delayed  # type: ignore[import-not-found]

    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False

from services.models import BacktestConfig
from services.runner import BacktestRunner

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """Configuration for optimization runs."""

    # Search strategy
    method: str = "bayesian"  # "bayesian", "random", "grid"
    n_trials: int = 200
    timeout_seconds: int | None = None

    # Parallelization
    n_jobs: int = 4
    use_multiprocessing: bool = True

    # Multi-fidelity
    use_multifidelity: bool = True
    initial_data_fraction: float = 0.3
    promotion_threshold: float = 0.5  # Top 50% advance to full data

    # Caching
    cache_preprocessing: bool = True
    cache_dir: str = "cache/optimization"

    # Early stopping
    enable_pruning: bool = True
    min_trials_for_pruning: int = 20

    # Walk-forward during optimization
    discovery_folds: int = 2  # Fast discovery phase (minimum 2 for validation)
    validation_folds: int = 3  # Final validation

    # Output
    output_dir: str = "results/optimization"
    save_study: bool = True


class OptimizationCache:
    """Caches expensive preprocessing operations."""

    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._aggregation_cache: dict[str, Any] = {}
        self._indicator_cache: dict[str, Any] = {}

    def get_cache_key(self, config: dict[str, Any], data_path: str) -> str:
        """Generate cache key from config and data."""
        cache_data = {
            "data_path": data_path,
            "aggregation": config.get("aggregation", {}),
            "indicators": config.get("indicators", {}),
        }
        return hashlib.md5(str(cache_data).encode()).hexdigest()

    def get_cached_preprocessing(self, cache_key: str) -> dict[str, Any] | None:
        """Load cached preprocessing results."""
        cache_file = self.cache_dir / f"preprocess_{cache_key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    return pickle.load(f)  # type: ignore[no-any-return]
            except Exception as e:
                logger.warning(f"Failed to load cache {cache_file}: {e}")
        return None

    def save_preprocessing(self, cache_key: str, data: dict[str, Any]) -> None:
        """Save preprocessing results to cache."""
        cache_file = self.cache_dir / f"preprocess_{cache_key}.pkl"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save cache {cache_file}: {e}")


class EnhancedOptimizationEngine:
    """Enhanced optimization engine with modern hyperparameter search."""

    def __init__(self, base_config: BacktestConfig, config: OptimizationConfig):
        self.base_config = base_config
        self.config = config
        self.cache = (
            OptimizationCache(config.cache_dir) if config.cache_preprocessing else None
        )

        # Results tracking
        self.results: list[dict[str, Any]] = []
        self.best_params: dict[str, Any] | None = None
        self.best_score = float("-inf")

        # Setup output directory
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def define_search_space(self, trial: Any) -> dict[str, Any]:
        """Define the hyperparameter search space for Optuna."""
        params = {}

        # Risk management
        params["risk.risk_per_trade"] = trial.suggest_float(
            "risk_per_trade", 0.003, 0.02, step=0.001
        )
        params["risk.tp_rr"] = trial.suggest_float("tp_rr", 2.0, 4.0, step=0.5)
        params["risk.sl_atr_multiple"] = trial.suggest_float(
            "sl_atr_multiple", 1.0, 2.5, step=0.25
        )

        # FVG detection
        params["detectors.fvg.min_gap_atr"] = trial.suggest_float(
            "fvg_min_gap_atr", 0.15, 0.4, step=0.05
        )
        params["detectors.fvg.min_gap_pct"] = trial.suggest_float(
            "fvg_min_gap_pct", 0.01, 0.05, step=0.005
        )
        params["detectors.fvg.min_rel_vol"] = trial.suggest_float(
            "fvg_min_rel_vol", 0.5, 2.5, step=0.25
        )

        # HLZ confluence
        params["hlz.min_strength"] = trial.suggest_float(
            "hlz_min_strength", 1.5, 4.0, step=0.25
        )
        params["hlz.merge_tolerance"] = trial.suggest_float(
            "hlz_merge_tolerance", 0.2, 0.5, step=0.05
        )

        # Zone filtering
        params["zone_watcher.min_strength"] = trial.suggest_float(
            "zone_min_strength", 0.8, 2.5, step=0.1
        )
        params["pools.strength_threshold"] = trial.suggest_float(
            "pool_strength_threshold", 0.3, 1.0, step=0.05
        )

        # Entry timing
        params["candidate.min_entry_spacing_minutes"] = trial.suggest_int(
            "entry_spacing", 30, 120, step=15
        )
        params["candidate.filters.ema_tolerance_pct"] = trial.suggest_float(
            "ema_tolerance", 0.0005, 0.003, step=0.0005
        )

        # Volume filtering
        params["candidate.filters.volume_multiple"] = trial.suggest_float(
            "volume_multiple", 0.0, 3.0, step=0.5
        )

        return params

    def objective_function(self, trial: Any) -> float:
        """Objective function for optimization."""
        try:
            # Get trial parameters
            params = self.define_search_space(trial)

            # Multi-fidelity: start with subset of data
            if self.config.use_multifidelity:
                # Quick evaluation on partial data
                quick_score = self._evaluate_quick(params, trial)

                # Report intermediate value for pruning
                trial.report(quick_score, step=0)

                # Check if trial should be pruned
                if trial.should_prune():
                    raise optuna.TrialPruned()

                # If promising, run full evaluation
                if quick_score > self.best_score * 0.7:  # Top candidates
                    score = self._evaluate_full(params)
                else:
                    score = quick_score
            else:
                # Standard full evaluation
                score = self._evaluate_full(params)

            # Track best result
            if score > self.best_score:
                self.best_score = score
                self.best_params = params.copy()

            return score

        except Exception as e:
            logger.error(f"Trial failed: {e}")
            # Return poor score rather than crash
            return float("-inf")

    def _evaluate_quick(self, params: dict[str, Any], trial: Any) -> float:
        """Quick evaluation on subset of data."""
        # Create trial config with reduced data
        trial_config = self._build_trial_config(params)

        # Convert to dict for modification, then back to config
        config_dict = trial_config.model_dump()

        # Reduce data size for quick evaluation
        original_start = config_dict["data"].get("start_date")
        original_end = config_dict["data"].get("end_date")

        if original_start and original_end:
            # Use first 30% of date range
            from datetime import datetime, timedelta

            start_dt = datetime.fromisoformat(original_start)
            end_dt = datetime.fromisoformat(original_end)
            total_days = (end_dt - start_dt).days
            quick_end = start_dt + timedelta(
                days=int(total_days * self.config.initial_data_fraction)
            )
            config_dict["data"]["end_date"] = quick_end.isoformat()

        # Disable expensive features for quick eval - use minimum folds
        config_dict["execution"]["dump_events"] = False
        config_dict["execution"]["export_data_for_viz"] = False
        config_dict["walk_forward"]["folds"] = 2  # Minimum allowed folds

        # Recreate config
        modified_config = BacktestConfig(**config_dict)

        # Run backtest
        runner = BacktestRunner(modified_config)
        result = runner.run()

        if result.success and hasattr(result, "metrics"):
            return self._extract_score(result.metrics)
        return float("-inf")

    def _evaluate_full(self, params: dict[str, Any]) -> float:
        """Full evaluation with complete data and walk-forward."""
        trial_config = self._build_trial_config(params)

        # Convert to dict for modification, then back to config
        config_dict = trial_config.model_dump()

        # Use discovery folds for optimization
        config_dict["walk_forward"]["folds"] = self.config.discovery_folds

        # Recreate config
        modified_config = BacktestConfig(**config_dict)

        # Run backtest
        runner = BacktestRunner(modified_config)

        if self.config.discovery_folds > 1:
            results = runner.run_walk_forward()
            if results and all(r.success for r in results):
                # Average score across folds
                scores = [self._extract_score(r.metrics) for r in results]
                return float(np.mean(scores))
        else:
            result = runner.run()
            if result.success and hasattr(result, "metrics"):
                return self._extract_score(result.metrics)

        return float("-inf")

    def _build_trial_config(self, params: dict[str, Any]) -> BacktestConfig:
        """Build configuration for trial with parameter overrides."""
        try:
            # Convert base config to dictionary
            config_dict = self.base_config.model_dump()

            # Apply parameter overrides
            for param_path, value in params.items():
                logger.debug(f"Setting {param_path} = {value} (type: {type(value)})")
                self._set_nested_param(config_dict, param_path, value)

            return BacktestConfig(**config_dict)

        except Exception as e:
            logger.error(f"Failed to build trial config: {e}")
            logger.error(f"Parameters: {params}")
            raise

    def _set_nested_param(self, config: dict[str, Any], path: str, value: Any) -> None:
        """Set nested parameter in config dictionary."""
        keys = path.split(".")
        current = config

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def _extract_score(self, metrics: dict[str, Any]) -> float:
        """Extract optimization score from metrics."""
        # Composite score combining multiple factors
        total_pnl = metrics.get("total_pnl", 0)
        sharpe = metrics.get("sharpe_ratio", 0)
        win_rate = metrics.get("win_rate", 0)
        total_trades = metrics.get("total_trades", 0)
        max_drawdown = metrics.get("max_drawdown", 0)

        # Minimum trade requirement
        if total_trades < 5:
            return float("-inf")

        # Composite score (you can adjust weights)
        score = (
            total_pnl * 0.4  # Absolute profit
            + sharpe * 100 * 0.3  # Risk-adjusted return
            + win_rate * 100 * 0.2  # Consistency
            + (1 - abs(max_drawdown)) * 50 * 0.1  # Drawdown penalty
        )

        return float(score)

    def run_bayesian_optimization(self) -> optuna.Study:
        """Run Bayesian optimization with Optuna."""
        if not HAS_OPTUNA:
            raise ImportError(
                "Optuna required for Bayesian optimization: pip install optuna"
            )

        # Create study
        sampler = TPESampler(seed=42)
        pruner = (
            MedianPruner(
                n_startup_trials=self.config.min_trials_for_pruning, n_warmup_steps=1
            )
            if self.config.enable_pruning
            else None
        )

        study = optuna.create_study(
            direction="maximize",
            sampler=sampler,
            pruner=pruner,
            study_name=f"htf_optimization_{int(time.time())}",
        )

        # Run optimization
        logger.info(
            f"Starting Bayesian optimization with {self.config.n_trials} trials"
        )

        study.optimize(
            self.objective_function,
            n_trials=self.config.n_trials,
            timeout=self.config.timeout_seconds,
            n_jobs=1,  # Optuna handles parallelization differently
        )

        # Save study
        if self.config.save_study:
            study_path = self.output_dir / f"optuna_study_{int(time.time())}.pkl"
            with open(study_path, "wb") as f:
                pickle.dump(study, f)
            logger.info(f"Study saved to {study_path}")

        return study

    def run_parallel_random_search(self) -> list[dict[str, Any]]:
        """Run parallel random search without Optuna."""
        logger.info(
            f"Starting parallel random search with {self.config.n_trials} trials"
        )

        # Generate random parameter combinations
        param_combinations = self._generate_random_params(self.config.n_trials)

        # Run in parallel
        if self.config.use_multiprocessing and HAS_JOBLIB:
            results: list[dict[str, Any]] = Parallel(n_jobs=self.config.n_jobs)(
                delayed(self._evaluate_params)(params) for params in param_combinations
            )
        else:
            # Sequential fallback
            results = [self._evaluate_params(params) for params in param_combinations]

        return results

    def _generate_random_params(self, n_trials: int) -> list[dict[str, Any]]:
        """Generate random parameter combinations."""
        combinations = []

        for _ in range(n_trials):
            params = {}

            # Risk management
            params["risk.risk_per_trade"] = float(np.random.uniform(0.003, 0.02))
            params["risk.tp_rr"] = float(np.random.choice([2.0, 2.5, 3.0, 3.5, 4.0]))
            params["risk.sl_atr_multiple"] = float(np.random.uniform(1.0, 2.5))

            # FVG detection
            params["detectors.fvg.min_gap_atr"] = float(np.random.uniform(0.15, 0.4))
            params["detectors.fvg.min_gap_pct"] = float(np.random.uniform(0.01, 0.05))
            params["detectors.fvg.min_rel_vol"] = float(np.random.uniform(0.5, 2.5))

            # HLZ confluence
            params["hlz.min_strength"] = float(np.random.uniform(1.5, 4.0))
            params["hlz.merge_tolerance"] = float(np.random.uniform(0.2, 0.5))

            # Zone filtering
            params["zone_watcher.min_strength"] = float(np.random.uniform(0.8, 2.5))
            params["pools.strength_threshold"] = float(np.random.uniform(0.3, 1.0))

            # Entry timing - fix the randint call
            spacing_options = [30, 45, 60, 75, 90, 105, 120]
            params["candidate.min_entry_spacing_minutes"] = int(
                np.random.choice(spacing_options)
            )
            params["candidate.filters.ema_tolerance_pct"] = float(
                np.random.uniform(0.0005, 0.003)
            )

            # Volume filtering
            params["candidate.filters.volume_multiple"] = float(
                np.random.uniform(0.0, 3.0)
            )

            combinations.append(params)

        return combinations

    def _evaluate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Evaluate single parameter combination."""
        try:
            score = self._evaluate_full(params)
            return {"params": params, "score": score, "success": True}
        except Exception as e:
            logger.error(f"Parameter evaluation failed: {e}")
            return {
                "params": params,
                "score": float("-inf"),
                "success": False,
                "error": str(e),
            }

    def validate_best_params(self, best_params: dict[str, Any]) -> dict[str, Any]:
        """Final validation with full walk-forward."""
        logger.info("Running final validation with full walk-forward")

        try:
            trial_config = self._build_trial_config(best_params)

            # Create new config dict with validation folds
            config_dict = trial_config.model_dump()
            config_dict["walk_forward"]["folds"] = self.config.validation_folds

            # Rebuild config from dict
            from services.models import BacktestConfig

            validation_config = BacktestConfig.model_validate(config_dict)

            runner = BacktestRunner(validation_config)

            if self.config.validation_folds > 1:
                results = runner.run_walk_forward()
                if results and all(r.success for r in results):
                    # Aggregate metrics
                    metrics = self._aggregate_walk_forward_metrics(results)
                    return {
                        "params": best_params,
                        "validation_metrics": metrics,
                        "individual_folds": [r.metrics for r in results],
                    }
            else:
                result = runner.run()
                if result.success:
                    return {"params": best_params, "validation_metrics": result.metrics}

            return {"params": best_params, "validation_error": "Failed to validate"}

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            logger.error(f"Parameters: {best_params}")
            raise

    def _aggregate_walk_forward_metrics(self, results: list) -> dict[str, Any]:
        """Aggregate metrics across walk-forward folds."""
        metrics = {}

        # Get all metric keys from first successful result
        first_result = next(r for r in results if r.success)
        logger.debug(f"First result metrics type: {type(first_result.metrics)}")
        logger.debug(f"First result metrics: {first_result.metrics}")

        metric_keys = first_result.metrics.keys()

        for key in metric_keys:
            values = [r.metrics.get(key, 0) for r in results if r.success]
            logger.debug(
                f"Key: {key}, Values: {values}, Types: {[type(v) for v in values]}"
            )

            if values:
                # Only aggregate numeric values
                try:
                    # Check if all values are numeric
                    numeric_values = []
                    for v in values:
                        if isinstance(v, int | float):
                            numeric_values.append(v)
                        elif isinstance(v, dict):
                            logger.warning(f"Skipping dict value for key {key}: {v}")
                            continue
                        else:
                            logger.warning(
                                f"Skipping non-numeric value for key {key}: {v} (type: {type(v)})"
                            )
                            continue

                    if numeric_values:
                        metrics[f"{key}_mean"] = np.mean(numeric_values)
                        metrics[f"{key}_std"] = np.std(numeric_values)
                        metrics[f"{key}_min"] = np.min(numeric_values)
                        metrics[f"{key}_max"] = np.max(numeric_values)
                    else:
                        logger.warning(f"No numeric values found for key {key}")

                except Exception as e:
                    logger.error(f"Error aggregating key {key}: {e}")
                    logger.error(f"Values causing error: {values}")

        return metrics

    def generate_report(
        self, study_or_results: Any, validation_result: dict | None = None
    ) -> str:
        """Generate optimization report."""
        report_lines = [
            "# HTF Strategy Optimization Report",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Configuration",
            f"- Method: {self.config.method}",
            f"- Trials: {self.config.n_trials}",
            f"- Parallel jobs: {self.config.n_jobs}",
            f"- Multi-fidelity: {self.config.use_multifidelity}",
            "",
        ]

        if HAS_OPTUNA and isinstance(study_or_results, optuna.Study):
            # Optuna study report
            best_trial = study_or_results.best_trial

            report_lines.extend(
                [
                    "## Best Trial",
                    f"- Score: {best_trial.value:.4f}",
                    f"- Trial number: {best_trial.number}",
                    "",
                    "### Best Parameters:",
                ]
            )

            for key, value in best_trial.params.items():
                report_lines.append(f"- {key}: {value}")

            # Parameter importance
            try:
                importance = optuna.importance.get_param_importances(study_or_results)
                report_lines.extend(
                    [
                        "",
                        "### Parameter Importance:",
                    ]
                )
                for param, score in sorted(
                    importance.items(), key=lambda x: x[1], reverse=True
                ):
                    report_lines.append(f"- {param}: {score:.4f}")
            except Exception:
                pass

        # Validation results
        if validation_result:
            report_lines.extend(
                [
                    "",
                    "## Validation Results",
                ]
            )

            validation_metrics = validation_result.get("validation_metrics", {})
            for key, value in validation_metrics.items():
                if isinstance(value, int | float):
                    report_lines.append(f"- {key}: {value:.4f}")

        return "\n".join(report_lines)


def main() -> None:
    """Example usage of the enhanced optimization engine."""
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced HTF Strategy Optimization")
    parser.add_argument("--config", default="configs/btcusdt_optimization_base.yaml")
    parser.add_argument("--method", choices=["bayesian", "random"], default="bayesian")
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, help="Timeout in seconds")

    args = parser.parse_args()

    # Load base configuration
    from services.cli.cli import load_configuration

    base_config_dict = load_configuration(args.config)
    base_config = BacktestConfig(**base_config_dict)

    # Setup optimization
    opt_config = OptimizationConfig(
        method=args.method,
        n_trials=args.trials,
        n_jobs=args.jobs,
        timeout_seconds=args.timeout,
    )

    engine = EnhancedOptimizationEngine(base_config, opt_config)

    # Run optimization
    if args.method == "bayesian" and HAS_OPTUNA:
        study = engine.run_bayesian_optimization()
        best_params = study.best_params

        # Map back to full parameter names
        full_params = {}
        for key, value in best_params.items():
            if key == "risk_per_trade":
                full_params["risk.risk_per_trade"] = value
            elif key == "tp_rr":
                full_params["risk.tp_rr"] = value
            # Add more mappings as needed

        best_result = study
    else:
        results = engine.run_parallel_random_search()
        best_result = max(results, key=lambda x: x["score"])
        full_params = best_result["params"]
        best_result = results

    # Final validation
    validation = engine.validate_best_params(full_params)

    # Generate report
    report = engine.generate_report(best_result, validation)

    # Save report
    report_path = engine.output_dir / "optimization_report.md"
    with open(report_path, "w") as f:
        f.write(report)

    print(f"✅ Optimization completed. Report saved to {report_path}")
    print(f"🏆 Best score: {engine.best_score:.4f}")


if __name__ == "__main__":
    main()
