#!/usr/bin/env python3
"""
Production-Grade Optimization Demo
Demonstrates all the enhanced features of ParallelOptimizer:

✅ Persistent study storage (SQLite)
✅ TPE sampler with multivariate=True
✅ SuccessiveHalvingPruner for multi-fidelity
✅ True parallelism with ProcessPoolExecutor
✅ Advanced caching with preprocessing
✅ Study resumption capabilities
"""

import logging
import time
from pathlib import Path

from services.parallel_optimizer import ParallelOptimizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def demonstrate_production_optimization():
    """Demonstrate production-grade optimization features."""

    print("🚀 Production-Grade Optimization Demo")
    print("=" * 60)

    # Configuration for BTC optimization
    config_dict = {
        "data": {
            "path": "data/BTC_USD_5min_20250801_160031.csv",
            "start_date": "2025-07-01",
            "end_date": "2025-08-01",
        },
        "strategy": {
            "name": "htf_liquidity_mtf",
            "htf_list": ["H4", "D1"],
            "filters": {"killzone": ["01:00", "18:00"], "volume_multiple": 1.5},
        },
        "walk_forward": {"folds": 3, "train_fraction": 0.7, "overlap_fraction": 0.1},
        "aggregation": {},
        "indicators": {},
    }

    # Initialize optimizer with custom database path
    study_db = "cache/optimization/production_studies.db"
    optimizer = ParallelOptimizer(
        config_dict,
        n_workers=10,  # Use 10 cores for M3 Pro
        study_db_path=study_db,
    )

    print("\n📊 Optimizer Configuration:")
    print(f"   Workers: {optimizer.n_workers}")
    print(f"   Study DB: {study_db}")
    print(f"   Cache: {optimizer.cache.cache_dir}")

    # 1. Precompute expensive operations
    print("\n⚡ Phase 1: Preprocessing & Caching")
    print("-" * 40)
    start_time = time.time()
    cache_key = optimizer.precompute_data()
    precompute_time = time.time() - start_time
    print(f"✅ Preprocessing completed in {precompute_time:.1f}s")
    print(f"   Cache key: {cache_key}")

    # 2. List existing studies (if any)
    studies = optimizer.list_studies()
    if studies:
        print(f"\n📋 Existing Studies: {len(studies)}")
        for study_name in studies[-3:]:  # Show last 3
            info = optimizer.get_study_info(study_name)
            print(
                f"   {study_name}: {info.get('n_trials', 0)} trials, "
                f"best={info.get('best_value', 'N/A')}"
            )

    # 3. Random exploration phase
    print("\n🎲 Phase 2: Random Exploration")
    print("-" * 40)
    study_name_random = f"prod_random_{int(time.time())}"

    start_time = time.time()
    random_study = optimizer.run_random_optimization(
        n_trials=20,
        timeout_seconds=600,  # 10 minute timeout
        data_fraction=0.5,  # Use 50% data for speed
        enable_pruning=False,
        study_name=study_name_random,
    )
    random_time = time.time() - start_time

    print(
        f"✅ Random exploration: {len(random_study.trials)} trials in {random_time:.1f}s"
    )
    print(f"   Rate: {len(random_study.trials) / random_time:.1f} trials/s")
    if random_study.best_trial:
        print(f"   Best score: {random_study.best_value:.6f}")

    # 4. Bayesian optimization phase
    print("\n🧠 Phase 3: Bayesian Optimization")
    print("-" * 40)
    study_name_bayesian = f"prod_bayesian_{int(time.time())}"

    start_time = time.time()
    bayesian_study = optimizer.run_bayesian_optimization(
        n_trials=15,
        timeout_seconds=900,  # 15 minute timeout
        initial_random_trials=5,
        enable_multifidelity=True,
        study_name=study_name_bayesian,
    )
    bayesian_time = time.time() - start_time

    print(
        f"✅ Bayesian optimization: {len(bayesian_study.trials)} trials in {bayesian_time:.1f}s"
    )
    print(f"   Rate: {len(bayesian_study.trials) / bayesian_time:.1f} trials/s")
    if bayesian_study.best_trial:
        print(f"   Best score: {bayesian_study.best_value:.6f}")
        print(f"   Best params: {bayesian_study.best_params}")

    # 5. Study persistence demo
    print("\n💾 Phase 4: Study Persistence Demo")
    print("-" * 40)

    # Show that we can reload studies
    random_info = optimizer.get_study_info(study_name_random)
    bayesian_info = optimizer.get_study_info(study_name_bayesian)

    print("📈 Random Study Info:")
    for key, value in random_info.items():
        if key != "best_params":
            print(f"   {key}: {value}")

    print("\n🎯 Bayesian Study Info:")
    for key, value in bayesian_info.items():
        if key != "best_params":
            print(f"   {key}: {value}")

    # 6. Performance summary
    total_time = precompute_time + random_time + bayesian_time
    total_trials = len(random_study.trials) + len(bayesian_study.trials)

    print("\n📊 Performance Summary")
    print("-" * 40)
    print(f"   Total time: {total_time:.1f}s")
    print(f"   Total trials: {total_trials}")
    print(f"   Overall rate: {total_trials / total_time:.1f} trials/s")
    print("   Cache efficiency: ✅ Preprocessing reused")
    print(f"   Study persistence: ✅ {Path(study_db).exists()}")

    # 7. Cache statistics
    cache_stats = optimizer.get_cache_stats()
    print("\n💽 Cache Statistics:")
    print(f"   Memory entries: {cache_stats['memory_entries']}")
    print(f"   Disk files: {cache_stats['disk_files']}")
    print(f"   Total size: {cache_stats['total_size_mb']:.1f} MB")

    print("\n🎉 Production optimization demo completed!")
    print(f"   Studies saved to: {study_db}")
    print(f"   Cache saved to: {optimizer.cache.cache_dir}")

    return {
        "random_study": random_study,
        "bayesian_study": bayesian_study,
        "cache_key": cache_key,
        "performance": {
            "total_time": total_time,
            "total_trials": total_trials,
            "rate": total_trials / total_time,
        },
    }


def demonstrate_study_resumption():
    """Demonstrate study resumption capabilities."""

    print("\n🔄 Study Resumption Demo")
    print("=" * 40)

    # Create optimizer (same config as before)
    config_dict = {"data": {"path": "data/test.csv"}, "strategy": {}}
    optimizer = ParallelOptimizer(config_dict)

    # List all studies
    studies = optimizer.list_studies()
    if not studies:
        print("   No existing studies found. Run main demo first.")
        return

    print(f"   Found {len(studies)} existing studies:")
    for study_name in studies:
        info = optimizer.get_study_info(study_name)
        print(f"   • {study_name}: {info.get('n_trials', 0)} trials")

    # Try to resume the latest Bayesian study
    latest_bayesian = [s for s in studies if "bayesian" in s]
    if latest_bayesian:
        study_name = latest_bayesian[-1]
        print(f"\n   Resuming study: {study_name}")

        # This would continue optimization from where it left off
        resumed_study = optimizer.run_bayesian_optimization(
            n_trials=5,  # Add 5 more trials
            timeout_seconds=180,
            study_name=study_name,  # Same name = resume
        )

        print(f"   ✅ Added {len(resumed_study.trials)} total trials")
        print(f"   Best score: {resumed_study.best_value:.6f}")


if __name__ == "__main__":
    # Run main demonstration
    results = demonstrate_production_optimization()

    # Demonstrate resumption
    demonstrate_study_resumption()

    print("\n✨ All demonstrations completed successfully!")
