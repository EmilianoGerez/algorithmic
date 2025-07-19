"""
Base Strategy Interface

Abstract base class for all trading strategies.
Defines the contract that all strategies must implement.
."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from ..data.models import MarketData, Position, Signal, StrategyConfig, TimeFrame


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    All strategies must implement this interface to be compatible
    with the trading system.
    ."""

    def __init__(self, config: StrategyConfig):
        """
        Initialize the strategy with configuration.

        Args:
            config: Strategy configuration containing parameters
        ."""
        self.config = config
        self.name = config.name
        self.symbol = config.symbol
        self.timeframes = config.timeframes
        self.active_positions: list[Position] = []
        self.signal_callback: Optional[
            Callable[[Signal], None]
        ] = None  # For backtesting
        self.is_initialized = False

        # Performance tracking
        self.signals_generated = 0
        self.positions_taken = 0
        self.total_pnl = 0.0

        # Strategy-specific data
        self.strategy_data: dict[str, Any] = {}
        self.metadata: dict[str, Any] = {}

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the strategy.
        Called once before the strategy starts processing data.
        ."""

    @abstractmethod
    def generate_signals(
        self, market_data: dict[TimeFrame, MarketData]
    ) -> list[Signal]:
        """
        Generate trading signals based on market data.

        Args:
            market_data: Dictionary mapping timeframes to market data

        Returns:
            List of generated signals
        ."""

    @abstractmethod
    def validate_signal(self, signal: Signal) -> bool:
        """
        Validate a trading signal.

        Args:
            signal: Signal to validate

        Returns:
            True if signal is valid, False otherwise
        ."""

    @abstractmethod
    def get_required_timeframes(self) -> list[TimeFrame]:
        """
        Get the timeframes required by this strategy.

        Returns:
            List of required timeframes
        ."""

    @abstractmethod
    def get_required_history_length(self) -> int:
        """
        Get the minimum number of candles required for the strategy.

        Returns:
            Minimum number of candles needed
        ."""

    def on_signal_generated(self, signal: Signal) -> None:
        """
        Called when a signal is generated.
        Override to add custom logic.

        Args:
            signal: Generated signal
        ."""

    def on_position_opened(self, position: Position) -> None:
        """
        Called when a position is opened.
        Override to add custom logic.

        Args:
            position: Opened position
        ."""

    def on_position_closed(self, position: Position) -> None:
        """
        Called when a position is closed.
        Override to add custom logic.

        Args:
            position: Closed position
        ."""

    def update_parameters(self, parameters: dict[str, Any]) -> None:
        """
        Update strategy parameters.

        Args:
            parameters: New parameters
        ."""
        self.config.parameters.update(parameters)

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """
        Get a strategy parameter.

        Args:
            key: Parameter key
            default: Default value if key not found

        Returns:
            Parameter value
        ."""
        return self.config.parameters.get(key, default)

    def get_strategy_info(self) -> dict[str, Any]:
        """
        Get strategy information.

        Returns:
            Dictionary containing strategy information
        ."""
        return {
            "name": self.name,
            "symbol": self.symbol,
            "timeframes": [tf.value for tf in self.timeframes],
            "risk_per_trade": self.config.risk_per_trade,
            "risk_reward_ratio": self.config.risk_reward_ratio,
            "max_positions": self.config.max_positions,
            "confidence_threshold": self.config.confidence_threshold,
            "parameters": self.config.parameters,
            "is_initialized": self.is_initialized,
            "metadata": self.metadata,
        }

    def set_signal_callback(self, callback: Callable[[Signal], None]) -> None:
        """
        Set callback function for signal generation.
        Used by backtesting engine to receive signals.

        Args:
            callback: Function to call when signal is generated
        ."""
        self.signal_callback = callback

    def emit_signal(self, signal: Signal) -> None:
        """
        Emit a signal to the callback if set.

        Args:
            signal: Signal to emit
        ."""
        if self.signal_callback:
            self.signal_callback(signal)

    def reset(self) -> None:
        """
        Reset the strategy state.
        Called when restarting or reinitializing the strategy.
        ."""
        self.is_initialized = False
        self.metadata.clear()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, symbol={self.symbol})"

    def __repr__(self) -> str:
        return self.__str__()


class StrategyRegistry:
    """
    Registry for managing trading strategies.

    Provides a centralized way to register, retrieve, and manage
    trading strategies.
    ."""

    def __init__(self) -> None:
        self._strategies: dict[str, type] = {}
        self._instances: dict[str, BaseStrategy] = {}

    def register(self, strategy_class: type) -> None:
        """
        Register a strategy class.

        Args:
            strategy_class: Strategy class to register
        ."""
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError("Strategy class must inherit from BaseStrategy")

        strategy_name = strategy_class.__name__
        if strategy_name in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' is already registered")

        self._strategies[strategy_name] = strategy_class

    def create_strategy(
        self, strategy_name: str, config: StrategyConfig
    ) -> BaseStrategy:
        """
        Create a strategy instance.

        Args:
            strategy_name: Name of the strategy class
            config: Strategy configuration

        Returns:
            Strategy instance
        ."""
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' is not registered")

        strategy_class = self._strategies[strategy_name]
        instance = strategy_class(config)

        # Store instance for later retrieval
        instance_key = f"{strategy_name}_{config.symbol}_{id(instance)}"
        self._instances[instance_key] = instance

        return instance

    def get_strategy(self, instance_key: str) -> Optional[BaseStrategy]:
        """
        Get a strategy instance by key.

        Args:
            instance_key: Instance key

        Returns:
            Strategy instance or None
        ."""
        return self._instances.get(instance_key)

    def list_strategies(self) -> list[str]:
        """
        List all registered strategy names.

        Returns:
            List of strategy names
        ."""
        return list(self._strategies.keys())

    def list_instances(self) -> list[str]:
        """
        List all strategy instance keys.

        Returns:
            List of instance keys
        ."""
        return list(self._instances.keys())

    def remove_strategy(self, strategy_name: str) -> None:
        """
        Remove a strategy from the registry.

        Args:
            strategy_name: Name of the strategy to remove
        ."""
        if strategy_name in self._strategies:
            del self._strategies[strategy_name]

        # Remove all instances of this strategy
        keys_to_remove = [
            key for key in self._instances.keys() if key.startswith(f"{strategy_name}_")
        ]
        for key in keys_to_remove:
            del self._instances[key]

    def clear(self) -> None:
        """Clear all strategies and instances."""
        self._strategies.clear()
        self._instances.clear()


# Global strategy registry instance
strategy_registry = StrategyRegistry()


def register_strategy(strategy_class: type) -> type:
    """
    Decorator to register a strategy class.

    Args:
        strategy_class: Strategy class to register

    Returns:
        The same strategy class
    """
    strategy_registry.register(strategy_class)
    return strategy_class
