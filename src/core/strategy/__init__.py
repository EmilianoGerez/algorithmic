"""
Strategy module initialization
"""

from .composable_strategy import (
    ComposableStrategy,
    LiquidityPoolEvent,
    MarketContext,
    TechnicalSignal,
    EntrySignal,
    LiquidityPoolType,
    TrendDirection,
    SignalStrength
)

from .ema_crossover_in_pool_strategy import (
    EMACrossoverInPoolStrategy,
    create_default_strategy,
    create_scalping_strategy,
    create_swing_strategy
)

__all__ = [
    "ComposableStrategy",
    "LiquidityPoolEvent",
    "MarketContext", 
    "TechnicalSignal",
    "EntrySignal",
    "LiquidityPoolType",
    "TrendDirection",
    "SignalStrength",
    "EMACrossoverInPoolStrategy",
    "create_default_strategy",
    "create_scalping_strategy",
    "create_swing_strategy"
]
