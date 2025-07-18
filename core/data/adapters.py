"""
Data Adapters

Platform-specific adapters to convert external data into our universal models.
These adapters handle the integration with different data sources and platforms.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .models import Candle, MarketData, SignalDirection, TimeFrame


class DataAdapter(ABC):
    """Abstract base class for data adapters"""

    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        limit: Optional[int] = None,
    ) -> MarketData:
        """Get historical market data"""
        pass

    @abstractmethod
    def get_latest_candle(
        self, symbol: str, timeframe: TimeFrame
    ) -> Optional[Candle]:
        """Get the latest candle for a symbol"""
        pass

    @abstractmethod
    def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol is available"""
        pass


class BacktraderAdapter(DataAdapter):
    """Adapter for Backtrader platform"""

    def __init__(self, cerebro_instance=None):
        self.cerebro = cerebro_instance
        self._data_cache = {}

    def get_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        limit: Optional[int] = None,
    ) -> MarketData:
        """Convert Backtrader data to our universal format"""
        # This would integrate with existing backtrader data feeds
        # For now, we'll create a structure that can be populated
        market_data = MarketData(
            symbol=symbol,
            timeframe=timeframe,
            metadata={
                "source": "backtrader",
                "start_date": start_date,
                "end_date": end_date,
                "adapter": "BacktraderAdapter",
            },
        )

        # TODO: Implement actual backtrader data conversion
        # This would pull from self.cerebro.datas or similar

        return market_data

    def get_latest_candle(
        self, symbol: str, timeframe: TimeFrame
    ) -> Optional[Candle]:
        """Get latest candle from backtrader"""
        # TODO: Implement backtrader latest candle retrieval
        return None

    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol in backtrader context"""
        # TODO: Implement symbol validation
        return True

    def convert_backtrader_candle(self, bt_data, index: int) -> Candle:
        """Convert backtrader data point to our Candle model"""
        # TODO: Implement conversion from backtrader data format
        # This would handle bt_data.open[index], bt_data.high[index], etc.
        pass


class AlpacaAdapter(DataAdapter):
    """Adapter for Alpaca Markets API"""

    # Alpaca timeframe mapping
    TIMEFRAME_MAP = {
        TimeFrame.MINUTE_1: "1Min",
        TimeFrame.MINUTE_5: "5Min",
        TimeFrame.MINUTE_15: "15Min",
        TimeFrame.MINUTE_30: "30Min",
        TimeFrame.HOUR_1: "1Hour",
        TimeFrame.DAY_1: "1Day",
    }

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str = "https://paper-api.alpaca.markets",
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self._client = None
        self._data_cache = {}

    def _get_client(self):
        """Get or create Alpaca client"""
        if self._client is None:
            try:
                from alpaca_trade_api import REST
                from alpaca_trade_api.common import URL

                self._client = REST(
                    self.api_key, self.secret_key, base_url=URL(self.base_url)
                )
            except ImportError:
                raise ImportError(
                    "alpaca-trade-api package required for AlpacaAdapter. "
                    "Install with: pip install alpaca-trade-api"
                )
        return self._client

    def get_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        limit: Optional[int] = None,
    ) -> MarketData:
        """Get historical data from Alpaca"""
        market_data = MarketData(
            symbol=symbol,
            timeframe=timeframe,
            metadata={
                "source": "alpaca",
                "start_date": start_date,
                "end_date": end_date,
                "adapter": "AlpacaAdapter",
            },
        )

        try:
            client = self._get_client()
            alpaca_timeframe = self.TIMEFRAME_MAP.get(timeframe)

            if not alpaca_timeframe:
                raise ValueError(f"Unsupported timeframe: {timeframe}")

            # Get bars from Alpaca
            bars = client.get_bars(
                symbol=symbol,
                timeframe=alpaca_timeframe,
                start=start_date.isoformat(),
                end=end_date.isoformat(),
                limit=limit,
                adjustment="raw",  # Use raw prices for backtesting
            ).df

            # Convert to our candle format
            for timestamp, row in bars.iterrows():
                candle = self._convert_alpaca_bar(
                    row, symbol, timeframe, timestamp
                )
                market_data.add_candle(candle)

            market_data.metadata["bars_fetched"] = len(bars)

        except Exception as e:
            market_data.metadata["error"] = str(e)
            print(f"Error fetching Alpaca data: {e}")

        return market_data

    def get_latest_candle(
        self, symbol: str, timeframe: TimeFrame
    ) -> Optional[Candle]:
        """Get latest candle from Alpaca"""
        try:
            # Get last trading day data
            end_date = datetime.now()
            start_date = end_date - timedelta(
                days=2
            )  # Get 2 days to ensure we have data

            market_data = self.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                limit=1,
            )

            return (
                market_data.get_latest_candle()
                if market_data.candles
                else None
            )

        except Exception as e:
            print(f"Error getting latest candle: {e}")
            return None

    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol with Alpaca"""
        try:
            client = self._get_client()
            assets = client.list_assets(
                status="active", asset_class="us_equity"
            )

            # Check if symbol exists in active assets
            for asset in assets:
                if asset.symbol == symbol and asset.tradable:
                    return True

            return False

        except Exception as e:
            print(f"Error validating symbol {symbol}: {e}")
            return False

    def _convert_alpaca_bar(
        self, bar, symbol: str, timeframe: TimeFrame, timestamp
    ) -> Candle:
        """Convert Alpaca bar to our Candle model"""
        return Candle(
            timestamp=(
                timestamp.to_pydatetime()
                if hasattr(timestamp, "to_pydatetime")
                else timestamp
            ),
            open=Decimal(str(bar["open"])),
            high=Decimal(str(bar["high"])),
            low=Decimal(str(bar["low"])),
            close=Decimal(str(bar["close"])),
            volume=Decimal(str(bar["volume"])),
            symbol=symbol,
            timeframe=timeframe,
        )


