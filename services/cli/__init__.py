"""
Quantitative Algorithm Platform CLI

This module provides the command-line interface for the backtesting engine,
including single backtests, walk-forward analysis, and parameter optimization.
"""

from .cli import app

__all__ = ["app"]
