"""Incremental FVG detector — skeleton implementation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.entities import Candle


@dataclass(frozen=True)
class FVGEvent:
    ts: datetime
    top: float
    bottom: float
    tf: str

class FVGDetector:
    def __init__(self, tf: str):
        self.tf = tf
        self._buffer: list[Candle] = []

    def update(self, candle: Candle) -> list[FVGEvent]:
        """Return events detected on CLOSED candles only."""
        self._buffer.append(candle)
        if len(self._buffer) < 3:
            return []
        prev, curr, nxt = self._buffer[-3], self._buffer[-2], self._buffer[-1]
        events = []
        if prev.high < nxt.low:      # bullish gap
            events.append(FVGEvent(ts=nxt.ts, top=nxt.low, bottom=prev.high, tf=self.tf))
        if prev.low > nxt.high:      # bearish gap
            events.append(FVGEvent(ts=nxt.ts, top=prev.low, bottom=nxt.high, tf=self.tf))
        # keep buffer size 3
        if len(self._buffer) > 3:
            self._buffer = self._buffer[-3:]
        return events
