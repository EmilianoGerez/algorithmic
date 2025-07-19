"""
Data Adapters

Platform-specific adapters to convert external data into our universal models.
These adapters handle the integration with different data sources and platforms.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
import logging

from .models import Candle, MarketData, TimeFrame


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

    @abstractmethod
    def get_latest_candle(self, symbol: str, timeframe: TimeFrame) -> Optional[Candle]:
        """Get the latest candle for a symbol"""

    @abstractmethod
    def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol is available"""


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

    def get_latest_candle(self, symbol: str, timeframe: TimeFrame) -> Optional[Candle]:
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
                # pylint: disable=import-outside-toplevel
                from alpaca_trade_api import REST
                # pylint: disable=import-outside-toplevel
                from alpaca_trade_api.common import URL

                self._client = REST(
                    self.api_key, self.secret_key, base_url=URL(self.base_url)
                )
            except ImportError as exc:
                raise ImportError(
                    "alpaca-trade-api package required for AlpacaAdapter. "
                    "Install with: pip install alpaca-trade-api"
                ) from exc
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
                candle = self._convert_alpaca_bar(row, symbol, timeframe, timestamp)
                market_data.add_candle(candle)

            market_data.metadata["bars_fetched"] = len(bars)

        except Exception as exc:  # pylint: disable=broad-exception-caught
            market_data.metadata["error"] = str(exc)
            print(f"Error fetching Alpaca data: {exc}")

        return market_data

    def get_latest_candle(self, symbol: str, timeframe: TimeFrame) -> Optional[Candle]:
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

            return market_data.get_latest_candle() if market_data.candles else None

        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Error getting latest candle: {exc}")
            return None

    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol with Alpaca"""
        try:
            client = self._get_client()
            assets = client.list_assets(status="active", asset_class="us_equity")

            # Check if symbol exists in active assets
            for asset in assets:
                if asset.symbol == symbol and asset.tradable:
                    return True

            return False

        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Error validating symbol {symbol}: {exc}")
            return False

    def _convert_alpaca_bar(
        self, price_bar, symbol: str, timeframe: TimeFrame, timestamp
    ) -> Candle:
        """Convert Alpaca bar to our Candle model"""
        return Candle(
            timestamp=(
                timestamp.to_pydatetime()
                if hasattr(timestamp, "to_pydatetime")
                else timestamp
            ),
            open=Decimal(str(price_bar["open"])),
            high=Decimal(str(price_bar["high"])),
            low=Decimal(str(price_bar["low"])),
            close=Decimal(str(price_bar["close"])),
            volume=Decimal(str(price_bar["volume"])),
            symbol=symbol,
            timeframe=timeframe,
        )


class YahooFinanceAdapter(DataAdapter):
    """Adapter for Yahoo Finance data"""

    def __init__(self):
        self._yfinance = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_yfinance(self):
        """Get or import yfinance"""
        if self._yfinance is None:
            try:
                import yfinance as yf  # pylint: disable=import-outside-toplevel

                self._yfinance = yf
            except ImportError as exc:
                raise ImportError(
                    "yfinance package required for YahooFinanceAdapter"
                ) from exc
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
        yahoo_finance = self._get_yfinance()

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
            ticker = yahoo_finance.Ticker(symbol)
            data_frame = ticker.history(
                start=start_date, end=end_date, interval=interval
            )

            # Convert to our candle format
            for timestamp, row in data_frame.iterrows():
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

        except (ValueError, KeyError, ImportError) as exc:
            market_data.metadata["error"] = str(exc)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Catch any other unexpected errors
            market_data.metadata["error"] = str(exc)

        return market_data

    def get_latest_candle(self, symbol: str, timeframe: TimeFrame) -> Optional[Candle]:
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

        except (ValueError, KeyError, AttributeError) as exc:
            self.logger.warning(f"Error getting latest candle for {symbol}: {exc}")
            return None
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.logger.error(
                f"Unexpected error getting latest candle for {symbol}: {exc}"
            )
            return None

    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol with Yahoo Finance"""
        try:
            yahoo_finance = self._get_yfinance()
            ticker = yahoo_finance.Ticker(symbol)
            info = ticker.info
            return bool(info and "symbol" in info)
        except (ValueError, KeyError, AttributeError) as exc:
            self.logger.warning(f"Error validating symbol {symbol}: {exc}")
            return False
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.logger.error(f"Unexpected error validating symbol {symbol}: {exc}")
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
    def get_available_adapters(cls) -> list[str]:
        """Get list of available adapter types"""
        return list(cls._adapters.keys())
