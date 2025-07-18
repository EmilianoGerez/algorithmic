"""
Backtesting Platform Integration

Integrates the core system with different backtesting platforms
and provides unified backtesting capabilities.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from ..data.adapters import DataAdapter
from ..data.feeds import BacktestDataFeed
from ..data.models import (
    BacktestResult,
    Candle,
    MarketData,
    Position,
    Signal,
    SignalDirection,
    StrategyConfig,
    TimeFrame,
)
from ..risk import FixedRiskPositionSizer, RiskLimits, RiskManager
from ..strategies.base_strategy import BaseStrategy


@dataclass
class BacktestConfig:
    """Backtesting configuration"""

    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    commission: Decimal = Decimal("0.001")  # 0.1% commission
    slippage: Decimal = Decimal("0.001")  # 0.1% slippage
    risk_limits: Optional[RiskLimits] = None
    benchmark_symbol: str = "SPY"

    def __post_init__(self):
        if self.risk_limits is None:
            self.risk_limits = RiskLimits()


class BacktestEngine(ABC):
    """Abstract base class for backtesting engines"""

    @abstractmethod
    def run_backtest(
        self,
        strategy: BaseStrategy,
        market_data: MarketData,
        config: BacktestConfig,
    ) -> BacktestResult:
        """Run a backtest"""
        pass


class CoreBacktestEngine(BacktestEngine):
    """Core backtesting engine using our unified system"""

    def __init__(self, data_adapter: DataAdapter):
        self.data_adapter = data_adapter
        self.reset()

    def reset(self):
        """Reset engine state"""
        self.signals: List[Signal] = []
        self.positions: List[Position] = []
        self.trades: List[Dict] = []
        self.current_time: Optional[datetime] = None
        self.current_prices: Dict[str, Decimal] = {}
        self.performance_metrics = {
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
        }

    def run_backtest(
        self,
        strategy: BaseStrategy,
        market_data: MarketData,
        config: BacktestConfig,
    ) -> BacktestResult:
        """Run a comprehensive backtest"""
        self.reset()

        # Initialize risk manager
        position_sizer = FixedRiskPositionSizer(
            risk_per_trade=float(config.risk_limits.max_position_size)
            / 5  # Conservative sizing
        )
        risk_manager = RiskManager(
            risk_limits=config.risk_limits,
            position_sizer=position_sizer,
            initial_capital=config.initial_capital,
        )

        # Initialize strategy
        strategy_config = StrategyConfig(
            name=strategy.__class__.__name__,
            symbol=market_data.symbol,
            timeframes=[market_data.timeframe],
            confidence_threshold=0.85,
        )
        strategy.initialize()

        # Create data feed
        data_feed = BacktestDataFeed(self.data_adapter, market_data)
        data_feed.subscribe(self._on_candle)

        # Set up strategy to receive signals
        self.current_strategy = strategy  # Store strategy reference
        strategy.set_signal_callback(self._on_signal)

        # Run backtest
        data_feed.set_playback_speed(0)  # Instant playback
        data_feed.start()

        # Wait for completion
        while not data_feed.is_complete:
            pass

        # Process any remaining signals
        self._process_signals(risk_manager, config)

        # Close any remaining positions
        if self.current_time and self.current_prices:
            self._close_all_positions(risk_manager, config)

        # Generate results
        return self._generate_results(
            strategy.name, market_data.symbol, config, risk_manager
        )

    def _on_candle(self, candle: Candle) -> None:
        """Handle incoming candle data"""
        self.current_time = candle.timestamp
        self.current_prices[candle.symbol] = candle.close

        # Update any active positions
        # This would normally be done by the risk manager
        # but we'll simulate it here for the backtest

        # For this demo, we'll trigger strategy analysis on each candle
        # In a real implementation, this would be more sophisticated
        market_data = {
            candle.timeframe: MarketData(
                symbol=candle.symbol,
                timeframe=candle.timeframe,
                candles=[candle],
            )
        }

        # Let strategy analyze the current market state
        # This is a simplified approach for demonstration
        try:
            if hasattr(self, "current_strategy"):
                self.current_strategy.generate_signals(market_data)
        except Exception as e:
            pass  # Ignore errors for demo

    def _on_signal(self, signal: Signal) -> None:
        """Handle signals from strategy"""
        self.signals.append(signal)

    def _process_signals(
        self, risk_manager: RiskManager, config: BacktestConfig
    ) -> None:
        """Process accumulated signals"""
        for signal in self.signals:
            if signal.signal_type.value == "entry":
                # Evaluate signal with risk management
                assessment = risk_manager.evaluate_signal(signal)

                if assessment["approved"]:
                    # Apply commission and slippage
                    adjusted_price = self._apply_costs(
                        signal.entry_price, config, "entry"
                    )

                    # Create position
                    position = risk_manager.add_position(
                        signal, assessment["position_size"]
                    )
                    position.entry_price = adjusted_price
                    self.positions.append(position)

        # Clear processed signals
        self.signals.clear()

    def _apply_costs(
        self, price: Decimal, config: BacktestConfig, action: str
    ) -> Decimal:
        """Apply commission and slippage to price"""
        # Simple slippage model
        slippage_amount = price * config.slippage

        if action == "entry":
            # Pay slippage on entry
            return price + slippage_amount
        else:
            # Pay slippage on exit
            return price - slippage_amount

    def _close_all_positions(
        self, risk_manager: RiskManager, config: BacktestConfig
    ) -> None:
        """Close all remaining positions at market close"""
        for position in self.positions[
            :
        ]:  # Copy list to avoid modification during iteration
            if position.symbol in self.current_prices:
                exit_price = self._apply_costs(
                    self.current_prices[position.symbol], config, "exit"
                )
                risk_manager.close_position(position, exit_price, self.current_time)

    def _generate_results(
        self,
        strategy_name: str,
        symbol: str,
        config: BacktestConfig,
        risk_manager: RiskManager,
    ) -> BacktestResult:
        """Generate backtest results"""
        portfolio_summary = risk_manager.get_portfolio_summary()

        return BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_capital,
            final_capital=risk_manager.metrics.total_value,
            total_trades=risk_manager.metrics.total_trades,
            winning_trades=risk_manager.metrics.winning_trades,
            losing_trades=risk_manager.metrics.total_trades
            - risk_manager.metrics.winning_trades,
            win_rate=risk_manager.metrics.win_rate,
            total_pnl=risk_manager.metrics.realized_pnl,
            max_drawdown=risk_manager.metrics.max_drawdown,
            signals=self.signals,
            trades=risk_manager.positions,
            metadata={
                "commission": config.commission,
                "slippage": config.slippage,
                "risk_limits": config.risk_limits,
                "portfolio_summary": portfolio_summary,
            },
        )


class BacktraderIntegration(BacktestEngine):
    """Integration with Backtrader platform"""

    def __init__(self, cerebro_class=None):
        self.cerebro_class = cerebro_class
        self.cerebro = None

    def run_backtest(
        self,
        strategy: BaseStrategy,
        market_data: MarketData,
        config: BacktestConfig,
    ) -> BacktestResult:
        """Run backtest using Backtrader"""
        if self.cerebro_class is None:
            raise ImportError("Backtrader not available")

        # Create Backtrader cerebro instance
        cerebro = self.cerebro_class()

        # Set initial capital
        cerebro.broker.setcash(float(config.initial_capital))

        # Set commission
        cerebro.broker.setcommission(commission=float(config.commission))

        # Add data feed
        # This would need to convert our MarketData to Backtrader format
        # data_feed = self._convert_to_backtrader_feed(market_data)
        # cerebro.adddata(data_feed)

        # Add strategy
        # This would need to wrap our strategy in Backtrader format
        # cerebro.addstrategy(BacktraderStrategyWrapper, core_strategy=strategy)

        # Add analyzers
        # cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        # cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        # cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

        # Run backtest
        # results = cerebro.run()

        # Convert results back to our format
        # For now, return a placeholder
        return BacktestResult(
            strategy_name=strategy.name,
            symbol=market_data.symbol,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_capital,
            final_capital=config.initial_capital,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=Decimal("0"),
            max_drawdown=Decimal("0"),
            metadata={"platform": "backtrader"},
        )


class OptimizationEngine:
    """Parameter optimization engine"""

    def __init__(self, backtest_engine: BacktestEngine):
        self.backtest_engine = backtest_engine

    def optimize_parameters(
        self,
        strategy_class: type,
        market_data: MarketData,
        config: BacktestConfig,
        parameter_ranges: Dict[str, List[Any]],
        objective_function: str = "total_return",
    ) -> Dict[str, Any]:
        """Optimize strategy parameters"""
        best_params = {}
        best_score = float("-inf")
        best_result = None

        # Generate parameter combinations
        combinations = self._generate_parameter_combinations(parameter_ranges)

        results = []
        for params in combinations:
            try:
                # Create strategy with parameters
                strategy = strategy_class(**params)

                # Run backtest
                result = self.backtest_engine.run_backtest(
                    strategy, market_data, config
                )

                # Calculate objective score
                score = self._calculate_objective_score(result, objective_function)

                results.append({"parameters": params, "result": result, "score": score})

                # Track best result
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_result = result

            except Exception as e:
                print(f"Error optimizing parameters {params}: {e}")
                continue

        return {
            "best_parameters": best_params,
            "best_score": best_score,
            "best_result": best_result,
            "all_results": results,
        }

    def _generate_parameter_combinations(
        self, parameter_ranges: Dict[str, List[Any]]
    ) -> List[Dict]:
        """Generate all combinations of parameters"""
        import itertools

        keys = list(parameter_ranges.keys())
        values = list(parameter_ranges.values())

        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))

        return combinations

    def _calculate_objective_score(
        self, result: BacktestResult, objective: str
    ) -> float:
        """Calculate objective score for optimization"""
        if objective == "total_return":
            return result.calculate_return_percentage()
        elif objective == "sharpe_ratio":
            return result.sharpe_ratio or 0.0
        elif objective == "profit_factor":
            return result.profit_factor or 0.0
        elif objective == "win_rate":
            return result.win_rate
        elif objective == "risk_adjusted_return":
            return_pct = result.calculate_return_percentage()
            max_dd = float(result.max_drawdown) if result.max_drawdown else 0.01
            return return_pct / max_dd
        else:
            return 0.0


class BacktestRunner:
    """High-level backtesting runner"""

    def __init__(self, data_adapter: DataAdapter):
        self.data_adapter = data_adapter
        self.core_engine = CoreBacktestEngine(data_adapter)
        self.optimization_engine = OptimizationEngine(self.core_engine)

    def run_single_backtest(
        self,
        strategy: BaseStrategy,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        initial_capital: Decimal = Decimal("100000"),
    ) -> BacktestResult:
        """Run a single backtest"""
        # Get market data
        market_data = self.data_adapter.get_historical_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )

        # Create config
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
        )

        # Run backtest
        return self.core_engine.run_backtest(strategy, market_data, config)

    def run_multi_symbol_backtest(
        self,
        strategy: BaseStrategy,
        symbols: List[str],
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        initial_capital: Decimal = Decimal("100000"),
    ) -> List[BacktestResult]:
        """Run backtest across multiple symbols"""
        results = []

        for symbol in symbols:
            try:
                result = self.run_single_backtest(
                    strategy,
                    symbol,
                    timeframe,
                    start_date,
                    end_date,
                    initial_capital,
                )
                results.append(result)
            except Exception as e:
                print(f"Error backtesting {symbol}: {e}")
                continue

        return results

    def run_walk_forward_analysis(
        self,
        strategy_class: type,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        train_periods: int = 252,  # 1 year of daily data
        test_periods: int = 63,  # 3 months of daily data
        step_size: int = 21,  # 1 month step
    ) -> Dict[str, Any]:
        """Run walk-forward analysis"""
        # TODO: Implement walk-forward analysis
        # This would involve:
        # 1. Splitting data into train/test periods
        # 2. Optimizing parameters on train data
        # 3. Testing on out-of-sample data
        # 4. Rolling forward and repeating

        return {
            "strategy": strategy_class.__name__,
            "symbol": symbol,
            "periods": [],
            "overall_performance": None,
        }
