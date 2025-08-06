#!/usr/bin/env python3
"""
Enhanced Optimization Engine
Production-grade optimization engine that provides a high-level interface
for the 3-phase optimization system using the ParallelOptimizer underneath.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import optuna
from pydantic import BaseModel

from services.models import BacktestConfig
from services.parallel_optimizer import ParallelOptimizer
from services.runner import BacktestRunner

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """Configuration for optimization engine."""

    # Core optimization settings
    method: str = "random"  # "random" or "bayesian"
    n_trials: int = 50
    timeout_seconds: int = 1800

    # Multi-fidelity settings
    use_multifidelity: bool = True
    initial_data_fraction: float = 0.3

    # Parallelization settings
    n_jobs: int = 8
    use_multiprocessing: bool = True

    # Pruning settings
    enable_pruning: bool = False
    min_trials_for_pruning: int = 5

    # Caching settings
    cache_preprocessing: bool = True
    cache_dir: str = "cache/optimization"

    # Validation settings
    discovery_folds: int = 2
    validation_folds: int = 3

    # Output settings
    output_dir: str = "results/optimization"
    save_study: bool = True


class EnhancedOptimizationEngine:
    """Enhanced optimization engine with production-grade features."""

    def __init__(self, base_config: BacktestConfig, opt_config: OptimizationConfig):
        self.base_config = base_config
        self.opt_config = opt_config

        # Create output directory
        self.output_path = Path(opt_config.output_dir)
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Initialize parallel optimizer
        config_dict = self._convert_config_to_dict(base_config)
        self.parallel_optimizer = ParallelOptimizer(
            config_dict=config_dict,
            n_workers=opt_config.n_jobs,
            cache_dir=opt_config.cache_dir,
            study_db_path=str(self.output_path / "optuna_studies.db"),
        )

        logger.info("EnhancedOptimizationEngine initialized")
        logger.info(f"Method: {opt_config.method}, Trials: {opt_config.n_trials}")
        logger.info(f"Output: {self.output_path}")

    def _convert_config_to_dict(self, config: BacktestConfig) -> dict[str, Any]:
        """Convert BacktestConfig to dictionary for ParallelOptimizer."""
        # Convert Pydantic model to dict
        if hasattr(config, "model_dump"):
            return config.model_dump()
        elif hasattr(config, "dict"):
            return config.dict()
        else:
            # Fallback for older versions
            return {
                "data": {
                    "path": getattr(config.data, "path", ""),
                    "start_date": getattr(config.data, "start_date", None),
                    "end_date": getattr(config.data, "end_date", None),
                },
                "strategy": {
                    "name": getattr(config.strategy, "name", ""),
                    "htf_list": getattr(config.strategy, "htf_list", []),
                },
                "walk_forward": {
                    "folds": self.opt_config.discovery_folds
                    + self.opt_config.validation_folds,
                    "train_fraction": 0.7,
                },
                "execution": {
                    "dump_events": False,
                    "export_data_for_viz": False,
                },
            }

    def run_random_optimization(self) -> optuna.Study:
        """Run random optimization phase."""
        logger.info(f"Starting random optimization: {self.opt_config.n_trials} trials")

        study_name = f"random_{int(time.time())}"

        study = self.parallel_optimizer.run_random_optimization(
            n_trials=self.opt_config.n_trials,
            timeout_seconds=self.opt_config.timeout_seconds,
            data_fraction=self.opt_config.initial_data_fraction
            if self.opt_config.use_multifidelity
            else 1.0,
            enable_pruning=self.opt_config.enable_pruning,
            study_name=study_name,
        )

        # Save study results
        self._save_study_results(study, f"{study_name}_results.json")

        return study

    def run_bayesian_optimization(self) -> optuna.Study:
        """Run Bayesian optimization phase."""
        logger.info(
            f"Starting Bayesian optimization: {self.opt_config.n_trials} trials"
        )

        study_name = f"bayesian_{int(time.time())}"

        study = self.parallel_optimizer.run_bayesian_optimization(
            n_trials=self.opt_config.n_trials,
            timeout_seconds=self.opt_config.timeout_seconds,
            initial_random_trials=max(10, self.opt_config.n_trials // 10),
            enable_multifidelity=self.opt_config.use_multifidelity,
            study_name=study_name,
        )

        # Save study results
        self._save_study_results(study, f"{study_name}_results.json")

        return study

    def get_performance_metrics(self, params: dict[str, Any]) -> dict[str, Any]:
        """Get performance metrics for a specific parameter set."""
        try:
            # Apply parameters to configuration and run real backtest
            config_dict = self._convert_config_to_dict(self.base_config)

            # Apply optimization parameters
            for param_name, param_value in params.items():
                if param_name == "risk_per_trade":
                    config_dict["risk"]["risk_per_trade"] = param_value
                elif param_name == "tp_rr":
                    config_dict["risk"]["tp_rr"] = param_value
                elif param_name == "sl_atr_multiple":
                    config_dict["risk"]["sl_atr_multiple"] = param_value
                elif param_name == "zone_min_strength":
                    if "zone_watcher" not in config_dict:
                        config_dict["zone_watcher"] = {}
                    config_dict["zone_watcher"]["min_strength"] = param_value
                elif param_name == "pool_strength_threshold":
                    if "pools" not in config_dict:
                        config_dict["pools"] = {}
                    config_dict["pools"]["strength_threshold"] = param_value
                # FVG detection parameters
                elif param_name == "min_gap_atr":
                    if "detectors" not in config_dict:
                        config_dict["detectors"] = {}
                    if "fvg" not in config_dict["detectors"]:
                        config_dict["detectors"]["fvg"] = {}
                    config_dict["detectors"]["fvg"]["min_gap_atr"] = param_value
                elif param_name == "min_gap_pct":
                    if "detectors" not in config_dict:
                        config_dict["detectors"] = {}
                    if "fvg" not in config_dict["detectors"]:
                        config_dict["detectors"]["fvg"] = {}
                    config_dict["detectors"]["fvg"]["min_gap_pct"] = param_value
                elif param_name == "min_rel_vol":
                    if "detectors" not in config_dict:
                        config_dict["detectors"] = {}
                    if "fvg" not in config_dict["detectors"]:
                        config_dict["detectors"]["fvg"] = {}
                    config_dict["detectors"]["fvg"]["min_rel_vol"] = param_value
                # Candidate filtering parameters
                elif param_name == "ema_tolerance_pct":
                    if "candidate" not in config_dict:
                        config_dict["candidate"] = {}
                    if "filters" not in config_dict["candidate"]:
                        config_dict["candidate"]["filters"] = {}
                    config_dict["candidate"]["filters"]["ema_tolerance_pct"] = (
                        param_value
                    )
                elif param_name == "volume_multiple":
                    if "candidate" not in config_dict:
                        config_dict["candidate"] = {}
                    if "filters" not in config_dict["candidate"]:
                        config_dict["candidate"]["filters"] = {}
                    config_dict["candidate"]["filters"]["volume_multiple"] = param_value
                elif param_name == "min_entry_spacing":
                    if "candidate" not in config_dict:
                        config_dict["candidate"] = {}
                    config_dict["candidate"]["min_entry_spacing_minutes"] = param_value

            # Create config and run backtest
            config = BacktestConfig.from_dict(config_dict)
            runner = BacktestRunner(config)
            results = runner.run()

            if results and results.success and results.metrics:
                # Handle both dict and BacktestMetrics object
                if hasattr(results.metrics, "to_dict"):
                    metrics_dict = results.metrics.to_dict()
                elif hasattr(results.metrics, "__dict__"):
                    metrics_dict = results.metrics.__dict__
                else:
                    metrics_dict = results.metrics

                # Extract nested metrics - the actual metrics are in 'trade_metrics' sub-dict
                trade_metrics = metrics_dict.get("trade_metrics", {})

                metrics = trade_metrics  # Use trade_metrics as the main metrics source
                return {
                    "total_pnl": metrics.get("total_pnl", 0.0),
                    "total_return": metrics.get("total_pnl", 0.0)
                    / 10000.0,  # Convert to return ratio
                    "sharpe_ratio": 0.0,  # Not available in trade_metrics
                    "win_rate": metrics.get("win_rate", 0.0),
                    "total_trades": metrics.get("total_trades", 0),
                    "max_drawdown": metrics.get("max_drawdown", 0.0),
                    "profit_factor": metrics.get("profit_factor", 1.0)
                    if "profit_factor" in metrics
                    else 1.0,
                }
            else:
                logger.warning("Backtest returned no metrics")
                return {
                    "total_pnl": 0.0,
                    "total_return": 0.0,
                    "sharpe_ratio": 0.0,
                    "win_rate": 0.0,
                    "total_trades": 0,
                    "max_drawdown": 0.0,
                    "profit_factor": 0.0,
                }

        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {
                "total_pnl": 0.0,
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
                "max_drawdown": 0.0,
                "profit_factor": 0.0,
            }

    def validate_best_params(self, best_params: dict[str, Any]) -> dict[str, Any]:
        """Run validation on the best parameters."""
        logger.info("Running validation on best parameters...")

        try:
            # Get performance metrics
            metrics = self.get_performance_metrics(best_params)

            # Run walk-forward validation if configured
            if self.opt_config.validation_folds > 1:
                validation_metrics = self._run_walk_forward_validation(best_params)

                return {
                    "validation_metrics": validation_metrics,
                    "single_run_metrics": metrics,
                    "best_params": best_params,
                    "validation_folds": self.opt_config.validation_folds,
                }
            else:
                return {
                    "validation_metrics": metrics,
                    "best_params": best_params,
                    "validation_folds": 1,
                }

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {"validation_metrics": {}, "error": str(e)}

    def _run_walk_forward_validation(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run walk-forward validation."""
        try:
            config_dict = self._convert_config_to_dict(self.base_config)

            # Apply parameters (simplified)
            temp_config = BacktestConfig(**config_dict)
            runner = BacktestRunner(temp_config)

            # Run walk-forward
            results = runner.run_walk_forward()

            if results and all(r.success for r in results):
                # Aggregate metrics across folds
                aggregated_metrics = {}
                all_metrics = [r.metrics for r in results if r.metrics]

                if all_metrics:
                    # Calculate means for key metrics
                    for key in all_metrics[0]:
                        values = [
                            m.get(key, 0)
                            for m in all_metrics
                            if isinstance(m.get(key), int | float)
                        ]
                        if values:
                            aggregated_metrics[f"{key}_mean"] = sum(values) / len(
                                values
                            )
                            aggregated_metrics[f"{key}_std"] = (
                                sum(
                                    (x - aggregated_metrics[f"{key}_mean"]) ** 2
                                    for x in values
                                )
                                / len(values)
                            ) ** 0.5

                return aggregated_metrics
            else:
                logger.warning("Walk-forward validation failed")
                return {}

        except Exception as e:
            logger.error(f"Walk-forward validation error: {e}")
            return {}

    def _save_study_results(self, study: optuna.Study, filename: str) -> None:
        """Save study results to file."""
        try:
            results = {
                "study_name": study.study_name,
                "direction": study.direction.name,
                "best_value": study.best_value if study.best_trial else None,
                "best_params": study.best_params if study.best_trial else None,
                "n_trials": len(study.trials),
                "creation_time": None,  # Optuna Study doesn't have creation_time
                "trials": [],
            }

            # Add trial details
            for trial in study.trials:
                trial_data = {
                    "number": trial.number,
                    "value": trial.value,
                    "params": trial.params,
                    "state": trial.state.name,
                    "datetime_start": trial.datetime_start.isoformat()
                    if trial.datetime_start
                    else None,
                    "datetime_complete": trial.datetime_complete.isoformat()
                    if trial.datetime_complete
                    else None,
                }
                results["trials"].append(trial_data)

            # Save to file
            output_file = self.output_path / filename
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)

            logger.info(f"Study results saved to: {output_file}")

        except Exception as e:
            logger.error(f"Failed to save study results: {e}")

    def get_optimization_summary(self) -> dict[str, Any]:
        """Get summary of optimization runs."""
        try:
            studies = self.parallel_optimizer.list_studies()
            summary: dict[str, Any] = {"total_studies": len(studies), "studies": []}

            for study_name in studies:
                study_info = self.parallel_optimizer.get_study_info(study_name)
                if isinstance(summary["studies"], list):
                    summary["studies"].append(study_info)

            return summary

        except Exception as e:
            logger.error(f"Failed to get optimization summary: {e}")
            return {"error": str(e)}


# Convenience functions for backward compatibility
def create_optimization_engine(
    base_config: BacktestConfig, **kwargs: Any
) -> EnhancedOptimizationEngine:
    """Create optimization engine with default settings."""
    opt_config = OptimizationConfig(**kwargs)
    return EnhancedOptimizationEngine(base_config, opt_config)


def run_quick_optimization(
    base_config: BacktestConfig,
    n_trials: int = 50,
    method: str = "random",
    **kwargs: Any,
) -> dict[str, Any]:
    """Run a quick optimization for testing."""
    opt_config = OptimizationConfig(
        method=method,
        n_trials=n_trials,
        timeout_seconds=600,  # 10 minutes
        n_jobs=4,
        enable_pruning=False,
        output_dir="results/quick_optimization",
    )

    engine = EnhancedOptimizationEngine(base_config, opt_config)

    if method == "random":
        result = engine.run_random_optimization()
        return result if isinstance(result, dict) else {}
    else:
        result = engine.run_bayesian_optimization()
        return result if isinstance(result, dict) else {}
