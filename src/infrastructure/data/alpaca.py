import os
import requests
from typing import List, Optional
from src.db.models.candle import Candle

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = "https://data.alpaca.markets/v1beta3/crypto/us"

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}


class AlpacaCryptoRepository:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def _convert_timeframe(self, timeframe: str) -> str:
        """
        Convert pandas-style timeframes to Alpaca API format
        
        Examples:
        - "1T" -> "1Min"
        - "5T" -> "5Min"
        - "15T" -> "15Min"
        - "1H" -> "1H"
        - "4H" -> "4H"
        - "1D" -> "1D"
        """
        timeframe_map = {
            "1T": "1Min",
            "5T": "5Min",
            "15T": "15Min",
            "30T": "30Min",
            "1H": "1H",
            "4H": "4H",
            "1D": "1D",
            "1W": "1W"
        }
        
        return timeframe_map.get(timeframe, timeframe)

    def get_bars(
        self,
        symbol: str,
        timeframe: str = "15Min",
        limit_per_page: int = 1000,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[Candle]:
        """
        Fetch bars from Alpaca, handling pagination.
        - symbol: 'BTC/USD'
        - timeframe: '1T', '5T', '15T', '1H', '4H', '1D' (pandas style)
        - start/end: ISO 8601 (e.g., '2024-01-01T00:00:00Z')
        """
        all_bars: List[Candle] = []

        url = f"{BASE_URL}/bars"
        page_token = None
        
        # Convert timeframe to Alpaca API format
        api_timeframe = self._convert_timeframe(timeframe)

        while True:
            params = {
                "symbols": symbol,  # Use symbol as-is, e.g. 'BTC/USD'
                "timeframe": api_timeframe,  # Use converted timeframe
                "limit": limit_per_page,
            }
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            if page_token:
                params["page_token"] = page_token

            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            bars_raw = data["bars"].get(symbol, [])
            all_bars.extend([self._map_to_candle(bar) for bar in bars_raw])

            page_token = data.get("next_page_token")
            if not page_token:
                break

        return all_bars

    def _map_to_candle(self, bar: dict) -> Candle:
        return Candle(
            timestamp=bar["t"],
            open=bar["o"],
            high=bar["h"],
            low=bar["l"],
            close=bar["c"],
            volume=bar["v"],
        )
