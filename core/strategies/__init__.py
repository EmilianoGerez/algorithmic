"""
Core Strategies Package

Contains trading strategy implementations and the strategy framework.
."""

from .base_strategy import (
    BaseStrategy,
    StrategyRegistry,
    register_strategy,
    strategy_registry,
)
from .fvg_strategy import (
    FVGStrategy,
    create_fvg_scalp_config,
    create_fvg_strategy_config,
    create_fvg_swing_config,
)

__all__ = [
    "BaseStrategy",
    "StrategyRegistry",
    "strategy_registry",
    "register_strategy",
    "FVGStrategy",
    "create_fvg_strategy_config",
    "create_fvg_swing_config",
    "create_fvg_scalp_config",
]
