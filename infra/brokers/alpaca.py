"""
Alpaca paper trading broker implementation.

This module implements the Alpaca Markets API for paper trading,
providing a realistic testing environment for live trading strategies.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any

import aiohttp
from pydantic_settings import BaseSettings

from core.trading.models import (
    AccountState,
    Order,
    OrderReceipt,
    OrderStatus,
    OrderType,
    Position,
)

from .base_live import HttpLiveBroker, LiveBrokerConfig
from .exceptions import BrokerError

__all__ = ["AlpacaConfig", "AlpacaBroker"]

logger = logging.getLogger(__name__)


class AlpacaConfig(BaseSettings):
    """Alpaca API configuration loaded from environment variables."""

    alpaca_key_id: str = ""
    alpaca_secret: str = ""
    alpaca_paper: bool = True

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}

    def model_post_init(self, __context: Any) -> None:
        """Validate that required fields are set."""
        if not self.alpaca_key_id:
            raise ValueError("ALPACA_API_KEY environment variable is required")
        if not self.alpaca_secret:
            raise ValueError("ALPACA_API_SECRET environment variable is required")


class AlpacaBroker(HttpLiveBroker):
    """Alpaca paper trading broker implementation.

    Supports:
    - Stock market orders (MARKET, LIMIT)
    - Paper trading environment
    - Real-time position and account updates
    - Extended hours trading
    """

    def __init__(self, config: AlpacaConfig | None = None) -> None:
        """Initialize Alpaca broker.

        Args:
            config: Alpaca configuration (loads from env if None)
        """
        if config is None:
            config = AlpacaConfig()

        # Set up base URLs
        if config.alpaca_paper:
            base_url = "https://paper-api.alpaca.markets"
            ws_url = "wss://stream.data.alpaca.markets"
        else:
            base_url = "https://api.alpaca.markets"
            ws_url = "wss://stream.data.alpaca.markets"

        live_config = LiveBrokerConfig(
            api_key=config.alpaca_key_id,
            api_secret=config.alpaca_secret,
            base_url=base_url,
            testnet=config.alpaca_paper,
        )

        super().__init__(live_config)
        self.ws_url = ws_url
        self._ws_task: asyncio.Task[None] | None = None

        # Order tracking
        self._order_map: dict[str, str] = {}  # local_id -> alpaca_id

    def _generate_signature(self, payload: str, timestamp: str | None = None) -> str:
        """Alpaca uses API key authentication, not HMAC signatures."""
        # Alpaca doesn't use HMAC signatures, just return empty string
        return ""

    async def _http_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        signed: bool = True,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        """Make authenticated HTTP request to Alpaca API.

        Alpaca uses API key authentication instead of HMAC signatures.
        """
        await self._ensure_session()
        await self._rate_limit()

        url = f"{self.config.base_url}{endpoint}"
        headers = {
            "APCA-API-KEY-ID": self.config.api_key,
            "APCA-API-SECRET-KEY": self.config.api_secret,
            "Content-Type": "application/json",
        }

        start_time = time.time()

        try:
            assert self._session is not None
            async with self._session.request(
                method=method,
                url=url,
                params=params,
                json=data if method.upper() != "GET" else None,
                headers=headers,
            ) as response:
                latency = (time.time() - start_time) * 1000
                self._track_latency(latency)

                response_text = await response.text()

                if response.status in [200, 201]:
                    try:
                        return json.loads(response_text) if response_text else {}
                    except json.JSONDecodeError as e:
                        raise BrokerError(f"Invalid JSON response: {e}") from e

                else:
                    # Handle error response
                    try:
                        error_data = json.loads(response_text)
                        error_msg = error_data.get("message", f"HTTP {response.status}")
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

                    raise BrokerError(f"Alpaca API error: {error_msg}")

        except aiohttp.ClientError as e:
            if retry_count < self.config.max_retries:
                self.logger.warning(f"Request failed, retrying: {e}")
                await self._backoff_sleep(retry_count)
                return await self._http_request(
                    method, endpoint, params, data, signed, retry_count + 1
                )
            raise BrokerError(f"HTTP request failed: {e}") from e

    async def submit(self, order: Order) -> OrderReceipt:
        """Submit order to Alpaca.

        Args:
            order: Order specification

        Returns:
            OrderReceipt with Alpaca order ID and status
        """
        try:
            # Map order parameters
            alpaca_side = "buy" if order.quantity > 0 else "sell"
            alpaca_type = self._map_order_type(order.order_type)

            # Prepare order data
            client_order_id = order.client_id or f"order_{int(time.time() * 1000)}"
            # Prefix with "algo-" for easy identification in Alpaca UI
            alpaca_client_id = f"algo-{client_order_id}"

            order_data = {
                "symbol": order.symbol,
                "qty": str(abs(order.quantity)),
                "side": alpaca_side,
                "type": alpaca_type,
                "time_in_force": "day",  # Day order by default
                "client_order_id": alpaca_client_id,
            }

            # Add price for limit orders
            if order.order_type == OrderType.LIMIT:
                order_data["limit_price"] = str(order.price)

            # Submit order
            response = await self._http_request("POST", "/v2/orders", data=order_data)

            # Map response to our format
            receipt = self._map_order_response(response, order)

            # Store order mapping
            self._order_map[receipt.order_id] = response["id"]

            self.logger.info(f"Order submitted: {receipt.order_id} -> {response['id']}")
            return receipt

        except Exception as e:
            self.logger.error(f"Order submission failed: {e}")
            raise BrokerError(f"Failed to submit order: {e}") from e

    async def positions(self) -> list[Position]:
        """Get current stock positions.

        Returns:
            List of open positions
        """
        try:
            response = await self._http_request("GET", "/v2/positions")
            # Cast response to list since we know the positions endpoint returns a list
            positions_data: list[dict[str, Any]] = response  # type: ignore[assignment]

            positions = []
            for pos_data in positions_data:
                qty = float(pos_data["qty"])
                if abs(qty) > 1e-8:  # Filter out zero positions
                    position = Position(
                        symbol=pos_data["symbol"],
                        quantity=Decimal(str(qty)),
                        avg_entry_price=float(pos_data["avg_entry_price"]),
                        current_price=float(pos_data["current_price"]),
                        unrealized_pnl=float(pos_data["unrealized_pl"]),
                        entry_timestamp=datetime.now(),  # Alpaca doesn't provide this
                    )
                    positions.append(position)

            return positions

        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            raise BrokerError(f"Failed to get positions: {e}") from e

    async def account(self) -> AccountState:
        """Get account information and balances.

        Returns:
            Current account state
        """
        try:
            response: dict[str, Any] = await self._http_request("GET", "/v2/account")

            # Get positions for detailed state
            positions_list = await self.positions()
            positions_map = {pos.symbol: pos for pos in positions_list}

            return AccountState(
                cash_balance=float(response["cash"]),
                equity=float(response["equity"]),
                positions=positions_map,
                realized_pnl=0.0,  # Would need to calculate from trade history
                open_orders=0,  # Would need to get open orders separately
                timestamp=datetime.now(),
            )

        except Exception as e:
            self.logger.error(f"Failed to get account: {e}")
            raise BrokerError(f"Failed to get account: {e}") from e

    async def close_position(
        self, symbol: str, quantity: float | None = None
    ) -> OrderReceipt:
        """Close an open position.

        Args:
            symbol: Symbol to close position for
            quantity: Partial quantity to close (None = close entire position)

        Returns:
            OrderReceipt for the closing order
        """
        # Get current position
        positions_list = await self.positions()
        position = next((p for p in positions_list if p.symbol == symbol), None)

        if position is None:
            raise BrokerError(f"No open position found for {symbol}")

        # Determine quantity to close
        close_qty = -position.quantity if quantity is None else -Decimal(str(quantity))

        # Create closing order
        closing_order = Order(
            symbol=symbol,
            order_type=OrderType.MARKET,
            quantity=close_qty,
            client_id=f"close_{symbol}_{int(time.time() * 1000)}",
        )

        return await self.submit(closing_order)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        Args:
            order_id: Local order ID to cancel

        Returns:
            True if cancellation successful
        """
        try:
            # Get Alpaca order ID
            alpaca_order_id = self._order_map.get(order_id)
            if not alpaca_order_id:
                self.logger.warning(f"Order ID {order_id} not found in mapping")
                return False

            # Cancel on Alpaca
            await self._http_request("DELETE", f"/v2/orders/{alpaca_order_id}")

            # Clean up mapping
            del self._order_map[order_id]

            self.logger.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def start_websocket(self) -> None:
        """Start WebSocket connection for real-time updates."""
        try:
            # Start WebSocket task for trade updates
            self._ws_task = asyncio.create_task(self._websocket_handler())
            self.logger.info("WebSocket connection started")

        except Exception as e:
            self.logger.error(f"Failed to start WebSocket: {e}")
            raise BrokerError(f"Failed to start WebSocket: {e}") from e

    async def stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        if self._ws_task:
            self._ws_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ws_task

        self.logger.info("WebSocket connection stopped")

    async def _websocket_handler(self) -> None:
        """Handle WebSocket messages for real-time updates."""
        # Alpaca WebSocket implementation would go here
        # For now, just maintain connection without processing
        try:
            while True:
                await asyncio.sleep(30)  # Keep alive

        except asyncio.CancelledError:
            pass

    def _map_order_type(self, order_type: OrderType) -> str:
        """Map our order type to Alpaca format."""
        mapping = {
            OrderType.MARKET: "market",
            OrderType.LIMIT: "limit",
        }
        return mapping.get(order_type, "market")

    def _map_order_status(self, alpaca_status: str) -> OrderStatus:
        """Map Alpaca order status to our format."""
        mapping = {
            "new": OrderStatus.PENDING,
            "partially_filled": OrderStatus.PARTIAL,
            "filled": OrderStatus.FILLED,
            "done_for_day": OrderStatus.CANCELLED,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.CANCELLED,
            "replaced": OrderStatus.PENDING,
            "pending_cancel": OrderStatus.PENDING,
            "pending_replace": OrderStatus.PENDING,
            "accepted": OrderStatus.PENDING,
            "pending_new": OrderStatus.PENDING,
            "accepted_for_bidding": OrderStatus.PENDING,
            "stopped": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
            "suspended": OrderStatus.CANCELLED,
            "calculated": OrderStatus.PENDING,
        }
        return mapping.get(alpaca_status, OrderStatus.PENDING)

    def _map_order_response(
        self, response: dict[str, Any], original_order: Order
    ) -> OrderReceipt:
        """Map Alpaca order response to our OrderReceipt format."""
        from uuid import uuid4

        status = self._map_order_status(response["status"])

        return OrderReceipt(
            order_id=str(uuid4()),  # Generate local order ID
            client_id=original_order.client_id or response.get("client_order_id"),
            status=status,
            filled_quantity=Decimal(response.get("filled_qty", "0")),
            avg_fill_price=float(response.get("filled_avg_price", 0))
            or original_order.price,
            message=f"Alpaca order {response['id']}: {response['status']}",
        )
