"""Indicator registry for dynamic discovery and instantiation."""

from __future__ import annotations

from typing import Any

from core.indicators.atr import ATR
from core.indicators.base import Indicator
from core.indicators.ema import EMA
from core.indicators.volume_sma import VolumeSMA

__all__ = ["IndicatorRegistry", "INDICATOR_REGISTRY"]


class IndicatorRegistry:
    """Registry for indicator discovery and dynamic instantiation.

    Allows indicators to be created from YAML configuration names,
    enabling flexible hyper-parameter sweeps and configuration-driven
    indicator selection.

    Example:
        >>> registry = IndicatorRegistry()
        >>> ema = registry.create("ema", period=21)
        >>> atr = registry.create("atr", period=14)
    """

    def __init__(self) -> None:
        self._registry: dict[str, type[Indicator]] = {}

    def register(self, name: str, indicator_class: type[Indicator]) -> None:
        """Register an indicator class with a given name.

        Args:
            name: String identifier for the indicator (e.g., "ema", "atr").
            indicator_class: The indicator class to register.
        """
        self._registry[name] = indicator_class

    def create(self, name: str, **kwargs: Any) -> Indicator | None:
        """Create an indicator instance by name.

        Args:
            name: Registered indicator name.
            **kwargs: Arguments to pass to the indicator constructor.

        Returns:
            New indicator instance or None if name not found.

        Raises:
            KeyError: If indicator name is not registered.
            TypeError: If invalid arguments are provided.
        """
        if name not in self._registry:
            raise KeyError(f"Indicator '{name}' not found in registry. "
                          f"Available: {list(self._registry.keys())}")

        indicator_class = self._registry[name]
        return indicator_class(**kwargs)

    def list_indicators(self) -> list[str]:
        """Get list of all registered indicator names.

        Returns:
            List of indicator names available for creation.
        """
        return list(self._registry.keys())

    def is_registered(self, name: str) -> bool:
        """Check if an indicator name is registered.

        Args:
            name: Indicator name to check.

        Returns:
            True if indicator is registered, False otherwise.
        """
        return name in self._registry


# Global registry instance
INDICATOR_REGISTRY = IndicatorRegistry()

# Register core indicators
INDICATOR_REGISTRY.register("ema", EMA)
INDICATOR_REGISTRY.register("atr", ATR)
INDICATOR_REGISTRY.register("volume_sma", VolumeSMA)
