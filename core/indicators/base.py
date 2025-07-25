from __future__ import annotations
from typing import Protocol, Optional
from core.entities import Candle

class Indicator(Protocol):
    def update(self, candle: Candle) -> None: ...
    @property
    def value(self) -> Optional[float]: ...
