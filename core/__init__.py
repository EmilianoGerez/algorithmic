"""
Core Package Initialization.

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
."""

from .backtesting import (
    BacktestConfig,
    BacktestEngine,
    BacktestRunner,
    CoreBacktestEngine,
)
from .data.adapters import DataAdapter, DataAdapterFactory
from .data.feeds import (
    BacktestDataFeed,
    DataFeed,
    LiveDataFeed,
    MultiSymbolDataFeed,
)
from .data.models import (
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
from .indicators.fvg_detector import FVGDetector, FVGFilterPresets
from .indicators.technical import EMASystem, TechnicalIndicators
from .live import (
    ExecutionMode,
    LiveTradingConfig,
    LiveTradingEngine,
    PaperBrokerAdapter,
)
from .risk import (
    FixedRiskPositionSizer,
    PortfolioMetrics,
    PositionSizer,
    RiskLimits,
    RiskManager,
)
from .signals.signal_processor import MultiTimeframeEngine, SignalProcessor
from .strategies.base_strategy import (
    BaseStrategy,
    StrategyRegistry,
    strategy_registry,
)
from .strategies.fvg_strategy import FVGStrategy, create_fvg_strategy_config
from .streaming import (
    StreamingConfig,
    StreamingFactory,
    StreamingManager,
    StreamingProvider,
)

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
    "StreamingProvider",
]
