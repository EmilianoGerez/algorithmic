from __future__ import annotations
from typing import AsyncIterator, Protocol
from core.entities import Candle

class DataFeed(Protocol):
    async def stream(self) -> AsyncIterator[Candle]: ...
