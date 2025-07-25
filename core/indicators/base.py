from __future__ import annotations

from typing import Protocol

from core.entities import Candle


class Indicator(Protocol):
    def update(self, candle: Candle) -> None: ...
    @property
    def value(self) -> float | None: ...
