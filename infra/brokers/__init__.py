"""
Broker implementations for backtesting and live trading.

This package provides both paper trading (simulation) and live broker
implementations for connecting to real exchanges and brokers.
"""

from .alpaca import AlpacaBroker, AlpacaConfig
from .base_live import HttpLiveBroker, LiveBrokerConfig
from .binance_futures import BinanceConfig, BinanceFuturesBroker
from .broker import PaperBroker
from .exceptions import BrokerError

__all__ = [
    "BrokerError",
    "PaperBroker",
    "HttpLiveBroker",
    "LiveBrokerConfig",
    "BinanceFuturesBroker",
    "BinanceConfig",
    "AlpacaBroker",
    "AlpacaConfig",
]
