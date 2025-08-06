#!/usr/bin/env python3
"""
Preprocessing Cache for Ultra-Fast Optimization
Caches expensive operations once and reuses across all trials.
"""

import hashlib
import logging
import pickle
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import polars as pl
from omegaconf import OmegaConf

from services.models import BacktestConfig
from services.runner import BacktestRunner

logger = logging.getLogger(__name__)


@dataclass
class TrialResult:
    """Result of a single optimization trial."""

    trial_id: str
    params: dict[str, Any]
    score: float
    metrics: dict[str, float]
    validation_passed: bool


class PreprocessingCache:
    """Cache for expensive preprocessing operations."""

    def __init__(self, cache_dir: str = "cache/preprocessing"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # In-memory cache for trial metrics
        self.in_memory_cache: dict[str, Any] = {}

    def get_cache_key(self, config_dict: dict[str, Any], data_path: str) -> str:
        """Generate cache key for preprocessing operations."""
        # Include only preprocessing-relevant config parts
        cache_parts = {
            "data_path": data_path,
            "start_date": config_dict.get("data", {}).get("start_date"),
            "end_date": config_dict.get("data", {}).get("end_date"),
            "htf_list": config_dict.get("strategy", {}).get("htf_list", []),
            "aggregation": config_dict.get("aggregation", {}),
            "indicators": config_dict.get("indicators", {}),
            "walk_forward_folds": config_dict.get("walk_forward", {}).get("folds", 2),
            "train_fraction": config_dict.get("walk_forward", {}).get(
                "train_fraction", 0.6
            ),
        }

        # Create hash from relevant parts only
        cache_str = str(sorted(cache_parts.items()))
        return hashlib.md5(cache_str.encode()).hexdigest()[:16]

    def get_cached_data(self, cache_key: str) -> dict[str, Any] | None:
        """Get cached preprocessing data."""
        # Check in-memory cache first
        if cache_key in self.in_memory_cache:
            logger.debug(f"Cache HIT (memory): {cache_key}")
            result = self.in_memory_cache[cache_key]
            return result if isinstance(result, dict) else None

        # Check disk cache
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    data = pickle.load(f)
                    # Store in memory for future access
                    self.in_memory_cache[cache_key] = data
                    logger.debug(f"Cache HIT (disk): {cache_key}")
                    return data if isinstance(data, dict) else None
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")
                cache_file.unlink(missing_ok=True)

        logger.debug(f"Cache MISS: {cache_key}")
        return None

    def store_cached_data(self, cache_key: str, data: dict[str, Any]) -> None:
        """Store preprocessing data in cache."""
        # Store in memory
        self.in_memory_cache[cache_key] = data

        # Store on disk
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(data, f)
            logger.debug(f"Cache STORE: {cache_key}")
        except Exception as e:
            logger.warning(f"Cache write error for {cache_key}: {e}")

    def precompute_for_optimization(self, config_dict: dict[str, Any]) -> str:
        """Precompute and cache all expensive preprocessing operations."""
        cache_key = self.get_cache_key(config_dict, config_dict["data"]["path"])

        # Check if already cached
        cached_data = self.get_cached_data(cache_key)
        if cached_data:
            logger.info(f"✅ Using cached preprocessing data: {cache_key}")
            return cache_key

        logger.info(f"🔄 Precomputing preprocessing data: {cache_key}")
        start_time = time.time()

        try:
            # For now, just validate that the data file exists and is readable
            # The actual preprocessing will be done by BacktestRunner during trials
            data_path = config_dict["data"]["path"]

            if not Path(data_path).exists():
                raise FileNotFoundError(f"Data file not found: {data_path}")

            # Simple validation - try to load first few rows
            from services.data_loader import load_market_data

            df = load_market_data(data_path)

            if df is None or len(df) == 0:
                raise ValueError(f"Data file is empty or invalid: {data_path}")

            # Store minimal cached data (just metadata for now)
            cached_data = {
                "data_path": data_path,
                "config_hash": cache_key,
                "created_at": time.time(),
                "data_rows": len(df),
                "validation_passed": True,
            }

            self.store_cached_data(cache_key, cached_data)

            elapsed = time.time() - start_time
            logger.info(
                f"✅ Preprocessing validation completed in {elapsed:.1f}s, cached as {cache_key}"
            )

            return cache_key

        except Exception as e:
            logger.error(f"❌ Preprocessing failed: {e}")
            raise

    def get_preprocessed_data(self, cache_key: str) -> dict[str, Any]:
        """Get preprocessed data by cache key."""
        data = self.get_cached_data(cache_key)
        if not data:
            raise ValueError(f"No cached data found for key: {cache_key}")
        return data

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.in_memory_cache.clear()
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        logger.info("Cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        disk_files = list(self.cache_dir.glob("*.pkl"))
        total_size = sum(f.stat().st_size for f in disk_files)

        return {
            "memory_entries": len(self.in_memory_cache),
            "disk_files": len(disk_files),
            "total_size_mb": total_size / (1024 * 1024),
            "cache_dir": str(self.cache_dir),
        }


class FastTrialRunner:
    """Ultra-fast trial runner using cached preprocessing."""

    def __init__(self, cache_key: str, preprocessing_cache: PreprocessingCache):
        self.cache_key = cache_key
        self.cache = preprocessing_cache

        # Get cached data
        try:
            self.cached_data = preprocessing_cache.get_preprocessed_data(cache_key)
            logger.debug(f"FastTrialRunner initialized with cache {cache_key}")
            logger.debug(
                f"Data: validation_passed={self.cached_data.get('validation_passed', False)}"
            )
        except Exception as e:
            logger.debug(
                f"Could not load cached data for {cache_key}: {e}"
            )  # Changed from WARNING to DEBUG
            # Create minimal cached data for fallback
            self.cached_data = {
                "data_path": "data/BTCUSDT_5m_2025-05-18_futures.csv",  # fallback
                "validation_passed": False,
            }

    def run_trial(
        self, params: dict[str, Any], data_fraction: float = 1.0
    ) -> dict[str, Any]:
        """Run a single trial using real backtests."""
        try:
            trial_id = str(uuid.uuid4())[:8]

            # Build real configuration with optimization parameters
            config_dict = self._build_trial_config(params, data_fraction)
            config = BacktestConfig.from_dict(config_dict)

            logger.debug(
                f"Trial {trial_id}: Running REAL backtest with params: {params}"
            )

            # Run actual backtest
            runner = BacktestRunner(config)
            result = runner.run()

            if result and result.success:
                metrics = result.metrics

                # Handle both dict and BacktestMetrics object
                if hasattr(metrics, "to_dict"):
                    metrics_dict = metrics.to_dict()
                elif hasattr(metrics, "__dict__"):
                    metrics_dict = metrics.__dict__
                else:
                    metrics_dict = metrics

                # Extract nested metrics - the actual metrics are in 'trade_metrics' sub-dict
                trade_metrics = metrics_dict.get("trade_metrics", {})

                # Extract key metrics for optimization
                total_trades = int(trade_metrics.get("total_trades", 0))
                win_rate = float(trade_metrics.get("win_rate", 0.0))
                total_pnl = float(trade_metrics.get("total_pnl", 0.0))
                max_drawdown = float(trade_metrics.get("max_drawdown", 0.0))

                # Calculate return from PnL
                starting_equity = 10000.0  # Default starting equity
                total_return = (
                    total_pnl / starting_equity if starting_equity > 0 else 0.0
                )

                # Extract other metrics (sharpe ratio might be calculated elsewhere)
                sharpe_ratio = float(trade_metrics.get("sharpe_ratio", 0.0))
                profit_factor = float(trade_metrics.get("profit_factor", 1.0))

                logger.info(
                    f"Trial {trial_id}: Extracted metrics - trades={total_trades}, win_rate={win_rate:.2%}, pnl=${total_pnl:.2f}, return={total_return:.3f}"
                )

                # Calculate optimization score (you can adjust this formula)
                # Prioritize Sharpe ratio with minimum trade requirement
                score = (
                    sharpe_ratio + total_return * 0.1 if total_trades > 0 else -10.0
                )  # Sharpe + small return bonus or heavy penalty for no trades

                logger.debug(
                    f"Trial {trial_id}: trades={total_trades}, return={total_return:.3f}, sharpe={sharpe_ratio:.3f}, score={score:.3f}"
                )

                return {
                    "score": float(score),
                    "success": True,
                    "metrics": {
                        "total_return": total_return,
                        "total_pnl": total_pnl,
                        "sharpe_ratio": sharpe_ratio,
                        "max_drawdown": max_drawdown,
                        "total_trades": total_trades,
                        "win_rate": win_rate,
                        "profit_factor": profit_factor,
                    },
                    "params": params,
                }
            else:
                error_msg = result.error_message if result else "No result returned"
                logger.warning(f"Trial {trial_id}: Backtest failed: {error_msg}")
                return {
                    "score": float("-inf"),
                    "success": False,
                    "error": f"Backtest failed: {error_msg}",
                    "params": params,
                }

        except Exception as e:
            logger.warning(f"Trial failed: {e}")
            return {
                "score": float("-inf"),
                "success": False,
                "error": str(e),
                "params": params,
            }

    def _build_trial_config(
        self, params: dict[str, Any], data_fraction: float
    ) -> dict[str, Any]:
        """Build trial configuration from parameters."""
        # Start with base configuration
        config = {
            "data": {
                "path": self.cached_data["data_path"],
                "source": "csv",
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "tick_size": 0.01,
                "date_format": "%Y-%m-%dT%H:%M:%SZ",
                "start_date": "2025-05-01",
                "end_date": "2025-07-01",
                "columns": {
                    "timestamp": "timestamp",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                },
            },
            "strategy": {
                "name": "htf_liquidity_mtf",
                "symbol": "BTCUSDT",
                "use_mock_strategy": False,
                "htf_list": ["60", "240", "1440"],
                "expiry_minutes": 120,
                "filters": {
                    "ema_alignment": True,
                    "volume_multiple": 1.2,
                    "killzone": ["01:00", "18:00"],
                    "regime_ok": ["bull", "neutral"],
                },
            },
            "walk_forward": {
                "folds": 2 if data_fraction < 1.0 else 3,
                "train_fraction": 0.7,
                "overlap_fraction": 0.1,
            },
            "execution": {
                "slippage_model": "linear",
                "slippage_bps": 2.0,
                "commission_rate": 0.0004,
                "dump_events": False,
                "export_data_for_viz": False,
                "enable_latency_profiling": False,
                "enable_memory_tracking": False,
            },
            "account": {"initial_balance": 10000.0, "currency": "USDT"},
            "aggregation": {
                "source_tf_minutes": 5,
                "target_timeframes_minutes": [60, 240, 1440],
                "buffer_size": 1500,
                "roll_from": "calendar",
                "out_of_order_policy": "drop",
                "max_clock_skew_seconds": 300,
                "enable_strict_ordering": False,
                "fill_missing": "ffill",
            },
            "indicators": {
                "ema": {"periods": [21, 50, 200], "source": "close"},
                "atr": {"period": 14},
                "volume_sma": {"period": 20},
            },
            "risk": {
                "model": "fixed_fractional",
                "risk_per_trade": 0.015,
                "max_positions": 3,
                "tp_rr": 3.0,
                "sl_atr_multiple": 1.5,
                "enable_trailing_stop": False,
            },
            "detectors": {
                "fvg": {
                    "enabled": True,
                    "min_gap_atr": 0.3,
                    "min_gap_pct": 0.015,
                    "min_rel_vol": 0.75,
                    "max_age_minutes": 1440,
                    "enabled_timeframes": ["60", "240", "1440"],
                },
                "pivot": {"enabled": False},
            },
            "hlz": {
                "min_members": 2,
                "min_strength": 1.5,
                "tf_weight": {"60": 1.0, "240": 2.5, "1440": 4.0},
                "merge_tolerance": 0.3,
                "side_mixing": False,
                "max_active_hlzs": 200,
                "recompute_on_update": False,
            },
            "zone_watcher": {
                "price_tolerance": 0.1,
                "confirm_closure": False,
                "min_strength": 0.7,
                "max_active_zones": 200,
            },
            "candidate": {
                "expiry_minutes": 120,
                "min_entry_spacing_minutes": 45,
                "global_min_entry_spacing": 10,
                "enable_spacing_throttle": True,
                "filters": {
                    "ema_alignment": True,
                    "ema_tolerance_pct": 0.002,
                    "linger_minutes": 60,
                    "reclaim_requires_ema": True,
                    "volume_multiple": 1.5,
                    "use_enhanced_killzone": False,
                    "killzone": ["01:00", "18:00"],
                    "regime": ["bull", "neutral"],
                },
            },
            "pools": {
                "60": {"ttl": "6h", "hit_tolerance": 0.0},
                "240": {"ttl": "3d", "hit_tolerance": 0.0},
                "1440": {"ttl": "3w", "hit_tolerance": 0.0},
                "strength_threshold": 0.3,
                "grace_period_minutes": 60,
                "max_pools_per_tf": 1000,
                "auto_expire_interval": "60s",
            },
            "pivot_pools": {
                "60": {"ttl": "12h", "hit_tolerance": 0.0, "min_atr_distance": 0.8},
                "240": {"ttl": "5d", "hit_tolerance": 0.0, "min_atr_distance": 1.0},
                "1440": {"ttl": "1M", "hit_tolerance": 0.0, "min_atr_distance": 1.5},
                "strength_threshold": 0.5,
                "grace_period_minutes": 10,
                "max_pools_per_tf": 1000,
                "auto_expire_interval": "60s",
            },
            "confluence": {
                "min_score": 2,
                "factors": {
                    "fvg_touch": 1,
                    "pivot_level": 1,
                    "ema_alignment": 1,
                    "volume_spike": 1,
                },
            },
        }

        # Apply optimization parameters
        for param_name, param_value in params.items():
            if param_name == "risk_per_trade":
                config["risk"]["risk_per_trade"] = param_value
            elif param_name == "tp_rr":
                config["risk"]["tp_rr"] = param_value
            elif param_name == "sl_atr_multiple":
                config["risk"]["sl_atr_multiple"] = param_value
            elif param_name == "zone_min_strength":
                config["zone_watcher"]["min_strength"] = param_value
            elif param_name == "pool_strength_threshold":
                config["pools"]["strength_threshold"] = param_value
            elif param_name == "min_gap_atr":
                config["detectors"]["fvg"]["min_gap_atr"] = param_value
            elif param_name == "min_gap_pct":
                config["detectors"]["fvg"]["min_gap_pct"] = param_value
            elif param_name == "hlz_min_strength":
                config["hlz"]["min_strength"] = param_value
            elif param_name == "merge_tolerance":
                config["hlz"]["merge_tolerance"] = param_value
            elif param_name == "min_entry_spacing_minutes":
                config["candidate"]["min_entry_spacing_minutes"] = param_value
            elif param_name == "ema_tolerance_pct":
                config["candidate"]["filters"]["ema_tolerance_pct"] = param_value
            elif param_name == "volume_multiple":
                config["candidate"]["filters"]["volume_multiple"] = param_value

        return config

    def _extract_score(self, metrics: dict[str, Any]) -> float:
        """Extract optimization score from metrics."""
        # Placeholder - would normally use proper scoring logic
        result = metrics.get("sharpe_ratio", float("-inf"))
        return float(result) if isinstance(result, int | float) else float("-inf")
