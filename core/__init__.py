"""
Core Package Initialization

The core package contains the fundamental components of the trading system:
- Data models and structures
- Strategy interfaces and implementations
- Technical indicators
- Signal processing
- Data integration and feeds
- Risk management
- Backtesting engine
- Live trading system
- Real-time data streaming
"""

from .data.models import *
from .data.adapters import DataAdapter, DataAdapterFactory
from .data.feeds import DataFeed, LiveDataFeed, BacktestDataFeed, MultiSymbolDataFeed
from .strategies.base_strategy import BaseStrategy, StrategyRegistry, strategy_registry
from .strategies.fvg_strategy import FVGStrategy, create_fvg_strategy_config
from .indicators.fvg_detector import FVGDetector, FVGFilterPresets
from .indicators.technical import TechnicalIndicators, EMASystem
from .signals.signal_processor import SignalProcessor, MultiTimeframeEngine
from .risk import RiskManager, RiskLimits, PositionSizer, FixedRiskPositionSizer, PortfolioMetrics
from .backtesting import BacktestEngine, CoreBacktestEngine, BacktestConfig, BacktestRunner
from .live import LiveTradingEngine, PaperBrokerAdapter, LiveTradingConfig, ExecutionMode
from .streaming import StreamingManager, StreamingFactory, StreamingConfig, StreamingProvider

__version__ = "3.0.0"
__author__ = "Algorithmic Trading System"

__all__ = [
    # Data models
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
    
    # Data integration
    "DataAdapter",
    "DataAdapterFactory",
    "DataFeed",
    "LiveDataFeed",
    "BacktestDataFeed",
    "MultiSymbolDataFeed",
    
    # Strategy system
    "BaseStrategy",
    "StrategyRegistry",
    "strategy_registry",
    "FVGStrategy",
    "create_fvg_strategy_config",
    
    # Indicators
    "FVGDetector",
    "FVGFilterPresets",
    "TechnicalIndicators",
    "EMASystem",
    
    # Signal processing
    "SignalProcessor",
    "MultiTimeframeEngine",
    
    # Risk management
    "RiskManager",
    "RiskLimits",
    "PositionSizer",
    "FixedRiskPositionSizer",
    "PortfolioMetrics",
    
    # Backtesting
    "BacktestEngine",
    "CoreBacktestEngine",
    "BacktestConfig",
    "BacktestRunner",
    
    # Live trading
    "LiveTradingEngine",
    "PaperBrokerAdapter",
    "LiveTradingConfig",
    "ExecutionMode",
    
    # Streaming
    "StreamingManager",
    "StreamingFactory",
    "StreamingConfig",
    "StreamingProvider"
]
