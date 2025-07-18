"""
Core Signals Package

Contains signal processing and generation components.
"""

from .signal_processor import (
    MultiTimeframeEngine,
    SignalContext,
    SignalProcessor,
    SignalQuality,
)

__all__ = [
    "SignalProcessor",
    "MultiTimeframeEngine",
    "SignalContext",
    "SignalQuality",
]
