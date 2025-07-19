"""
Real-time Data Streaming

Integration with real-time data providers for live market data streaming.
Supports multiple data sources and provides unified streaming interface.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, Optional

import websockets

from ..data.models import Candle, TimeFrame


class StreamingProvider(Enum):
    """Supported streaming providers"""

    ALPACA = "alpaca"
    POLYGON = "polygon"
    YAHOO = "yahoo"
    BINANCE = "binance"
    MOCK = "mock"


@dataclass
class StreamingConfig:
    """Configuration for data streaming"""

    provider: StreamingProvider
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    base_url: Optional[str] = None
    symbols: list[str] = field(default_factory=list)
    timeframes: list[TimeFrame] = field(default_factory=lambda: [TimeFrame.MINUTE_1])
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 10
    reconnect_delay: float = 5.0
    heartbeat_interval: float = 30.0
    buffer_size: int = 1000


class StreamingDataProvider(ABC):
    """Abstract base class for streaming data providers"""

    def __init__(self, config: StreamingConfig):
        self.config = config
        self.is_connected = False
        self.subscribers: list[Callable[[Candle], None]] = []
        self.reconnect_attempts = 0
        self.last_heartbeat = datetime.now()

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to streaming provider"""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from streaming provider"""

    @abstractmethod
    async def subscribe_symbols(self, symbols: list[str]) -> None:
        """Subscribe to symbols"""

    @abstractmethod
    async def unsubscribe_symbols(self, symbols: list[str]) -> None:
        """Unsubscribe from symbols"""

    def add_subscriber(self, callback: Callable[[Candle], None]) -> None:
        """Add data subscriber"""
        self.subscribers.append(callback)

    def remove_subscriber(self, callback: Callable[[Candle], None]) -> None:
        """Remove data subscriber"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def _notify_subscribers(self, candle: Candle) -> None:
        """Notify all subscribers of new candle"""
        for callback in self.subscribers:
            try:
                callback(candle)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Error in streaming subscriber: {exc}")

    async def _handle_reconnect(self) -> None:
        """Handle reconnection logic"""
        if not self.config.auto_reconnect:
            return

        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            print(f"Max reconnection attempts reached for {self.config.provider.value}")
            return

        self.reconnect_attempts += 1
        print(
            f"Reconnecting to {self.config.provider.value} "
            f"(attempt {self.reconnect_attempts})..."
        )

        await asyncio.sleep(self.config.reconnect_delay)

        try:
            success = await self.connect()
            if success:
                self.reconnect_attempts = 0
                print(f"Successfully reconnected to {self.config.provider.value}")
            else:
                await self._handle_reconnect()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Reconnection failed: {exc}")
            await self._handle_reconnect()


class MockStreamingProvider(StreamingDataProvider):
    """Mock streaming provider for testing"""

    def __init__(self, config: StreamingConfig):
        super().__init__(config)
        self._streaming_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._current_prices: Dict[str, Decimal] = {}

    async def connect(self) -> bool:
        """Connect to mock provider"""
        print("📡 Connecting to Mock streaming provider...")
        await asyncio.sleep(0.1)  # Simulate connection delay

        self.is_connected = True
        self._stop_event.clear()

        # Start streaming simulation
        self._streaming_task = asyncio.create_task(self._simulate_streaming())

        print("✅ Connected to Mock streaming provider")
        return True

    async def disconnect(self) -> None:
        """Disconnect from mock provider"""
        print("🔌 Disconnecting from Mock streaming provider...")

        self.is_connected = False
        self._stop_event.set()

        if self._streaming_task:
            await self._streaming_task

        print("✅ Disconnected from Mock streaming provider")

    async def subscribe_symbols(self, symbols: list[str]) -> None:
        """Subscribe to symbols"""
        print(f"➕ Subscribing to symbols: {symbols}")

        # Initialize current prices
        for symbol in symbols:
            if symbol not in self._current_prices:
                self._current_prices[symbol] = Decimal("100.00")  # Base price

        if symbols not in self.config.symbols:
            self.config.symbols.extend(symbols)

    async def unsubscribe_symbols(self, symbols: list[str]) -> None:
        """Unsubscribe from symbols"""
        print(f"➖ Unsubscribing from symbols: {symbols}")

        for symbol in symbols:
            if symbol in self.config.symbols:
                self.config.symbols.remove(symbol)
            if symbol in self._current_prices:
                del self._current_prices[symbol]

    async def _simulate_streaming(self) -> None:
        """Simulate real-time data streaming"""
        while not self._stop_event.is_set():
            try:
                for symbol in self.config.symbols:
                    if symbol in self._current_prices:
                        # Generate realistic price movement
                        current_price = self._current_prices[symbol]

                        # Random price change (-0.5% to +0.5%)
                        import random

                        change_pct = Decimal(str(random.uniform(-0.005, 0.005)))
                        price_change = current_price * change_pct
                        new_price = current_price + price_change

                        # Ensure price stays positive
                        if new_price <= 0:
                            new_price = current_price

                        self._current_prices[symbol] = new_price

                        # Create candle
                        candle = Candle(
                            timestamp=datetime.now(),
                            open=current_price,
                            high=max(current_price, new_price),
                            low=min(current_price, new_price),
                            close=new_price,
                            volume=Decimal(str(random.randint(1000, 10000))),
                            symbol=symbol,
                            timeframe=TimeFrame.MINUTE_1,
                        )

                        # Notify subscribers
                        self._notify_subscribers(candle)

                # Wait before next update
                await asyncio.sleep(1.0)  # 1 second interval

            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Error in mock streaming: {exc}")
                await asyncio.sleep(1.0)


