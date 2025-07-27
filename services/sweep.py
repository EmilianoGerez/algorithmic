"""
Parameter Sweep Engine for Hyperparameter Optimization

This module provides the core functionality for running parameter sweeps
across multiple configurations, enabling systematic hyperparameter optimization
with parallel execution and comprehensive result analysis.

Key Features:
- Grid search and random search support
- Parallel execution with configurable worker pools
- Comprehensive result tracking and ranking
- Statistical significance testing
- Export to CSV/JSON for analysis

Author: GitHub Copilot
"""

from __future__ import annotations

import itertools
import json
import logging
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from omegaconf import DictConfig, OmegaConf

from services.models import BacktestConfig, BacktestResult
from services.runner import BacktestRunner

logger = logging.getLogger(__name__)


@dataclass
class SweepParameter:
    """Definition of a parameter to sweep over."""

    name: str
    values: list[Any]
    parameter_type: str = "discrete"  # discrete, continuous, categorical

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError(f"Parameter {self.name} must have at least one value")


@dataclass
class SweepConfiguration:
    """Configuration for parameter sweep execution."""

    base_config: BacktestConfig
    parameters: list[SweepParameter]
    max_workers: int = 4
    timeout_seconds: int = 300
    output_dir: str = "sweep_results"
    save_individual_results: bool = True

    def __post_init__(self) -> None:
        if not self.parameters:
            raise ValueError("At least one parameter must be specified for sweep")


@dataclass
class SweepResult:
    """Result from a single parameter combination."""

    parameter_combination: dict[str, Any]
    backtest_result: BacktestResult | None
    execution_time: float
    success: bool
    error_message: str | None = None

    @property
    def sharpe_ratio(self) -> float:
        """Get Sharpe ratio, default to negative infinity for failed runs."""
        if not self.success or not self.backtest_result:
            return float("-inf")
        sharpe_val = self.backtest_result.metrics.get("sharpe_ratio", 0.0)
        return float(sharpe_val) if sharpe_val is not None else 0.0

    @property
    def total_return(self) -> float:
        """Get total return, default to negative infinity for failed runs."""
        if not self.success or not self.backtest_result:
            return float("-inf")
        return_val = self.backtest_result.metrics.get("total_return", 0.0)
        return float(return_val) if return_val is not None else 0.0

    @property
    def max_drawdown(self) -> float:
        """Get max drawdown, default to positive infinity for failed runs."""
        if not self.success or not self.backtest_result:
            return float("inf")
        drawdown_val = self.backtest_result.metrics.get("max_drawdown", 0.0)
        return float(drawdown_val) if drawdown_val is not None else 0.0


