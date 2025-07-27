"""
Binance Futures live broker implementation for testnet trading.

This module implements the Binance Futures API for live trading on testnet,
including REST order management and WebSocket streaming for real-time updates.
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

__all__ = ["BinanceConfig", "BinanceFuturesBroker"]

logger = logging.getLogger(__name__)


class BinanceConfig(BaseSettings):
    """Binance API configuration loaded from environment variables.

    Configuration options:
    - position_side_mode: "ONEWAY" (default) or "HEDGE" for position management
    - recv_window_ms: API receive window in milliseconds (default 5000)
    """

    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    # Position side mode configuration
    # ONEWAY: Traditional mode - one position per symbol
    # HEDGE: Advanced mode - separate LONG/SHORT positions per symbol
    position_side_mode: str = "ONEWAY"  # "ONEWAY" or "HEDGE"

    # Clock skew handling - receive window for API requests
    recv_window_ms: int = 5000  # Default 5 second receive window

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}

    def model_post_init(self, __context: Any) -> None:
        """Validate that required fields are set."""
        if not self.binance_api_key:
            raise ValueError("BINANCE_API_KEY environment variable is required")
        if not self.binance_api_secret:
            raise ValueError("BINANCE_API_SECRET environment variable is required")
        if self.position_side_mode not in ["ONEWAY", "HEDGE"]:
            raise ValueError("position_side_mode must be 'ONEWAY' or 'HEDGE'")


class BinanceFuturesBroker(HttpLiveBroker):
    """Binance Futures broker implementation for live trading.

    Supports:
    - Market and limit orders
    - Position management
    - Account information
    - WebSocket streaming
    """

    def __init__(self, config: BinanceConfig | None = None) -> None:
        """Initialize Binance Futures broker.

        Args:
            config: Binance configuration (loads from env if None)
        """
        if config is None:
            config = BinanceConfig()

        # Set up base URLs
        if config.binance_testnet:
            base_url = "https://testnet.binancefuture.com/fapi/v1"
            ws_url = "wss://stream.binancefuture.com/ws"
        else:
            base_url = "https://fapi.binance.com/fapi/v1"
            ws_url = "wss://fstream.binance.com/ws"

        live_config = LiveBrokerConfig(
            api_key=config.binance_api_key,
            api_secret=config.binance_api_secret,
            base_url=base_url,
            testnet=config.binance_testnet,
        )

        super().__init__(live_config)
        self.ws_url = ws_url
        self._ws_task: asyncio.Task[None] | None = None
        self._listen_key: str | None = None
        self._order_map: dict[str, str] = {}  # local_id -> binance_id
        self._reverse_order_map: dict[str, str] = {}  # binance_id -> local_id

        # Clock skew handling
        self._config = config
        self._server_time_offset: int = 0  # ms offset from server time
        self._recv_window_margin: int = 0  # additional margin for recv window

    async def initialize(self) -> None:
        """Initialize broker connection and sync with server time.

        Should be called after creating the broker instance.
        """
        await self._sync_server_time()
        await self._setup_position_side_mode()

    async def _setup_position_side_mode(self) -> None:
        """Configure position side mode for the account.

        Sets up ONEWAY (default) or HEDGE mode based on configuration.
        This only needs to be called once per account.
        """
        try:
            # Check current position side mode
            response = await self._http_request("GET", "/positionSide/dual", {})
            current_dual_side = response.get("dualSidePosition", False)

            # Determine target mode
            target_dual_side = self._config.position_side_mode == "HEDGE"

            if current_dual_side != target_dual_side:
                # Change position side mode
                await self._http_request(
                    "POST",
                    "/positionSide/dual",
                    data={"dualSidePosition": "true" if target_dual_side else "false"},
                )
                self.logger.info(
                    f"Position side mode changed to {self._config.position_side_mode}"
                )
            else:
                self.logger.info(
                    f"Position side mode already set to {self._config.position_side_mode}"
                )

        except Exception as e:
            self.logger.warning(f"Failed to set position side mode: {e}")
            # Non-critical error - continue with current mode

    async def submit(self, order: Order) -> OrderReceipt:
        """Submit order to Binance Futures.

        Args:
            order: Order specification

        Returns:
            OrderReceipt with Binance order ID and status
        """
        try:
            # Map order type
            order_type = "MARKET" if order.order_type == OrderType.MARKET else "LIMIT"
            side = "BUY" if order.quantity > 0 else "SELL"

            # Generate client order ID if not provided
            client_order_id = order.client_id or f"order_{int(time.time() * 1000)}"

            payload = {
                "symbol": order.symbol,
                "side": side,
                "type": order_type,
                "quantity": abs(float(order.quantity)),
                "newClientOrderId": client_order_id,
            }

            if order.order_type == OrderType.LIMIT and order.price:
                payload["price"] = float(order.price)
                payload["timeInForce"] = "GTC"

            response = await self._http_request(
                "POST", "/order", data=payload, signed=True
            )

            # Store order mapping
            binance_order_id = response["orderId"]
            self._order_map[client_order_id] = str(binance_order_id)
            self._reverse_order_map[str(binance_order_id)] = client_order_id

            return self._map_order_response(response, order, client_order_id)

        except Exception as e:
            self.logger.error(f"Order submission failed: {e}")
            raise BrokerError(f"Failed to submit order: {e}") from e

    async def positions(self) -> list[Position]:
        """Get current futures positions.

        Returns:
            List of open positions
        """
        try:
            response = await self._http_request("GET", "/positionRisk", signed=True)
            # Cast response to list since we know the positions endpoint returns a list
            positions_data: list[dict[str, Any]] = response  # type: ignore[assignment]

            positions = []
            for pos_data in positions_data:
                if float(pos_data["positionAmt"]) != 0:
                    positions.append(
                        Position(
                            symbol=pos_data["symbol"],
                            quantity=Decimal(pos_data["positionAmt"]),
                            avg_entry_price=float(pos_data["entryPrice"]),
                            current_price=float(
                                pos_data.get("markPrice", pos_data["entryPrice"])
                            ),
                            unrealized_pnl=float(pos_data["unRealizedProfit"]),
                            entry_timestamp=datetime.now(),  # Binance doesn't provide this
                        )
                    )

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
            response: dict[str, Any] = await self._http_request(
                "GET", "/account", signed=True
            )

            # Extract USDT balance - Binance uses "assets" in futures API
            usdt_balance = 0.0
            assets = response.get("assets", response.get("balances", []))
            for balance in assets:
                if balance["asset"] == "USDT":
                    usdt_balance = float(
                        balance.get("walletBalance", balance.get("balance", 0))
                    )
                    break

            # Get positions for position map
            positions = await self.positions()
            position_map = {pos.symbol: pos for pos in positions}

            return AccountState(
                cash_balance=usdt_balance,
                equity=float(response.get("totalWalletBalance", usdt_balance)),
                positions=position_map,
                realized_pnl=float(response.get("totalRealizedProfit", 0)),
                open_orders=len(response.get("positions", [])),
                timestamp=datetime.now(),
            )

        except Exception as e:
            self.logger.error(f"Failed to get account: {e}")
            raise BrokerError(f"Failed to get account: {e}") from e

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        Args:
            order_id: Local order ID to cancel

        Returns:
            True if cancellation successful
        """
        try:
            binance_order_id = self._order_map.get(order_id)
            if not binance_order_id:
                self.logger.warning(f"Order {order_id} not found in order map")
                return False

            # Get symbol from order (we'd need to store this)
            # For now, this is a simplified implementation
            response: dict[str, Any] = await self._http_request(
                "DELETE", "/order", params={"orderId": binance_order_id}, signed=True
            )

            result: bool = response["status"] == "CANCELED"
            return result

        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

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
        positions = await self.positions()
        position = next((p for p in positions if p.symbol == symbol), None)

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

    def _map_order_status(self, binance_status: str) -> OrderStatus:
        """Map Binance order status to our OrderStatus enum."""
        mapping = {
            "NEW": OrderStatus.PENDING,
            "PARTIALLY_FILLED": OrderStatus.PARTIAL,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.CANCELLED,
        }
        return mapping.get(binance_status, OrderStatus.PENDING)

    async def _sync_server_time(self) -> None:
        """Synchronize with Binance server time to handle clock skew.

        Fetches server time from /fapi/v1/time and calculates offset
        to adjust recvWindow margin for reliable API calls.
        """
        try:
            response = await self._http_request("GET", "/time", {})
            server_time = response["serverTime"]
            local_time = int(time.time() * 1000)

            # Calculate offset (server - local)
            self._server_time_offset = server_time - local_time

            # Set recv window margin based on offset magnitude
            offset_abs = abs(self._server_time_offset)
            if offset_abs > 1000:  # More than 1 second difference
                self._recv_window_margin = min(offset_abs + 1000, 3000)  # Cap at 3s
                self.logger.warning(
                    f"Large clock skew detected: {self._server_time_offset}ms. "
                    f"Adjusting recvWindow margin to {self._recv_window_margin}ms"
                )
            else:
                self._recv_window_margin = 500  # Small default margin

            self.logger.info(
                f"Server time sync: offset={self._server_time_offset}ms, "
                f"margin={self._recv_window_margin}ms"
            )

        except Exception as e:
            self.logger.error(f"Failed to sync server time: {e}")
            # Use conservative default
            self._recv_window_margin = 2000

    async def _http_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        signed: bool = True,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        """Override to add recvWindow for authenticated requests."""
        if signed and params is not None:
            # Add recvWindow with calculated margin for clock skew
            recv_window = self._config.recv_window_ms + self._recv_window_margin
            params["recvWindow"] = recv_window

        return await super()._http_request(
            method, endpoint, params, data, signed, retry_count
        )

    async def start_websocket(self) -> None:
        """Start WebSocket connection for real-time updates."""
        if self._ws_task is not None:
            self.logger.warning("WebSocket already running")
            return

        try:
            # Get listen key for user data stream
            response = await self._http_request("POST", "/listenKey", signed=True)
            self._listen_key = response["listenKey"]

            # Start WebSocket task
            self._ws_task = asyncio.create_task(self._websocket_loop())
            self.logger.info("Started Binance WebSocket connection")

        except Exception as e:
            self.logger.error(f"Failed to start WebSocket: {e}")
            raise BrokerError(f"Failed to start WebSocket: {e}") from e

    async def stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        if self._ws_task is None:
            return

        # Cancel the WebSocket task
        self._ws_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._ws_task

        self._ws_task = None

        # Close listen key if we have one
        if self._listen_key:
            with contextlib.suppress(Exception):
                await self._http_request("DELETE", "/listenKey", signed=True)
            self._listen_key = None

        self.logger.info("Stopped Binance WebSocket connection")

    async def _websocket_loop(self) -> None:
        """Main WebSocket message handling loop."""
        if not self._listen_key:
            self.logger.error("No listen key available for WebSocket")
            return

        if self._session is None:
            self.logger.error("Session not initialized for WebSocket")
            return

        ws_url = f"{self.ws_url}/{self._listen_key}"

        try:
            async with self._session.ws_connect(ws_url) as ws:
                self._ws = ws
                self.logger.info(f"Connected to Binance WebSocket: {ws_url}")

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                            await self._handle_websocket_message(data)
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Invalid JSON from WebSocket: {e}")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        self.logger.error(f"WebSocket error: {ws.exception()}")
                        break

        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {e}")
        finally:
            self._ws = None

    async def _handle_websocket_message(self, data: dict[str, Any]) -> None:
        """Handle incoming WebSocket messages."""
        event_type = data.get("e")

        if event_type == "ORDER_TRADE_UPDATE":
            # Handle order updates
            order_data = data.get("o", {})
            client_order_id = order_data.get("c")
            if client_order_id in self._reverse_order_map:
                self.logger.info(
                    f"Order update for {client_order_id}: {order_data.get('X')}"
                )

        elif event_type == "ACCOUNT_UPDATE":
            # Handle account/position updates
            self.logger.info("Account update received")

        else:
            self.logger.debug(f"Unhandled WebSocket event: {event_type}")

    def _map_order_response(
        self, response: dict[str, Any], original_order: Order, client_order_id: str
    ) -> OrderReceipt:
        """Map Binance order response to our OrderReceipt format."""
        from uuid import uuid4

        status = self._map_order_status(response["status"])

        return OrderReceipt(
            order_id=str(response["orderId"]),  # Broker order ID
            client_id=client_order_id,  # Our client order ID
            status=status,
            filled_quantity=Decimal(response.get("executedQty", "0")),
            avg_fill_price=float(response.get("avgPrice", 0)) or original_order.price,
            message=f"Binance order {response['orderId']}: {response['status']}",
        )
