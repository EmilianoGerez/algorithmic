"""
Core Data Module

Contains all data structures, adapters, and feeds used throughout the trading system.
."""

from .adapters import (
    AlpacaAdapter,
    BacktraderAdapter,
    DataAdapter,
    DataAdapterFactory,
    YahooFinanceAdapter,
)
from .feeds import (
    BacktestDataFeed,
    DataFeed,
    LiveDataFeed,
    MultiSymbolDataFeed,
)
from .models import (
    BacktestResult,
    Candle,
    FVGZone,
    MarketData,
    Order,
    OrderStatus,
    Position,
    Signal,
    SignalDirection,
    SignalType,
    StrategyConfig,
    TimeFrame,
)

__all__ = [
    # Models
    "Candle",
    "MarketData",
    "Signal",
    "Position",
    "Order",
    "FVGZone",
    "StrategyConfig",
    "BacktestResult",
    "TimeFrame",
    "SignalDirection",
    "SignalType",
    "OrderStatus",
    # Adapters
    "DataAdapter",
    "BacktraderAdapter",
    "AlpacaAdapter",
    "YahooFinanceAdapter",
    "DataAdapterFactory",
    # Feeds
    "DataFeed",
    "LiveDataFeed",
    "BacktestDataFeed",
    "MultiSymbolDataFeed",
]
