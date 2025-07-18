"""
Core Data Module

Contains all data structures, adapters, and feeds used throughout the trading system.
"""

from .models import *
from .adapters import (
    DataAdapter,
    BacktraderAdapter,
    AlpacaAdapter,
    YahooFinanceAdapter,
    DataAdapterFactory
)
from .feeds import (
    DataFeed,
    LiveDataFeed,
    BacktestDataFeed,
    MultiSymbolDataFeed
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
    "IndicatorResult",
    
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
    "MultiSymbolDataFeed"
]