class YahooFinanceAdapter(DataAdapter):
    """Adapter for Yahoo Finance data"""

    def __init__(self):
        self._yfinance = None

    def _get_yfinance(self):
        """Get or import yfinance"""
        if self._yfinance is None:
            try:
                import yfinance as yf

                self._yfinance = yf
            except ImportError:
                raise ImportError(
                    "yfinance package required for YahooFinanceAdapter"
                )
        return self._yfinance

    def get_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        limit: Optional[int] = None,
    ) -> MarketData:
        """Get historical data from Yahoo Finance"""
        yf = self._get_yfinance()

        # Convert our timeframe to Yahoo Finance interval
        interval_map = {
            TimeFrame.MINUTE_1: "1m",
            TimeFrame.MINUTE_5: "5m",
            TimeFrame.MINUTE_15: "15m",
            TimeFrame.MINUTE_30: "30m",
            TimeFrame.HOUR_1: "1h",
            TimeFrame.DAY_1: "1d",
            TimeFrame.WEEK_1: "1wk",
            TimeFrame.MONTH_1: "1mo",
        }

        interval = interval_map.get(timeframe, "1d")

        market_data = MarketData(
            symbol=symbol,
            timeframe=timeframe,
            metadata={
                "source": "yahoo_finance",
                "start_date": start_date,
                "end_date": end_date,
                "adapter": "YahooFinanceAdapter",
                "interval": interval,
            },
        )

        try:
            # Get data from Yahoo Finance
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date, end=end_date, interval=interval
            )

            # Convert to our candle format
            for timestamp, row in df.iterrows():
                candle = Candle(
                    timestamp=timestamp.to_pydatetime(),
                    open=Decimal(str(row["Open"])),
                    high=Decimal(str(row["High"])),
                    low=Decimal(str(row["Low"])),
                    close=Decimal(str(row["Close"])),
                    volume=Decimal(str(row["Volume"])),
                    symbol=symbol,
                    timeframe=timeframe,
                )
                market_data.add_candle(candle)

                if limit and len(market_data.candles) >= limit:
                    break

        except Exception as e:
            market_data.metadata["error"] = str(e)

        return market_data

    def get_latest_candle(
        self, symbol: str, timeframe: TimeFrame
    ) -> Optional[Candle]:
        """Get latest candle from Yahoo Finance"""
        try:
            # Get last 2 days of data to ensure we have latest complete candle
            end_date = datetime.now()
            start_date = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            market_data = self.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                limit=1,
            )

            return market_data.get_latest_candle()

        except Exception:
            return None

    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol with Yahoo Finance"""
        try:
            yf = self._get_yfinance()
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return bool(info and "symbol" in info)
        except Exception:
            return False


class DataAdapterFactory:
    """Factory for creating data adapters"""

    _adapters = {
        "backtrader": BacktraderAdapter,
        "alpaca": AlpacaAdapter,
        "yahoo": YahooFinanceAdapter,
    }

    @classmethod
    def create_adapter(cls, adapter_type: str, **kwargs) -> DataAdapter:
        """Create a data adapter instance"""
        if adapter_type not in cls._adapters:
            raise ValueError(f"Unknown adapter type: {adapter_type}")

        adapter_class = cls._adapters[adapter_type]
        return adapter_class(**kwargs)

    @classmethod
    def register_adapter(cls, name: str, adapter_class: type) -> None:
        """Register a new adapter type"""
        if not issubclass(adapter_class, DataAdapter):
            raise ValueError("Adapter must inherit from DataAdapter")
        cls._adapters[name] = adapter_class

    @classmethod
    def get_available_adapters(cls) -> List[str]:
        """Get list of available adapter types"""
        return list(cls._adapters.keys())
