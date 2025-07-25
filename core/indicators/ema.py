from __future__ import annotations

from dataclasses import dataclass

from core.entities import Candle


@dataclass
class EMA:
    period: int
    _mult: float | None = None
    _value: float | None = None

    def __post_init__(self) -> None:
        self._mult = 2 / (self.period + 1)

    def update(self, candle: Candle) -> None:
        if self._value is None:
            self._value = candle.close
        else:
            assert self._mult is not None  # mypy hint: _mult is set in __post_init__
            self._value = (candle.close - self._value) * self._mult + self._value

    @property
    def value(self) -> float | None:
        return self._value
