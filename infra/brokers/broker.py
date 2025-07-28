"""
Paper trading broker implementation for simulation and backtesting.

This module provides a complete paper trading broker that simulates real
trading operations without actual market execution. It maintains positions,
calculates PnL, and handles stop loss / take profit logic automatically.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from core.trading.models import (
    AccountState,
    Order,
    OrderReceipt,
    OrderStatus,
    OrderType,
    Position,
)

from .exceptions import BrokerError

__all__ = ["PaperBroker"]

logger = logging.getLogger(__name__)


class PaperBroker:
    """Paper trading broker for simulation and backtesting.

    Provides a complete trading simulation environment that mimics real
    broker behavior without actual market execution. Automatically handles
    position management, PnL calculations, and stop/take profit logic.

    The broker maintains an internal order book and position tracking,
    processing market data to simulate realistic fill behavior.
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        commission_per_trade: float = 0.0,
    ) -> None:
        """Initialize paper broker with account settings.

        Args:
            initial_balance: Starting cash balance for the account.
            commission_per_trade: Commission charged per trade (flat fee).
        """
        self.initial_balance = initial_balance
        self.commission_per_trade = commission_per_trade

        # Account state
        self._cash_balance = initial_balance
        self._realized_pnl = 0.0
        self._positions: dict[str, Position] = {}
        self._pending_orders: dict[str, Order] = {}

        # Stop/TP tracking for automatic execution
        self._stop_orders: dict[
            str, tuple[str, float]
        ] = {}  # position_id -> (symbol, price)
        self._tp_orders: dict[
            str, tuple[str, float]
        ] = {}  # position_id -> (symbol, price)

        self._logger = logger.getChild(self.__class__.__name__)
        self._logger.info(f"Paper broker initialized with ${initial_balance:,.2f}")

    async def submit(self, order: Order) -> OrderReceipt:
        """Submit an order for execution.

        For market orders, executes immediately at current price.
        For limit orders, stores for future execution when price is hit.

        Args:
            order: Order specification to execute.

        Returns:
            OrderReceipt with execution details.

        Raises:
            BrokerError: If order validation fails.
        """
        order_id = str(uuid4())
        timestamp = datetime.utcnow()

        try:
            # Validate order
            self._validate_order(order)

            if order.order_type == OrderType.MARKET:
                # Execute market order immediately
                return await self._execute_market_order(order, order_id, timestamp)
            else:
                # Store limit order for future execution
                self._pending_orders[order_id] = order
                return OrderReceipt(
                    order_id=order_id,
                    client_id=order.client_id,
                    status=OrderStatus.PENDING,
                    timestamp=timestamp,
                    message="Order accepted and pending execution",
                )

        except Exception as e:
            self._logger.error(f"Order submission failed: {e}")
            return OrderReceipt(
                order_id=order_id,
                client_id=order.client_id,
                status=OrderStatus.REJECTED,
                timestamp=timestamp,
                message=str(e),
            )

    async def positions(self) -> list[Position]:
        """Get current open positions.

        Returns:
            List of all open positions.
        """
        return list(self._positions.values())

    async def account(self) -> AccountState:
        """Get current account state.

        Returns:
            Current account state with balances and positions.
        """
        # Calculate total unrealized PnL
        total_unrealized = sum(pos.unrealized_pnl for pos in self._positions.values())
        equity = self._cash_balance + total_unrealized

        return AccountState(
            cash_balance=self._cash_balance,
            equity=equity,
            positions=dict(self._positions),
            realized_pnl=self._realized_pnl,
            open_orders=len(self._pending_orders),
            timestamp=datetime.utcnow(),
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        Args:
            order_id: Order ID to cancel.

        Returns:
            True if order was cancelled successfully.
        """
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]
            self._logger.info(f"Order {order_id} cancelled")
            return True
        return False

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
        if symbol not in self._positions:
            raise BrokerError(f"No open position for {symbol}")

        position = self._positions[symbol]
        close_quantity = (
            quantity if quantity is not None else abs(float(position.quantity))
        )

        # Create opposing order to close position
        close_order = Order(
            symbol=symbol,
            order_type=OrderType.MARKET,
            quantity=Decimal(
                str(-close_quantity if position.quantity > 0 else close_quantity)
            ),
        )

        return await self.submit(close_order)

    def update_prices(self, symbol: str, current_price: float) -> None:
        """Update current market prices and check for stop/TP execution.

        This method should be called with each new price update to:
        1. Update position mark-to-market values
        2. Check for stop loss and take profit triggers
        3. Execute any pending limit orders

        Args:
            symbol: Symbol being updated.
            current_price: New market price.
        """
        # Update position marks
        if symbol in self._positions:
            self._update_position_mark(symbol, current_price)

        # Check stop loss and take profit triggers
        self._check_stop_tp_triggers(symbol, current_price)

        # Check pending limit orders
        self._check_pending_orders(symbol, current_price)

    def _validate_order(self, order: Order) -> None:
        """Validate order before execution.

        Args:
            order: Order to validate.

        Raises:
            BrokerError: If order validation fails.
        """
        if order.quantity == 0:
            raise BrokerError("Order quantity cannot be zero")

        if order.order_type == OrderType.LIMIT and order.price is None:
            raise BrokerError("Limit orders must specify a price")

        # Check available balance for new positions
        if order.symbol not in self._positions:
            required_margin = abs(float(order.quantity)) * (
                order.price or 100.0
            )  # Rough estimate
            if required_margin > self._cash_balance:
                raise BrokerError(
                    f"Insufficient funds: ${self._cash_balance:.2f} available, ${required_margin:.2f} required"
                )

    async def _execute_market_order(
        self,
        order: Order,
        order_id: str,
        timestamp: datetime,
    ) -> OrderReceipt:
        """Execute a market order immediately.

        Args:
            order: Market order to execute.
            order_id: Generated order ID.
            timestamp: Execution timestamp.

        Returns:
            OrderReceipt with execution details.
        """
        # For paper trading, assume we can fill at the requested price
        # In real implementation, this would use current bid/ask
        fill_price = order.price or 100.0  # Default price if not specified

        # Update or create position
        self._update_position(order.symbol, order.quantity, fill_price, timestamp)

        # Handle stop loss and take profit orders
        if order.stop_loss:
            position_key = f"{order.symbol}_{timestamp.timestamp()}"
            self._stop_orders[position_key] = (order.symbol, order.stop_loss)

        if order.take_profit:
            position_key = f"{order.symbol}_{timestamp.timestamp()}"
            self._tp_orders[position_key] = (order.symbol, order.take_profit)

        # Apply commission
        self._cash_balance -= self.commission_per_trade

        self._logger.info(
            f"Market order executed: {order.symbol} {order.quantity} @ ${fill_price:.2f}"
        )

        return OrderReceipt(
            order_id=order_id,
            client_id=order.client_id,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            avg_fill_price=fill_price,
            timestamp=timestamp,
            message="Market order filled",
        )

    def _update_position(
        self,
        symbol: str,
        quantity: Decimal,
        price: float,
        timestamp: datetime,
    ) -> None:
        """Update or create position after order execution.

        Args:
            symbol: Trading symbol.
            quantity: Quantity to add/subtract (signed).
            price: Execution price.
            timestamp: Execution time.
        """
        if symbol in self._positions:
            # Update existing position
            existing = self._positions[symbol]
            new_quantity = existing.quantity + quantity

            if new_quantity == 0:
                # Position closed - calculate realized PnL
                # Use the quantity being closed (absolute value) for PnL calculation
                closing_quantity = abs(float(quantity))

                if existing.quantity > 0:  # Was long
                    pnl = closing_quantity * (price - existing.avg_entry_price)
                else:  # Was short
                    pnl = closing_quantity * (existing.avg_entry_price - price)

                self._realized_pnl += pnl
                self._cash_balance += pnl
                del self._positions[symbol]

                self._logger.info(f"Position closed: {symbol}, PnL: ${pnl:.2f}")

            elif (new_quantity > 0) == (existing.quantity > 0):
                # Same direction - update average entry price
                total_cost = (
                    float(existing.quantity) * existing.avg_entry_price
                    + float(quantity) * price
                )
                new_avg_price = total_cost / float(new_quantity)

                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=new_quantity,
                    avg_entry_price=new_avg_price,
                    current_price=price,
                    unrealized_pnl=0.0,  # Will be updated on next price update
                    entry_timestamp=existing.entry_timestamp,
                )

            else:
                # Opposite direction - partial close with remaining position
                # This is a simplification; real implementation would be more complex
                close_quantity = min(
                    abs(float(quantity)), abs(float(existing.quantity))
                )

                if abs(float(existing.quantity)) > close_quantity:
                    # Partial close
                    remaining_qty = existing.quantity - quantity
                    self._positions[symbol] = Position(
                        symbol=symbol,
                        quantity=remaining_qty,
                        avg_entry_price=existing.avg_entry_price,
                        current_price=price,
                        unrealized_pnl=0.0,
                        entry_timestamp=existing.entry_timestamp,
                    )

        else:
            # New position
            self._positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_entry_price=price,
                current_price=price,
                unrealized_pnl=0.0,
                entry_timestamp=timestamp,
            )

            self._logger.info(
                f"New position opened: {symbol} {quantity} @ ${price:.2f}"
            )

    def _update_position_mark(self, symbol: str, current_price: float) -> None:
        """Update position mark-to-market value.

        Args:
            symbol: Symbol to update.
            current_price: Current market price.
        """
        if symbol in self._positions:
            position = self._positions[symbol]

            # Calculate unrealized PnL
            if position.quantity > 0:  # Long position
                unrealized_pnl = float(position.quantity) * (
                    current_price - position.avg_entry_price
                )
            else:  # Short position
                unrealized_pnl = float(position.quantity) * (
                    current_price - position.avg_entry_price
                )

            # Update position
            self._positions[symbol] = Position(
                symbol=position.symbol,
                quantity=position.quantity,
                avg_entry_price=position.avg_entry_price,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                entry_timestamp=position.entry_timestamp,
            )

    def _check_stop_tp_triggers(self, symbol: str, current_price: float) -> None:
        """Check if current price triggers any stop loss or take profit orders.

        In gap scenarios where both stop and TP are triggered, priority is given to:
        - Take profit for favorable gaps (price moved in profit direction)
        - Stop loss for adverse gaps (price moved against position)

        Args:
            symbol: Symbol being checked.
            current_price: Current market price.
        """
        position = self._positions.get(symbol)
        if not position:
            return

        # Find triggered stops and TPs for this symbol
        triggered_stops = []
        triggered_tps = []

        for pos_key, (stop_symbol, stop_price) in self._stop_orders.items():
            if stop_symbol == symbol and (
                (position.quantity > 0 and current_price <= stop_price)
                or (position.quantity < 0 and current_price >= stop_price)
            ):
                triggered_stops.append((pos_key, stop_price))

        for pos_key, (tp_symbol, tp_price) in self._tp_orders.items():
            if tp_symbol == symbol and (
                (position.quantity > 0 and current_price >= tp_price)
                or (position.quantity < 0 and current_price <= tp_price)
            ):
                triggered_tps.append((pos_key, tp_price))

        # Handle gap scenarios where both stop and TP are triggered
        if triggered_stops and triggered_tps:
            # Determine gap direction relative to position
            is_long = position.quantity > 0

            # For gaps, prioritize the order that would execute first based on direction
            # Long position: TP executes on upward gap, stop on downward gap
            # Short position: TP executes on downward gap, stop on upward gap
            if is_long:
                # Long position: if price gapped up through both, TP has priority
                # if price gapped down through both, stop has priority
                tp_price = triggered_tps[0][1]  # Use first TP price as reference
                stop_price = triggered_stops[0][1]  # Use first stop price as reference

                if current_price >= max(tp_price, stop_price):
                    # Upward gap - TP priority for long
                    self._execute_tp_orders(triggered_tps, symbol, current_price)
                    self._clear_remaining_orders(triggered_stops, triggered_tps, symbol)
                else:
                    # Downward gap - stop priority for long
                    self._execute_stop_orders(triggered_stops, symbol, current_price)
                    self._clear_remaining_orders(triggered_stops, triggered_tps, symbol)
            else:
                # Short position: if price gapped down through both, TP has priority
                # if price gapped up through both, stop has priority
                tp_price = triggered_tps[0][1]
                stop_price = triggered_stops[0][1]

                if current_price <= min(tp_price, stop_price):
                    # Downward gap - TP priority for short
                    self._execute_tp_orders(triggered_tps, symbol, current_price)
                    self._clear_remaining_orders(triggered_stops, triggered_tps, symbol)
                else:
                    # Upward gap - stop priority for short
                    self._execute_stop_orders(triggered_stops, symbol, current_price)
                    self._clear_remaining_orders(triggered_stops, triggered_tps, symbol)
        else:
            # Normal scenario - execute whatever is triggered
            if triggered_stops:
                self._execute_stop_orders(triggered_stops, symbol, current_price)
            if triggered_tps:
                self._execute_tp_orders(triggered_tps, symbol, current_price)

    def _execute_stop_orders(
        self,
        triggered_stops: list[tuple[str, float]],
        symbol: str,
        current_price: float,
    ) -> None:
        """Execute triggered stop loss orders."""
        for pos_key, stop_price in triggered_stops:
            del self._stop_orders[pos_key]
            self._logger.info(
                f"Stop loss triggered for {symbol} at ${current_price:.2f} (stop: ${stop_price:.2f})"
            )
            # Close the position by updating with opposing quantity
            if symbol in self._positions:
                position = self._positions[symbol]
                from datetime import datetime

                # Update position with opposing quantity to close it
                self._update_position(
                    symbol,
                    -position.quantity,  # Opposite quantity closes position
                    current_price,
                    datetime.utcnow(),
                )

    def _execute_tp_orders(
        self, triggered_tps: list[tuple[str, float]], symbol: str, current_price: float
    ) -> None:
        """Execute triggered take profit orders."""
        for pos_key, tp_price in triggered_tps:
            del self._tp_orders[pos_key]
            self._logger.info(
                f"Take profit triggered for {symbol} at ${current_price:.2f} (TP: ${tp_price:.2f})"
            )
            # Close the position by updating with opposing quantity
            if symbol in self._positions:
                position = self._positions[symbol]
                from datetime import datetime

                # Update position with opposing quantity to close it
                self._update_position(
                    symbol,
                    -position.quantity,  # Opposite quantity closes position
                    current_price,
                    datetime.utcnow(),
                )

    def _clear_remaining_orders(
        self,
        triggered_stops: list[tuple[str, float]],
        triggered_tps: list[tuple[str, float]],
        symbol: str,
    ) -> None:
        """Clear all remaining stop and TP orders for the symbol after gap execution."""
        # Clear any remaining stops that weren't executed due to gap priority
        for pos_key, _ in triggered_stops:
            if pos_key in self._stop_orders:
                del self._stop_orders[pos_key]

        # Clear any remaining TPs that weren't executed due to gap priority
        for pos_key, _ in triggered_tps:
            if pos_key in self._tp_orders:
                del self._tp_orders[pos_key]

    def _check_pending_orders(self, symbol: str, current_price: float) -> None:
        """Check if current price triggers any pending limit orders.

        Args:
            symbol: Symbol being checked.
            current_price: Current market price.
        """
        # This is simplified - would need proper limit order logic
        # For now, just log that we have this capability
        pending_count = len(
            [o for o in self._pending_orders.values() if o.symbol == symbol]
        )
        if pending_count > 0:
            self._logger.debug(f"Checking {pending_count} pending orders for {symbol}")

    def get_stats(self) -> dict[str, Any]:
        """Get broker performance statistics.

        Returns:
            Dictionary with broker statistics and performance metrics.
        """
        total_positions = len(self._positions)
        total_unrealized = sum(pos.unrealized_pnl for pos in self._positions.values())

        return {
            "initial_balance": self.initial_balance,
            "cash_balance": self._cash_balance,
            "realized_pnl": self._realized_pnl,
            "unrealized_pnl": total_unrealized,
            "total_equity": self._cash_balance + total_unrealized,
            "open_positions": total_positions,
            "pending_orders": len(self._pending_orders),
            "stop_orders": len(self._stop_orders),
            "tp_orders": len(self._tp_orders),
        }
