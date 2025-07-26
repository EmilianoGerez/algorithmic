"""
Paper trading broker implementation for backtesting and simulation.

This package provides a paper trading broker that simulates real trading
without actual market execution. It maintains positions, calculates PnL,
and provides the same interface as live brokers.
"""

from .broker import PaperBroker
from .exceptions import BrokerError

__all__ = [
    "BrokerError",
    "PaperBroker",
]
