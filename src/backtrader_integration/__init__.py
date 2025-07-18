"""
Backtrader Integration Module
Professional integration of Backtrader with existing FVG trading system
"""

from .main import FVGBacktraderIntegration
from .engine import BacktraderEngine, run_fvg_backtest
from .strategy import FVGTradingStrategy
from .data_feeds import FVGDataFeed, BacktraderDataManager
from .indicators import (
    FVGIndicator,
    EMATrendFilter,
    NYTradingHours,
    SwingPointDetector,
    EntrySignalDetector,
    RiskManager
)
from .analyzers import (
    FVGAnalyzer,
    TradingSessionAnalyzer,
    RiskMetricsAnalyzer,
    PerformanceBreakdownAnalyzer,
    ConsistencyAnalyzer
)

__all__ = [
    'FVGBacktraderIntegration',
    'BacktraderEngine',
    'run_fvg_backtest',
    'FVGTradingStrategy',
    'FVGDataFeed',
    'BacktraderDataManager',
    'FVGIndicator',
    'EMATrendFilter',
    'NYTradingHours',
    'SwingPointDetector',
    'EntrySignalDetector',
    'RiskManager',
    'FVGAnalyzer',
    'TradingSessionAnalyzer',
    'RiskMetricsAnalyzer',
    'PerformanceBreakdownAnalyzer',
    'ConsistencyAnalyzer'
]
