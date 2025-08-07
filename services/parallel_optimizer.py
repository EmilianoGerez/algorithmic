#!/usr/bin/env python3
"""
Parallel Optimization Runner with True Parallelism
Uses ProcessPoolExecutor with as_completed() for maximum speed.
"""

import logging
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

import numpy as np
import optuna
from optuna.pruners import MedianPruner, SuccessiveHalvingPruner
from optuna.samplers import RandomSampler, TPESampler

from services.preprocessing_cache import FastTrialRunner, PreprocessingCache

logger = logging.getLogger(__name__)


def run_single_trial(
    args: tuple[str, dict[str, Any], float, int],
) -> tuple[int, dict[str, Any]]:
    """Run a single trial in a separate process."""
    cache_key, params, data_fraction, trial_id = args

    try:
        # Create cache and runner in worker process
        cache = PreprocessingCache()
        runner = FastTrialRunner(cache_key, cache)

        # Run trial
        result = runner.run_trial(params, data_fraction)
        result["trial_id"] = trial_id

        return trial_id, result

    except Exception as e:
        logger.error(f"Trial {trial_id} failed: {e}")
        return trial_id, {"score": float("-inf"), "success": False, "error": str(e)}


class ParallelOptimizer:
    """Ultra-fast parallel optimizer using cached preprocessing."""

    def __init__(
        self,
        config_dict: dict[str, Any],
        n_workers: int | None = None,
        cache_dir: str = "cache/optimization",
        study_db_path: str = "cache/optimization/optuna_studies.db",
    ):
        self.config_dict = config_dict
        self.n_workers = n_workers or min(12, mp.cpu_count())  # M3 Pro optimization
        self.cache = PreprocessingCache(cache_dir)
        self.cache_key: str | None = None
        self.study_db_path = study_db_path

        # Ensure study database directory exists
        Path(study_db_path).parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"ParallelOptimizer initialized with {self.n_workers} workers")
        logger.info(f"Study persistence: {study_db_path}")

    def precompute_data(self) -> str:
        """Precompute and cache all expensive operations."""
        cache_key = self.cache.precompute_for_optimization(self.config_dict)
        if cache_key is None:
            raise RuntimeError("Failed to generate cache key")
        self.cache_key = cache_key
        return self.cache_key

    def run_random_optimization(
        self,
        n_trials: int,
        timeout_seconds: int = 1800,
        data_fraction: float = 1.0,
        enable_pruning: bool = False,
        study_name: str | None = None,
    ) -> optuna.Study:
        """Run random optimization with true parallelism and persistent storage."""

        if not self.cache_key:
            self.precompute_data()

        if study_name is None:
            study_name = f"random_opt_{int(time.time())}"
        logger.info(
            f"Starting random optimization: {n_trials} trials, {self.n_workers} workers"
        )
        logger.info(f"Study: {study_name}, Storage: {self.study_db_path}")

        # Create study with persistent storage
        storage_url = f"sqlite:///{self.study_db_path}"
        study = optuna.create_study(
            direction="maximize",
            sampler=RandomSampler(seed=42),
            pruner=MedianPruner() if enable_pruning else optuna.pruners.NopPruner(),
            study_name=study_name,
            storage=storage_url,
            load_if_exists=True,
        )

        start_time = time.time()
        completed_trials = 0

        # Ensure data is precomputed
        if self.cache_key is None:
            self.precompute_data()

        assert self.cache_key is not None, (
            "Cache key should be available after precompute_data"
        )

        # Generate all trial parameters upfront
        trial_params = []
        for trial_id in range(n_trials):
            params = self._generate_random_params()
            trial_params.append(
                (self.cache_key, params, data_fraction, trial_id)
            )  # Run trials in parallel
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            # Submit all trials
            future_to_trial = {
                executor.submit(run_single_trial, args): args[3]
                for args in trial_params
            }

            # Process results as they complete
            for future in as_completed(future_to_trial, timeout=timeout_seconds):
                trial_id = future_to_trial[future]

                try:
                    trial_id, result = future.result()

                    if result["success"]:
                        # Add trial to study
                        trial = study.ask()
                        study.tell(trial, result["score"])
                        completed_trials += 1

                        elapsed = time.time() - start_time
                        rate = completed_trials / elapsed if elapsed > 0 else 0

                        logger.info(
                            f"Trial {trial_id}: score={result['score']:.6f} "
                            f"({completed_trials}/{n_trials}, {rate:.1f} trials/s)"
                        )
                    else:
                        logger.warning(
                            f"Trial {trial_id} failed: {result.get('error', 'Unknown')}"
                        )

                except Exception as e:
                    logger.error(f"Trial {trial_id} error: {e}")

                # Check timeout
                if time.time() - start_time > timeout_seconds:
                    logger.warning(f"Timeout reached ({timeout_seconds}s)")
                    break

        elapsed = time.time() - start_time
        logger.info(
            f"Random optimization completed: {completed_trials} trials in {elapsed:.1f}s"
        )

        return study

    def run_bayesian_optimization(
        self,
        n_trials: int,
        timeout_seconds: int = 1800,
        initial_random_trials: int = 10,
        enable_multifidelity: bool = True,
        study_name: str | None = None,
    ) -> optuna.Study:
        """Run Bayesian optimization with TPE sampler and successive halving pruning."""

        if not self.cache_key:
            self.precompute_data()

        if study_name is None:
            study_name = f"bayesian_opt_{int(time.time())}"
        logger.info(
            f"Starting Bayesian optimization: {n_trials} trials, {self.n_workers} workers"
        )
        logger.info(f"Study: {study_name}, Storage: {self.study_db_path}")

        # Create study with advanced TPE sampler and successive halving pruner
        storage_url = f"sqlite:///{self.study_db_path}"

        sampler = TPESampler(
            n_startup_trials=max(10, n_trials // 20),  # Dynamic startup trials
            n_ei_candidates=24,  # Balance exploration/exploitation
            multivariate=True,  # Enable multivariate TPE for parameter correlations
            seed=42,
        )

        pruner = (
            SuccessiveHalvingPruner(
                min_resource=1,  # Start pruning after 1 step
                reduction_factor=3,  # Cut to 1/3 at each rung
                min_early_stopping_rate=0,  # Immediate pruning allowed
            )
            if enable_multifidelity
            else optuna.pruners.NopPruner()
        )

        study = optuna.create_study(
            direction="maximize",
            sampler=sampler,
            pruner=pruner,
            study_name=study_name,
            storage=storage_url,
            load_if_exists=True,
        )

        start_time = time.time()
        completed_trials = 0
        pruned_trials = 0

        # For Bayesian, we need to run trials sequentially to use feedback
        # But we can still parallelize the multi-fidelity evaluation

        for trial_num in range(n_trials):
            if time.time() - start_time > timeout_seconds:
                logger.warning(f"Timeout reached ({timeout_seconds}s)")
                break

            trial = study.ask()
            params = self._extract_params_from_trial(trial)

            try:
                if enable_multifidelity:
                    # Multi-fidelity evaluation with pruning
                    score = self._evaluate_multifidelity(params, trial)
                else:
                    # Single-shot evaluation
                    if self.cache_key is None:
                        self.precompute_data()
                    assert self.cache_key is not None, "Cache key should be available"
                    runner = FastTrialRunner(self.cache_key, self.cache)
                    result = runner.run_trial(params, 1.0)
                    score = result["score"] if result["success"] else float("-inf")

                study.tell(trial, score)
                completed_trials += 1

                elapsed = time.time() - start_time
                rate = completed_trials / elapsed if elapsed > 0 else 0

                logger.info(
                    f"Trial {trial_num}: score={score:.6f} "
                    f"({completed_trials}/{n_trials}, {rate:.1f} trials/s)"
                )

            except optuna.TrialPruned:
                study.tell(trial, state=optuna.trial.TrialState.PRUNED)
                pruned_trials += 1
                logger.debug(f"Trial {trial_num} pruned")

            except Exception as e:
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
                logger.error(f"Trial {trial_num} failed: {e}")

        elapsed = time.time() - start_time
        pruning_rate = pruned_trials / (completed_trials + pruned_trials) * 100

        logger.info(
            f"Bayesian optimization completed: {completed_trials} trials, "
            f"{pruned_trials} pruned ({pruning_rate:.1f}%) in {elapsed:.1f}s"
        )

        return study

    def _evaluate_multifidelity(
        self, params: dict[str, Any], trial: optuna.Trial
    ) -> float:
        """Evaluate with multi-fidelity and successive halving pruning."""
        if self.cache_key is None:
            self.precompute_data()
        assert self.cache_key is not None, "Cache key should be available"
        runner = FastTrialRunner(self.cache_key, self.cache)

        # Stage 1: Quick evaluation (30% data) - Resource level 1
        result = runner.run_trial(params, 0.3)
        if not result["success"]:
            return float("-inf")

        score_30 = float(result["score"])
        trial.report(score_30, step=1)  # Report as resource level 1

        if trial.should_prune():
            raise optuna.TrialPruned()

        # Stage 2: Intermediate evaluation (60% data) - Resource level 2
        result = runner.run_trial(params, 0.6)
        if not result["success"]:
            return score_30  # Return partial result

        score_60 = float(result["score"])
        trial.report(score_60, step=2)  # Report as resource level 2

        if trial.should_prune():
            raise optuna.TrialPruned()

        # Stage 3: Full evaluation (100% data) - Resource level 3
        # Only for promising candidates that pass successive halving
        result = runner.run_trial(params, 1.0)
        if result["success"]:
            score_100 = float(result["score"])
            trial.report(score_100, step=3)  # Report as resource level 3
            return score_100

        return score_60

    def _generate_random_params(self) -> dict[str, Any]:
        """Generate random parameters for optimization."""
        return {
            # Core risk parameters
            "risk_per_trade": np.random.uniform(0.005, 0.025),
            "tp_rr": np.random.uniform(2.0, 4.0),
            "sl_atr_multiple": np.random.uniform(1.0, 2.5),
            # Zone detection parameters
            "zone_min_strength": np.random.uniform(0.5, 2.0),
            "pool_strength_threshold": np.random.uniform(0.3, 1.0),
            # FVG detection parameters
            "min_gap_atr": np.random.uniform(0.15, 0.4),
            "min_gap_pct": np.random.uniform(0.01, 0.05),
            "min_rel_vol": np.random.uniform(0.5, 2.5),
            # Candidate filtering parameters
            "ema_tolerance_pct": np.random.uniform(0.0005, 0.003),
            "volume_multiple": np.random.uniform(0.0, 3.0),
            "min_entry_spacing": np.random.randint(
                30, 121
            ),  # randint is exclusive of upper bound
        }

    def _extract_params_from_trial(self, trial: optuna.Trial) -> dict[str, Any]:
        """Extract parameters from Optuna trial."""
        return {
            # Core risk parameters
            "risk_per_trade": trial.suggest_float("risk_per_trade", 0.005, 0.025),
            "tp_rr": trial.suggest_float("tp_rr", 2.0, 4.0),
            "sl_atr_multiple": trial.suggest_float("sl_atr_multiple", 1.0, 2.5),
            # Zone detection parameters
            "zone_min_strength": trial.suggest_float("zone_min_strength", 0.5, 2.0),
            "pool_strength_threshold": trial.suggest_float(
                "pool_strength_threshold", 0.3, 1.0
            ),
            # FVG detection parameters
            "min_gap_atr": trial.suggest_float("min_gap_atr", 0.15, 0.4),
            "min_gap_pct": trial.suggest_float("min_gap_pct", 0.01, 0.05),
            "min_rel_vol": trial.suggest_float("min_rel_vol", 0.5, 2.5),
            # Candidate filtering parameters
            "ema_tolerance_pct": trial.suggest_float(
                "ema_tolerance_pct", 0.0005, 0.003
            ),
            "volume_multiple": trial.suggest_float("volume_multiple", 0.0, 3.0),
            "min_entry_spacing": trial.suggest_int("min_entry_spacing", 30, 120),
        }

    def get_cache_stats(self) -> dict[str, Any]:
        """Get optimization cache statistics."""
        return self.cache.get_cache_stats()

    def get_study_info(self, study_name: str) -> dict[str, Any]:
        """Get information about an existing study."""
        try:
            storage_url = f"sqlite:///{self.study_db_path}"
            study = optuna.load_study(study_name=study_name, storage=storage_url)

            return {
                "study_name": study.study_name,
                "direction": study.direction.name,
                "n_trials": len(study.trials),
                "best_value": study.best_value if study.best_trial else None,
                "best_params": study.best_params if study.best_trial else None,
                "sampler": type(study.sampler).__name__,
                "pruner": type(study.pruner).__name__,
            }
        except Exception as e:
            return {"error": str(e)}

    def list_studies(self) -> list[str]:
        """List all available study names in the database."""
        try:
            storage_url = f"sqlite:///{self.study_db_path}"
            study_names = optuna.study.get_all_study_names(storage=storage_url)
            return list(study_names) if study_names else []
        except Exception as e:
            logger.error(f"Failed to list studies: {e}")
            return []


def benchmark_optimization_speed() -> None:
    """Benchmark the optimization speed improvements with persistent storage."""

    # Mock configuration for testing
    config_dict = {
        "data": {
            "path": "data/BTCUSDT_5m_2025-05-18_futures.csv",
            "start_date": "2025-05-18",
            "end_date": "2025-05-20",
        },
        "strategy": {"htf_list": ["60", "240"]},
        "aggregation": {},
        "indicators": {},
        "walk_forward": {"folds": 2, "train_fraction": 0.7},
    }

    optimizer = ParallelOptimizer(config_dict, n_workers=8)

    print("🚀 Benchmarking Enhanced Optimization Speed")
    print("=" * 50)

    # Test preprocessing caching
    print("\n1. Testing preprocessing cache...")
    start_time = time.time()
    cache_key = optimizer.precompute_data()
    cache_time = time.time() - start_time
    print(f"   Preprocessing: {cache_time:.1f}s (cached as {cache_key})")

    # List existing studies
    studies = optimizer.list_studies()
    if studies:
        print(f"\n📋 Existing studies: {studies}")

    # Test parallel random optimization with persistence
    print("\n2. Testing persistent random optimization...")
    start_time = time.time()
    _ = optimizer.run_random_optimization(
        n_trials=10, timeout_seconds=120, study_name="benchmark_random"
    )
    random_time = time.time() - start_time
    print(
        f"   Random (10 trials): {random_time:.1f}s ({random_time / 10:.1f}s per trial)"
    )

    # Test Bayesian optimization with enhanced settings
    print("\n3. Testing enhanced Bayesian optimization...")
    start_time = time.time()
    _ = optimizer.run_bayesian_optimization(
        n_trials=5,
        timeout_seconds=120,
        enable_multifidelity=True,
        study_name="benchmark_bayesian",
    )
    bayesian_time = time.time() - start_time
    print(
        f"   Bayesian (5 trials): {bayesian_time:.1f}s ({bayesian_time / 5:.1f}s per trial)"
    )

    # Show study information
    random_info = optimizer.get_study_info("benchmark_random")
    bayesian_info = optimizer.get_study_info("benchmark_bayesian")

    print("\n📊 Study Information:")
    print(
        f"   Random study: {random_info.get('n_trials', 0)} trials, "
        f"best: {random_info.get('best_value', 'N/A')}"
    )
    print(
        f"   Bayesian study: {bayesian_info.get('n_trials', 0)} trials, "
        f"best: {bayesian_info.get('best_value', 'N/A')}"
    )

    # Show cache stats
    stats = optimizer.get_cache_stats()
    print("\n� Cache Stats:")
    print(f"   Memory entries: {stats['memory_entries']}")
    print(f"   Disk files: {stats['disk_files']}")
    print(f"   Total size: {stats['total_size_mb']:.1f} MB")
    print(f"   Study database: {optimizer.study_db_path}")

    total_time = cache_time + random_time + bayesian_time
    print("\n✅ Enhanced benchmark complete!")
    print(f"   Total time: {total_time:.1f}s")
    print(f"   Speed: {15 / total_time:.1f} trials/s (15 total trials)")
    print(
        "   Features: ✅ Persistent storage ✅ TPE+multivariate ✅ Successive halving"
    )


if __name__ == "__main__":
    benchmark_optimization_speed()
