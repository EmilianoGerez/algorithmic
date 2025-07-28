"""
Core backtesting runner that orchestrates strategy execution with replay engine.

This module provides the main BacktestRunner class that coordinates:
- Data loading and validation
- Strategy initialization
- Broker setup and configuration
- Replay engine execution
- Results collection and analysis
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from core.strategy.factory import StrategyFactory
from services.data_loader import DataLoader, create_candle_stream
from services.metrics import MetricsCollector
from services.models import BacktestConfig, BacktestResult
from services.replay import ReplayEngine, ReplayMode, create_backtest_replay

logger = logging.getLogger(__name__)


class BacktestRunner:
    """Main backtesting execution engine with full configuration management."""

    def __init__(self, config: BacktestConfig):
        """Initialize backtest runner with configuration.

        Args:
            config: Complete backtest configuration
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize components
        self.data_loader = DataLoader(config.data)
        self.metrics_collector = MetricsCollector(
            enable_latency_profiling=config.execution.enable_latency_profiling,
            enable_memory_tracking=config.execution.enable_memory_tracking,
        )

        # Will be set during execution
        self.strategy: Any | None = None
        self.broker: Any | None = None
        self.replay_engine: ReplayEngine | None = None

    def setup_logging(self) -> None:
        """Configure logging based on configuration."""
        log_level = getattr(logging, self.config.execution.log_level.upper())

        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
            ],
        )

        # Add file handler if log file specified
        if self.config.execution.log_file:
            file_handler = logging.FileHandler(self.config.execution.log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            logging.getLogger().addHandler(file_handler)

    def validate_configuration(self) -> None:
        """Validate backtest configuration before execution."""
        self.logger.info("Validating backtest configuration")

        # Check data file exists
        if not Path(self.config.data.path).exists():
            raise FileNotFoundError(f"Data file not found: {self.config.data.path}")

        # Validate date range
        if (
            self.config.data.start_date
            and self.config.data.end_date
            and self.config.data.start_date >= self.config.data.end_date
        ):
            raise ValueError("start_date must be before end_date")

        # Validate strategy configuration
        if not self.config.strategy.name:
            raise ValueError("Strategy name is required")

        # Validate account configuration
        if self.config.account.initial_balance <= 0:
            raise ValueError("Initial balance must be positive")

        self.logger.info("Configuration validation passed")

    def create_audit_trail(self) -> dict[str, Any]:
        """Create audit trail for deterministic reproduction.

        Returns:
            Dictionary with environment and configuration details
        """
        try:
            git_hash = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=Path(__file__).parent.parent,
                text=True,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_hash = "unknown"

        return {
            "timestamp": datetime.now().isoformat(),
            "git_hash": git_hash,
            "config_hash": hash(str(self.config.model_dump())),
            "python_version": f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}.{__import__('sys').version_info.micro}",
            "config": self.config.model_dump(),
        }

    def initialize_strategy(self) -> None:
        """Initialize strategy based on configuration."""
        self.logger.info(f"Initializing strategy: {self.config.strategy.symbol}")

        # Use StrategyFactory to build complete strategy
        self.strategy = StrategyFactory.build(
            config=self.config, metrics_collector=self.metrics_collector
        )

        self.logger.info("Strategy initialized successfully")

    def initialize_broker(self) -> None:
        """Initialize broker based on configuration."""
        self.logger.info("Using integrated broker from strategy factory")

        # Broker is now integrated in the strategy
        # Get reference for replay engine compatibility
        if self.strategy is not None:
            self.broker = (
                self.strategy.broker if hasattr(self.strategy, "broker") else None
            )
        else:
            self.broker = None

        self.logger.info("Broker reference established")

    def load_market_data(self) -> Any:
        """Load and prepare market data for backtesting.

        Returns:
            Iterator of Candle objects
        """
        self.logger.info(f"Loading market data from: {self.config.data.path}")

        # Get data information and validate structure
        data_info = self.data_loader.get_data_info(self.config.data.path)
        self.logger.info(
            f"Dataset: {data_info['total_rows']} rows, "
            f"{data_info['date_range']['start']} to {data_info['date_range']['end']}"
        )

        # Create streaming data source
        candle_stream = self.data_loader.create_stream(
            self.config.data.path,
            use_csv_stream=self.config.execution.use_csv_streaming,
        )

        return candle_stream

    def create_replay_engine(self, candle_stream: Any) -> ReplayEngine:
        """Create and configure replay engine.

        Args:
            candle_stream: Iterator of market data candles

        Returns:
            Configured ReplayEngine
        """
        # Determine replay mode
        if self.config.execution.realtime_simulation:
            mode = ReplayMode.REALTIME
        else:
            mode = ReplayMode.FAST

        # Create replay engine
        self.replay_engine = create_backtest_replay(
            candle_stream=candle_stream,
            strategy=self.strategy,
            broker=self.broker,
            mode=mode,
            metrics_collector=self.metrics_collector,
        )

        return self.replay_engine

    def _export_visualization_data(
        self, replay_engine: ReplayEngine, candle_stream: Any, audit_trail: dict[str, Any]
    ) -> None:
        """Export data for visualization purposes.

        Args:
            replay_engine: The completed replay engine
            candle_stream: Original candle data stream
            audit_trail: Execution audit trail
        """
        try:
            # Try different import approaches
            try:
                from quant_algo.visual.data_exporter import BacktestDataExporter
            except ImportError:
                # Try relative import from current directory
                import sys
                import os
                sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                from quant_algo.visual.data_exporter import BacktestDataExporter
            
            from datetime import datetime
            import os

            # Create result directory based on current timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            result_dir = f"results/backtest_{timestamp}"
            os.makedirs(result_dir, exist_ok=True)

            # Initialize data exporter
            exporter = BacktestDataExporter(result_dir)
            
            self.logger.info(f"Exporting visualization data to {result_dir}")

            # Export market data
            # Re-create candle stream to export data
            fresh_candle_stream = self.data_loader.create_stream(
                self.config.data.path,
                use_csv_stream=self.config.execution.use_csv_streaming,
            )
            
            for candle in fresh_candle_stream:
                exporter.add_candle(
                    timestamp=candle.ts,
                    open_price=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume
                )

            # Export trades from broker if available
            if self.strategy and hasattr(self.strategy, 'broker') and self.strategy.broker:
                broker = self.strategy.broker
                # Export completed trades if broker has trade history
                try:
                    if hasattr(broker, 'get_trade_history'):
                        trades = broker.get_trade_history()
                        for trade in trades:
                            # Extract trade details - exact format depends on trade object
                            if hasattr(trade, 'id') and hasattr(trade, 'symbol'):
                                exporter.add_trade(
                                    trade_id=str(getattr(trade, 'id', 'unknown')),
                                    symbol=getattr(trade, 'symbol', 'UNKNOWN'),
                                    side=str(getattr(trade, 'side', 'BUY')),
                                    entry_ts=getattr(trade, 'entry_time', datetime.now()),
                                    exit_ts=getattr(trade, 'exit_time', datetime.now()),
                                    entry_price=float(getattr(trade, 'entry_price', 0.0)),
                                    exit_price=float(getattr(trade, 'exit_price', 0.0)),
                                    size=float(getattr(trade, 'size', 0.0)),
                                    pnl=float(getattr(trade, 'pnl', 0.0)),
                                    fees=float(getattr(trade, 'fees', 0.0)),
                                    exit_reason=str(getattr(trade, 'exit_reason', ''))
                                )
                    elif hasattr(broker, 'trades'):
                        trades = getattr(broker, 'trades', [])
                        for trade in trades:
                            # Similar processing for direct trades list
                            if hasattr(trade, 'id') or hasattr(trade, 'trade_id'):
                                trade_id = getattr(trade, 'id', getattr(trade, 'trade_id', 'unknown'))
                                exporter.add_trade(
                                    trade_id=str(trade_id),
                                    symbol=getattr(trade, 'symbol', 'UNKNOWN'),
                                    side=str(getattr(trade, 'side', 'BUY')),
                                    entry_ts=getattr(trade, 'entry_time', datetime.now()),
                                    exit_ts=getattr(trade, 'exit_time', datetime.now()),
                                    entry_price=float(getattr(trade, 'entry_price', 0.0)),
                                    exit_price=float(getattr(trade, 'exit_price', 0.0)),
                                    size=float(getattr(trade, 'size', 0.0)),
                                    pnl=float(getattr(trade, 'pnl', 0.0)),
                                    fees=float(getattr(trade, 'fees', 0.0)),
                                    exit_reason=str(getattr(trade, 'exit_reason', ''))
                                )
                except Exception as e:
                    self.logger.warning(f"Could not export trades: {e}")

            # Export events if dump_events is enabled
            if self.config.execution.dump_events:
                try:
                    # Export detector events if available
                    if self.strategy and hasattr(self.strategy, 'detectors'):
                        detectors = getattr(self.strategy, 'detectors', {})
                        
                        # Export FVG events
                        if 'fvg_detector' in detectors:
                            fvg_detector = detectors['fvg_detector']
                            if hasattr(fvg_detector, 'detected_fvgs'):
                                for fvg in getattr(fvg_detector, 'detected_fvgs', []):
                                    exporter.add_fvg_event(fvg)
                        
                        # Export pivot events  
                        if 'pivot_detector' in detectors:
                            pivot_detector = detectors['pivot_detector']
                            if hasattr(pivot_detector, 'detected_pivots'):
                                for pivot in getattr(pivot_detector, 'detected_pivots', []):
                                    exporter.add_pivot_event(pivot)
                except Exception as e:
                    self.logger.warning(f"Could not export events: {e}")

            # Finalize export
            exporter.finalize_events()
            
            self.logger.info(f"✅ Visualization data exported successfully to {result_dir}")
            
            # Store result directory for later use
            self._result_dir = result_dir

        except ImportError as e:
            self.logger.warning(f"Visualization export skipped - missing dependencies: {e}")
        except Exception as e:
            self.logger.error(f"Failed to export visualization data: {e}")

    def run(self) -> BacktestResult:
        """Execute the complete backtest.

        Returns:
            BacktestResult with performance metrics and metadata
        """
        try:
            # Setup and validation
            self.setup_logging()
            self.validate_configuration()

            self.logger.info("Starting backtest execution")
            start_time = datetime.now()

            # Create audit trail
            audit_trail = self.create_audit_trail()

            # Initialize components
            self.initialize_strategy()
            self.initialize_broker()

            # Load market data
            candle_stream = self.load_market_data()

            # Create and run replay engine
            replay_engine = self.create_replay_engine(candle_stream)
            replay_engine.run()

            # Export data for visualization if enabled
            if self.config.execution.export_data_for_viz:
                self._export_visualization_data(
                    replay_engine, candle_stream, audit_trail
                )

            # Collect results
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            # Get comprehensive metrics
            metrics_summary = self.metrics_collector.get_summary()
            self.metrics_collector.log_summary()

            # Create result
            result = BacktestResult(
                config=self.config,
                metrics=metrics_summary,
                execution_time_seconds=execution_time,
                start_time=start_time,
                end_time=end_time,
                audit_trail=audit_trail,
                success=True,
                error_message=None,
                result_dir=getattr(self, '_result_dir', None),
            )

            self.logger.info(
                f"Backtest completed successfully in {execution_time:.2f} seconds"
            )
            return result

        except Exception as e:
            error_msg = f"Backtest failed: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            # Return error result
            return BacktestResult(
                config=self.config,
                metrics={},
                execution_time_seconds=0.0,
                start_time=datetime.now(),
                end_time=datetime.now(),
                audit_trail=self.create_audit_trail(),
                success=False,
                error_message=error_msg,
            )

    def run_walk_forward(self) -> list[BacktestResult]:
        """Execute walk-forward analysis.

        Returns:
            List of BacktestResult objects for each fold
        """
        try:
            self.setup_logging()
            self.validate_configuration()

            self.logger.info("Starting walk-forward analysis")
            start_time = datetime.now()

            # Get walk-forward folds
            folds = self.data_loader.split_into_folds(
                self.config.data.path,
                self.config.walk_forward.folds,
                self.config.walk_forward.train_fraction,
            )

            results = []

            for fold_idx, (_train_data, test_data) in enumerate(folds, 1):
                self.logger.info(f"Processing fold {fold_idx}/{len(folds)}")

                # Create fold-specific configuration
                fold_config = self.config.model_copy(deep=True)

                # Initialize strategy for this fold
                fold_strategy = StrategyFactory.build(
                    config=fold_config.strategy,
                    metrics_collector=self.metrics_collector,
                )

                # Create candle stream from test data
                test_candle_stream = create_candle_stream(test_data, self.config.data)

                # Create replay engine for this fold
                replay_engine = create_backtest_replay(
                    candle_stream=test_candle_stream,
                    strategy=fold_strategy,
                    broker=fold_strategy.broker,
                    mode=ReplayMode.FAST,
                    metrics_collector=self.metrics_collector,
                )

                # Run fold
                fold_start_time = datetime.now()
                replay_engine.run()
                fold_end_time = datetime.now()

                # Collect fold results
                fold_execution_time = (fold_end_time - fold_start_time).total_seconds()
                fold_metrics = fold_strategy.get_performance_stats()

                # Create fold result
                fold_result = BacktestResult(
                    config=fold_config,
                    metrics=fold_metrics,
                    execution_time_seconds=fold_execution_time,
                    start_time=fold_start_time,
                    end_time=fold_end_time,
                    audit_trail=self.create_audit_trail(),
                    success=True,
                    error_message=None,
                    fold_id=fold_idx,
                    total_folds=len(folds),
                )

                results.append(fold_result)

                self.logger.info(
                    f"Fold {fold_idx} completed - Sharpe: {fold_metrics.get('sharpe_ratio', 0):.3f}"
                )

            # Log aggregate statistics
            end_time = datetime.now()
            total_execution_time = (end_time - start_time).total_seconds()

            if results:
                avg_sharpe = sum(
                    r.metrics.get("sharpe_ratio", 0) for r in results
                ) / len(results)
                avg_win_rate = sum(r.metrics.get("win_rate", 0) for r in results) / len(
                    results
                )

                self.logger.info(
                    f"Walk-forward analysis completed in {total_execution_time:.2f} seconds"
                )
                self.logger.info(
                    f"Average Sharpe: {avg_sharpe:.3f}, Average Win Rate: {avg_win_rate:.2%}"
                )

            return results

        except Exception as e:
            error_msg = f"Walk-forward analysis failed: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            # Return error result
            return [
                BacktestResult(
                    config=self.config,
                    metrics={},
                    execution_time_seconds=0.0,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    audit_trail=self.create_audit_trail(),
                    success=False,
                    error_message=error_msg,
                )
            ]


