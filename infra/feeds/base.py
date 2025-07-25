from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from core.entities import Candle


class DataFeed(Protocol):
    async def stream(self) -> AsyncIterator[Candle]: ...