class AlpacaStreamingProvider(StreamingDataProvider):
    """Alpaca streaming provider"""

    def __init__(self, config: StreamingConfig):
        super().__init__(config)
        self._websocket: Optional[websockets.WebSocketServerProtocol] = None
        self._streaming_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def connect(self) -> bool:
        """Connect to Alpaca streaming"""
        try:
            # This would connect to Alpaca's WebSocket API
            # For now, we'll simulate the connection
            print("📡 Connecting to Alpaca streaming...")
            await asyncio.sleep(0.2)  # Simulate connection delay

            self.is_connected = True
            self._stop_event.clear()

            # In a real implementation, you would:
            # uri = f"wss://stream.data.alpaca.markets/v2/iex"
            # self._websocket = await websockets.connect(uri)
            # await self._authenticate()

            print("✅ Connected to Alpaca streaming")
            return True

        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"❌ Failed to connect to Alpaca: {exc}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Alpaca streaming"""
        print("🔌 Disconnecting from Alpaca streaming...")

        self.is_connected = False
        self._stop_event.set()

        if self._websocket:
            await self._websocket.close()

        if self._streaming_task:
            await self._streaming_task

        print("✅ Disconnected from Alpaca streaming")

    async def subscribe_symbols(self, symbols: list[str]) -> None:
        """Subscribe to Alpaca symbols"""
        if not self.is_connected:
            raise RuntimeError("Not connected to Alpaca")

        # In a real implementation:
        # subscribe_message = {
        #     "action": "subscribe",
        #     "bars": symbols,
        #     "quotes": symbols,
        #     "trades": symbols
        # }
        # await self._websocket.send(json.dumps(subscribe_message))

        print(f"➕ Subscribed to Alpaca symbols: {symbols}")

    async def unsubscribe_symbols(self, symbols: list[str]) -> None:
        """Unsubscribe from Alpaca symbols"""
        if not self.is_connected:
            return

        # In a real implementation:
        # unsubscribe_message = {
        #     "action": "unsubscribe",
        #     "bars": symbols,
        #     "quotes": symbols,
        #     "trades": symbols
        # }
        # await self._websocket.send(json.dumps(unsubscribe_message))

        print(f"➖ Unsubscribed from Alpaca symbols: {symbols}")

    async def _authenticate(self) -> None:
        """Authenticate with Alpaca"""
        # In a real implementation:
        # auth_message = {
        #     "action": "auth",
        #     "key": self.config.api_key,
        #     "secret": self.config.secret_key
        # }
        # await self._websocket.send(json.dumps(auth_message))

    async def _handle_message(self, message: str) -> None:
        """Handle incoming Alpaca message"""
        try:
            data = json.loads(message)

            # Handle different message types
            if "bars" in data:
                for bar_data in data["bars"]:
                    candle = self._convert_alpaca_bar(bar_data)
                    self._notify_subscribers(candle)

        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Error handling Alpaca message: {exc}")

    def _convert_alpaca_bar(self, bar_data: Dict) -> Candle:
        """Convert Alpaca bar data to Candle"""
        return Candle(
            timestamp=datetime.fromisoformat(bar_data["t"]),
            open=Decimal(str(bar_data["o"])),
            high=Decimal(str(bar_data["h"])),
            low=Decimal(str(bar_data["l"])),
            close=Decimal(str(bar_data["c"])),
            volume=Decimal(str(bar_data["v"])),
            symbol=bar_data["S"],
            timeframe=TimeFrame.MINUTE_1,
        )


