"""
Base live broker implementation with common authentication and REST helpers.

This module provides the foundation for all live broker implementations,
including HMAC signing, rate limiting, retry logic, and async HTTP client setup.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import ssl
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import aiohttp
import certifi

from core.trading.models import AccountState, Order, OrderReceipt, Position
from core.trading.protocols import Broker

from .exceptions import BrokerError

__all__ = ["LiveBrokerConfig", "HttpLiveBroker"]

logger = logging.getLogger(__name__)


@dataclass
class LiveBrokerConfig:
    """Configuration for live broker connections."""

    api_key: str
    api_secret: str
    base_url: str
    testnet: bool = True
    ws_timeout: int = 30
    rest_timeout: int = 10
    max_retries: int = 3
    retry_backoff: float = 1.0


class HttpLiveBroker(Broker, ABC):
    """Base class for HTTP-based live brokers with authentication and retry logic.

    Provides common functionality for:
    - HMAC-SHA256 signature generation
    - Rate-limited HTTP requests with exponential backoff
    - WebSocket connection management
    - Error handling and logging
    """

    def __init__(self, config: LiveBrokerConfig) -> None:
        """Initialize live broker with configuration.

        Args:
            config: Broker configuration including API credentials
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None

        # Rate limiting
        self._last_request_time = 0.0
        self._min_request_interval = 0.1  # 100ms between requests

        # Latency tracking
        self._request_latencies: list[float] = []
        self._max_latency_samples = 100

    async def __aenter__(self) -> HttpLiveBroker:
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure HTTP session is initialized."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.rest_timeout)

            # Create SSL context with certifi certificates
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED

            # Create connector with proper SSL context
            connector = aiohttp.TCPConnector(ssl=ssl_context)

            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "QuantBot/1.0"},
                connector=connector,
            )

    async def close(self) -> None:
        """Close HTTP session and WebSocket connections."""
        if self._ws and not self._ws.closed:
            await self._ws.close()

        if self._session and not self._session.closed:
            await self._session.close()

    def _generate_signature(self, payload: str, timestamp: str | None = None) -> str:
        """Generate HMAC-SHA256 signature for request authentication.

        Args:
            payload: Request payload to sign
            timestamp: Optional timestamp (uses current time if None)

        Returns:
            Hex-encoded HMAC signature
        """
        if timestamp is None:
            timestamp = str(int(time.time() * 1000))

        message = timestamp + payload
        signature = hmac.new(
            self.config.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return signature

    async def _rate_limit(self) -> None:
        """Apply rate limiting to prevent API abuse."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)

        self._last_request_time = time.time()

    async def _http_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        signed: bool = True,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        """Make authenticated HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            signed: Whether to sign the request
            retry_count: Current retry attempt

        Returns:
            Parsed JSON response

        Raises:
            BrokerError: If request fails after all retries
        """
        await self._ensure_session()
        await self._rate_limit()

        url = f"{self.config.base_url}{endpoint}"
        headers = {"X-MBX-APIKEY": self.config.api_key} if signed else {}

        # Prepare request payload for signing
        if signed:
            timestamp = str(int(time.time() * 1000))

            # Combine params and data for signature
            all_params = {}
            if params:
                all_params.update(params)
            if data:
                all_params.update(data)

            # Add timestamp
            all_params["timestamp"] = timestamp

            # Create query string for signature
            query_string = "&".join(f"{k}={v}" for k, v in sorted(all_params.items()))
            signature = self._generate_signature(query_string, timestamp)
            all_params["signature"] = signature

            # Split back to params vs data based on method
            if method.upper() == "GET":
                params = all_params
                data = None
            else:
                params = {"timestamp": timestamp, "signature": signature}
                if data:
                    data.update({"timestamp": timestamp, "signature": signature})
                else:
                    data = {"timestamp": timestamp, "signature": signature}

        start_time = time.time()

        try:
            assert self._session is not None  # Type safety
            async with self._session.request(
                method=method,
                url=url,
                params=params,
                json=data if method.upper() != "GET" else None,
                headers=headers,
            ) as response:
                latency = (time.time() - start_time) * 1000  # Convert to ms
                self._track_latency(latency)

                response_text = await response.text()

                if response.status == 200:
                    try:
                        result: dict[str, Any] = json.loads(response_text)
                        return result
                    except json.JSONDecodeError as e:
                        raise BrokerError(f"Invalid JSON response: {e}") from e

                else:
                    # Handle error response
                    try:
                        error_data = json.loads(response_text)
                        error_msg = error_data.get("msg", f"HTTP {response.status}")
                    except json.JSONDecodeError:
                        error_msg = f"HTTP {response.status}: {response_text}"

                    # Retry on certain error codes
                    if (
                        response.status in [429, 500, 502, 503, 504]
                        and retry_count < self.config.max_retries
                    ):
                        await self._backoff_sleep(retry_count)
                        return await self._http_request(
                            method, endpoint, params, data, signed, retry_count + 1
                        )

                    raise BrokerError(f"API request failed: {error_msg}")

        except aiohttp.ClientError as e:
            if retry_count < self.config.max_retries:
                self.logger.warning(f"Request failed, retrying: {e}")
                await self._backoff_sleep(retry_count)
                return await self._http_request(
                    method, endpoint, params, data, signed, retry_count + 1
                )
            raise BrokerError(f"HTTP request failed: {e}") from e

    async def _backoff_sleep(self, retry_count: int) -> None:
        """Sleep with exponential backoff."""
        sleep_time = self.config.retry_backoff * (2**retry_count)
        await asyncio.sleep(sleep_time)

    def _track_latency(self, latency_ms: float) -> None:
        """Track request latency for monitoring."""
        self._request_latencies.append(latency_ms)

        # Keep only recent samples
        if len(self._request_latencies) > self._max_latency_samples:
            self._request_latencies.pop(0)

    def get_latency_stats(self) -> dict[str, float]:
        """Get latency statistics for monitoring.

        Returns:
            Dictionary with avg, max, and p95 latency in milliseconds
        """
        if not self._request_latencies:
            return {"avg": 0.0, "max": 0.0, "p95": 0.0}

        latencies = sorted(self._request_latencies)
        n = len(latencies)
        p95_idx = int(0.95 * n)

        return {
            "avg": sum(latencies) / n,
            "max": max(latencies),
            "p95": latencies[p95_idx] if p95_idx < n else latencies[-1],
        }

    # Abstract methods that subclasses must implement
    @abstractmethod
    async def submit(self, order: Order) -> OrderReceipt:
        """Submit order to broker."""
        pass

    @abstractmethod
    async def positions(self) -> list[Position]:
        """Get current positions."""
        pass

    @abstractmethod
    async def account(self) -> AccountState:
        """Get account state."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order."""
        pass

    @abstractmethod
    async def start_websocket(self) -> None:
        """Start WebSocket connection for real-time updates."""
        pass

    @abstractmethod
    async def stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        pass
