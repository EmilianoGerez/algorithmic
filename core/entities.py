from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Literal

__all__ = ["Candle", "Event"]

@dataclass(frozen=True, slots=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Event(Protocol):
    ts: datetime