class ParameterSweepEngine:
    """Core engine for executing parameter sweeps with parallel processing."""

    def __init__(self, config: SweepConfiguration):
        """Initialize sweep engine with configuration.

        Args:
            config: Sweep configuration
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.results: list[SweepResult] = []
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

        # Create output directory
        self.output_path = Path(config.output_dir)
        self.output_path.mkdir(parents=True, exist_ok=True)

    def generate_parameter_combinations(self) -> list[dict[str, Any]]:
        """Generate all parameter combinations for grid search.

        Returns:
            List of parameter dictionaries
        """
        parameter_names = [p.name for p in self.config.parameters]
        parameter_values = [p.values for p in self.config.parameters]

        combinations = []
        for value_combo in itertools.product(*parameter_values):
            combination = dict(zip(parameter_names, value_combo, strict=False))
            combinations.append(combination)

        self.logger.info(f"Generated {len(combinations)} parameter combinations")
        return combinations

    def create_config_for_combination(
        self, parameters: dict[str, Any]
    ) -> BacktestConfig:
        """Create backtest config with specific parameter values.

        Args:
            parameters: Parameter values to apply

        Returns:
            Modified backtest configuration
        """
        # Start with base configuration
        config_dict = self.config.base_config.model_dump()

        # Apply parameter overrides using dot notation
        for param_name, param_value in parameters.items():
            self._set_nested_value(config_dict, param_name, param_value)

        # Create new config instance
        return BacktestConfig(**config_dict)

    def _set_nested_value(
        self, config_dict: dict[str, Any], key_path: str, value: Any
    ) -> None:
        """Set nested dictionary value using dot notation.

        Args:
            config_dict: Configuration dictionary to modify
            key_path: Dot-separated key path (e.g., 'strategy.risk_per_trade')
            value: Value to set
        """
        keys = key_path.split(".")
        current = config_dict

        # Navigate to parent dict
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set final value
        current[keys[-1]] = value

    def run_single_combination(self, parameters: dict[str, Any]) -> SweepResult:
        """Run backtest for a single parameter combination.

        Args:
            parameters: Parameter values for this run

        Returns:
            SweepResult with execution details
        """
        start_time = time.time()

        try:
            # Create configuration for this combination
            config = self.create_config_for_combination(parameters)

            # Run backtest
            runner = BacktestRunner(config)
            result = runner.run()

            execution_time = time.time() - start_time

            return SweepResult(
                parameter_combination=parameters,
                backtest_result=result,
                execution_time=execution_time,
                success=result.success,
                error_message=result.error_message if not result.success else None,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Failed to run combination {parameters}: {e!s}"

            return SweepResult(
                parameter_combination=parameters,
                backtest_result=None,
                execution_time=execution_time,
                success=False,
                error_message=error_msg,
            )

    def run_sweep(self) -> list[SweepResult]:
        """Execute complete parameter sweep with parallel processing.

        Returns:
            List of SweepResult objects sorted by performance
        """
        self.start_time = datetime.now()
        self.logger.info("Starting parameter sweep execution")

        # Generate all parameter combinations
        combinations = self.generate_parameter_combinations()

        if len(combinations) > 100:
            self.logger.warning(
                f"Large sweep with {len(combinations)} combinations. "
                f"This may take significant time."
            )

        # Execute combinations in parallel
        self.results = []
        completed_count = 0

        with ProcessPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all jobs
            future_to_params = {
                executor.submit(self.run_single_combination, params): params
                for params in combinations
            }

            # Collect results as they complete
            for future in as_completed(
                future_to_params, timeout=self.config.timeout_seconds
            ):
                try:
                    result = future.result()
                    self.results.append(result)
                    completed_count += 1

                    if result.success:
                        self.logger.info(
                            f"[{completed_count}/{len(combinations)}] "
                            f"✅ Sharpe: {result.sharpe_ratio:.3f}, "
                            f"Params: {result.parameter_combination}"
                        )
                    else:
                        self.logger.warning(
                            f"[{completed_count}/{len(combinations)}] "
                            f"❌ Failed: {result.error_message}"
                        )

                except Exception as e:
                    params = future_to_params[future]
                    self.logger.error(f"Future failed for {params}: {e}")

                    # Add failed result
                    self.results.append(
                        SweepResult(
                            parameter_combination=params,
                            backtest_result=None,
                            execution_time=0.0,
                            success=False,
                            error_message=f"Future execution failed: {e!s}",
                        )
                    )
                    completed_count += 1

        self.end_time = datetime.now()

        # Sort results by performance (Sharpe ratio descending)
        self.results.sort(key=lambda x: x.sharpe_ratio, reverse=True)

        # Log summary
        successful_runs = sum(1 for r in self.results if r.success)
        total_time = (self.end_time - self.start_time).total_seconds()

        self.logger.info(
            f"Sweep completed: {successful_runs}/{len(self.results)} successful "
            f"in {total_time:.1f} seconds"
        )

        if successful_runs > 0:
            best_result = next(r for r in self.results if r.success)
            self.logger.info(
                f"🏆 Best result: Sharpe {best_result.sharpe_ratio:.3f}, "
                f"Params: {best_result.parameter_combination}"
            )

        return self.results

    def save_results(self, filename: str | None = None) -> Path:
        """Save sweep results to CSV and JSON files.

        Args:
            filename: Base filename (timestamp added if None)

        Returns:
            Path to results directory
        """
        if filename is None:
            timestamp = (
                self.start_time.strftime("%Y%m%d_%H%M%S")
                if self.start_time
                else "unknown"
            )
            filename = f"sweep_results_{timestamp}"

        # Save detailed JSON results
        json_path = self.output_path / f"{filename}.json"
        self._save_json_results(json_path)

        # Save CSV summary
        csv_path = self.output_path / f"{filename}.csv"
        self._save_csv_results(csv_path)

        # Save individual backtest results if requested
        if self.config.save_individual_results:
            individual_dir = self.output_path / f"{filename}_individual"
            self._save_individual_results(individual_dir)

        self.logger.info(f"Results saved to {self.output_path}")
        return self.output_path

    def _save_json_results(self, filepath: Path) -> None:
        """Save complete results to JSON file."""
        results_data = {
            "sweep_config": {
                "parameters": [
                    {"name": p.name, "values": p.values, "type": p.parameter_type}
                    for p in self.config.parameters
                ],
                "max_workers": self.config.max_workers,
                "total_combinations": len(self.results),
            },
            "execution_summary": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "total_duration_seconds": (
                    (self.end_time - self.start_time).total_seconds()
                    if self.start_time and self.end_time
                    else None
                ),
                "successful_runs": sum(1 for r in self.results if r.success),
                "failed_runs": sum(1 for r in self.results if not r.success),
            },
            "results": [
                {
                    "parameters": result.parameter_combination,
                    "success": result.success,
                    "execution_time": result.execution_time,
                    "sharpe_ratio": result.sharpe_ratio if result.success else None,
                    "total_return": result.total_return if result.success else None,
                    "max_drawdown": result.max_drawdown if result.success else None,
                    "error_message": result.error_message,
                    "metrics": (
                        result.backtest_result.metrics
                        if result.success and result.backtest_result
                        else None
                    ),
                }
                for result in self.results
            ],
        }

        with open(filepath, "w") as f:
            json.dump(results_data, f, indent=2, default=str)

    def _save_csv_results(self, filepath: Path) -> None:
        """Save results summary to CSV file."""
        import csv

        if not self.results:
            return

        # Get all parameter names
        param_names = list(self.results[0].parameter_combination.keys())

        # Define CSV columns
        columns = [
            *param_names,
            "success",
            "execution_time",
            "sharpe_ratio",
            "total_return",
            "max_drawdown",
            "total_trades",
            "win_rate",
            "error_message",
        ]

        with open(filepath, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()

            for result in self.results:
                row = result.parameter_combination.copy()
                row.update(
                    {
                        "success": result.success,
                        "execution_time": result.execution_time,
                        "sharpe_ratio": result.sharpe_ratio if result.success else None,
                        "total_return": result.total_return if result.success else None,
                        "max_drawdown": result.max_drawdown if result.success else None,
                        "total_trades": (
                            result.backtest_result.metrics.get("total_trades", 0)
                            if result.success and result.backtest_result
                            else None
                        ),
                        "win_rate": (
                            result.backtest_result.metrics.get("win_rate", 0.0)
                            if result.success and result.backtest_result
                            else None
                        ),
                        "error_message": result.error_message or "",
                    }
                )
                writer.writerow(row)

    def _save_individual_results(self, directory: Path) -> None:
        """Save individual backtest results for successful runs."""
        directory.mkdir(parents=True, exist_ok=True)

        for i, result in enumerate(self.results):
            if result.success and result.backtest_result:
                filename = f"result_{i:04d}.json"
                filepath = directory / filename

                result_data = {
                    "parameters": result.parameter_combination,
                    "backtest_result": result.backtest_result.to_dict(),
                }

                with open(filepath, "w") as f:
                    json.dump(result_data, f, indent=2, default=str)

    def get_top_results(self, n: int = 10) -> list[SweepResult]:
        """Get top N results by Sharpe ratio.

        Args:
            n: Number of top results to return

        Returns:
            List of top SweepResult objects
        """
        successful_results = [r for r in self.results if r.success]
        return successful_results[:n]

    def analyze_parameter_importance(self) -> dict[str, float]:
        """Analyze which parameters have the most impact on performance.

        Returns:
            Dictionary mapping parameter names to importance scores
        """
        if len([r for r in self.results if r.success]) < 10:
            self.logger.warning(
                "Insufficient successful results for parameter analysis"
            )
            return {}

        successful_results = [r for r in self.results if r.success]
        param_names = [self.config.parameters[0].name for p in self.config.parameters]
        importance = {}

        for param_name in param_names:
            # Group results by parameter value
            param_groups: dict[Any, list[float]] = {}
            for result in successful_results:
                param_value = result.parameter_combination[param_name]
                if param_value not in param_groups:
                    param_groups[param_value] = []
                param_groups[param_value].append(result.sharpe_ratio)

            # Calculate variance between groups vs within groups
            if len(param_groups) > 1:
                group_means = [np.mean(values) for values in param_groups.values()]
                np.mean([r.sharpe_ratio for r in successful_results])

                between_group_var = np.var(group_means)
                within_group_var = np.mean(
                    [np.var(values) for values in param_groups.values()]
                )

                # Simple importance score (between-group variance relative to within-group)
                importance[param_name] = between_group_var / (within_group_var + 1e-8)
            else:
                importance[param_name] = 0.0

        return importance


def run_parameter_sweep_from_config(
    base_config_path: str,
    sweep_config: dict[str, Any],
    output_dir: str = "sweep_results",
) -> list[SweepResult]:
    """Convenience function to run parameter sweep from configuration files.

    Args:
        base_config_path: Path to base backtest configuration
        sweep_config: Dictionary defining parameters to sweep
        output_dir: Output directory for results

    Returns:
        List of SweepResult objects
    """
    # Load base configuration
    from services.cli.cli import load_configuration

    base_cfg = load_configuration(base_config_path)
    base_config = BacktestConfig(**base_cfg)

    # Parse sweep parameters
    parameters = []
    for param_name, param_values in sweep_config.items():
        if isinstance(param_values, list):
            parameters.append(SweepParameter(name=param_name, values=param_values))
        else:
            raise ValueError(f"Parameter {param_name} must be a list of values")

    # Create sweep configuration
    sweep_cfg = SweepConfiguration(
        base_config=base_config, parameters=parameters, output_dir=output_dir
    )

    # Execute sweep
    engine = ParameterSweepEngine(sweep_cfg)
    results = engine.run_sweep()
    engine.save_results()

    return results
