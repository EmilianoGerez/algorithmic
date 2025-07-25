from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from core.entities import Candle

@dataclass
class EMA:
    period: int
    _mult: float = None
    _value: Optional[float] = None

    def __post_init__(self):
        self._mult = 2 / (self.period + 1)

    def update(self, candle: Candle) -> None:
        if self._value is None:
            self._value = candle.close
        else:
            self._value = (candle.close - self._value) * self._mult + self._value

    @property
    def value(self) -> Optional[float]:
        return self._value