class BatchBacktestRunner:
    """Runner for executing multiple backtests in batch mode."""

    def __init__(self, configs: list[BacktestConfig]):
        """Initialize batch runner with list of configurations.

        Args:
            configs: List of backtest configurations
        """
        self.configs = configs
        self.results: list[BacktestResult] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def run_all(self) -> list[BacktestResult]:
        """Run all backtests in the batch.

        Returns:
            List of BacktestResult objects
        """
        self.logger.info(f"Starting batch execution of {len(self.configs)} backtests")

        for i, config in enumerate(self.configs, 1):
            self.logger.info(f"Running backtest {i}/{len(self.configs)}")

            runner = BacktestRunner(config)
            result = runner.run()
            self.results.append(result)

            if result.success:
                self.logger.info(f"Backtest {i} completed successfully")
            else:
                self.logger.error(f"Backtest {i} failed: {result.error_message}")

        # Summary statistics
        successful = sum(1 for r in self.results if r.success)
        self.logger.info(
            f"Batch execution completed: {successful}/{len(self.results)} successful"
        )

        return self.results

    def get_summary_stats(self) -> dict[str, Any]:
        """Get summary statistics across all batch results.

        Returns:
            Dictionary with batch summary statistics
        """
        if not self.results:
            return {}

        successful_results = [r for r in self.results if r.success]

        if not successful_results:
            return {"all_failed": True, "total_backtests": len(self.results)}

        total_execution_time = sum(r.execution_time_seconds for r in successful_results)

        return {
            "total_backtests": len(self.results),
            "successful_backtests": len(successful_results),
            "success_rate": len(successful_results) / len(self.results),
            "total_execution_time_seconds": total_execution_time,
            "average_execution_time_seconds": total_execution_time
            / len(successful_results),
        }