class StreamingManager:
    """Manages multiple streaming providers and data distribution"""

    def __init__(self):
        self.providers: Dict[StreamingProvider, StreamingDataProvider] = {}
        self.subscribers: list[Callable[[Candle], None]] = []
        self.symbol_subscriptions: Dict[str, list[StreamingProvider]] = {}
        self.is_running = False

    def add_provider(self, provider: StreamingDataProvider) -> None:
        """Add a streaming provider"""
        self.providers[provider.config.provider] = provider
        provider.add_subscriber(self._on_candle_received)

    def remove_provider(self, provider_type: StreamingProvider) -> None:
        """Remove a streaming provider"""
        if provider_type in self.providers:
            provider = self.providers[provider_type]
            provider.remove_subscriber(self._on_candle_received)
            del self.providers[provider_type]

    def add_subscriber(self, callback: Callable[[Candle], None]) -> None:
        """Add data subscriber"""
        self.subscribers.append(callback)

    def remove_subscriber(self, callback: Callable[[Candle], None]) -> None:
        """Remove data subscriber"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    async def start(self) -> bool:
        """Start all streaming providers"""
        if self.is_running:
            return True

        success_count = 0
        for provider in self.providers.values():
            try:
                success = await provider.connect()
                if success:
                    success_count += 1
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(
                    f"Failed to start provider {provider.config.provider.value}: {exc}"
                )

        self.is_running = success_count > 0
        return self.is_running

    async def stop(self) -> None:
        """Stop all streaming providers"""
        if not self.is_running:
            return

        for provider in self.providers.values():
            try:
                await provider.disconnect()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(
                    f"Error stopping provider {provider.config.provider.value}: {exc}"
                )

        self.is_running = False

    async def subscribe_symbol(
        self, symbol: str, providers: Optional[list[StreamingProvider]] = None
    ) -> None:
        """Subscribe to a symbol on specified providers"""
        if providers is None:
            providers = list(self.providers.keys())

        for provider_type in providers:
            if provider_type in self.providers:
                provider = self.providers[provider_type]
                await provider.subscribe_symbols([symbol])

                # Track subscription
                if symbol not in self.symbol_subscriptions:
                    self.symbol_subscriptions[symbol] = []
                if provider_type not in self.symbol_subscriptions[symbol]:
                    self.symbol_subscriptions[symbol].append(provider_type)

    async def unsubscribe_symbol(
        self, symbol: str, providers: Optional[list[StreamingProvider]] = None
    ) -> None:
        """Unsubscribe from a symbol on specified providers"""
        if providers is None:
            providers = self.symbol_subscriptions.get(symbol, [])

        for provider_type in providers:
            if provider_type in self.providers:
                provider = self.providers[provider_type]
                await provider.unsubscribe_symbols([symbol])

                # Update subscription tracking
                if symbol in self.symbol_subscriptions:
                    if provider_type in self.symbol_subscriptions[symbol]:
                        self.symbol_subscriptions[symbol].remove(provider_type)
                    if not self.symbol_subscriptions[symbol]:
                        del self.symbol_subscriptions[symbol]

    def _on_candle_received(self, candle: Candle) -> None:
        """Handle candle from any provider"""
        for callback in self.subscribers:
            try:
                callback(candle)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Error in streaming subscriber: {exc}")

    def get_status(self) -> Dict[str, Any]:
        """Get streaming status"""
        return {
            "is_running": self.is_running,
            "providers": {
                provider_type.value: provider.is_connected
                for provider_type, provider in self.providers.items()
            },
            "subscriptions": dict(self.symbol_subscriptions),
            "subscriber_count": len(self.subscribers),
        }


class StreamingFactory:
    """Factory for creating streaming providers"""

    @staticmethod
    def create_provider(config: StreamingConfig) -> StreamingDataProvider:
        """Create a streaming provider"""
        if config.provider == StreamingProvider.MOCK:
            return MockStreamingProvider(config)
        elif config.provider == StreamingProvider.ALPACA:
            return AlpacaStreamingProvider(config)
        else:
            raise ValueError(f"Unsupported streaming provider: {config.provider}")

    @staticmethod
    def create_manager_with_providers(
        configs: list[StreamingConfig],
    ) -> StreamingManager:
        """Create a streaming manager with multiple providers"""
        manager = StreamingManager()

        for config in configs:
            provider = StreamingFactory.create_provider(config)
            manager.add_provider(provider)

        return manager
