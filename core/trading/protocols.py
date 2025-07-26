"""
Broker interface protocols and abstractions.

This module defines the abstract interfaces that all broker implementations
must satisfy. This allows the trading system to work with different brokers
(paper, live, etc.) through a common interface.
"""

from __future__ import annotations

from typing import Protocol

from .models import AccountState, Order, OrderReceipt, Position

__all__ = ["Broker"]


class Broker(Protocol):
    """Abstract broker interface for order execution and account management.

    This protocol defines the standard interface that all broker implementations
    must provide. It supports both paper trading (simulation) and live trading
    through the same interface.

    All methods are async to support real-world broker APIs that typically
    require network calls. This also ensures consistency when switching
    between paper and live trading.
    """

    async def submit(self, order: Order) -> OrderReceipt:
        """Submit an order for execution.

        Args:
            order: Order specification with symbol, quantity, price, etc.

        Returns:
            OrderReceipt with broker order ID and initial status.

        Raises:
            BrokerError: If order validation fails or submission is rejected.
        """
        ...

    async def positions(self) -> list[Position]:
        """Get current open positions.

        Returns:
            List of current positions across all symbols.
        """
        ...

    async def account(self) -> AccountState:
        """Get current account state and balances.

        Returns:
            Current account state including cash, equity, and positions.
        """
        ...

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        Args:
            order_id: Broker order ID to cancel.

        Returns:
            True if cancellation was successful, False otherwise.
        """
        ...

    async def close_position(
        self, symbol: str, quantity: float | None = None
    ) -> OrderReceipt:
        """Close an open position.

        Args:
            symbol: Symbol to close position for.
            quantity: Partial quantity to close (None = close entire position).

        Returns:
            OrderReceipt for the closing order.
        """
        ...
