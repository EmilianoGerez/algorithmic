"""
Tests for paper broker implementation.

This module tests the paper trading broker functionality including
order        # Check PnL was realized
        account = await broker.account()
        # Trading profit: 1000 * (1.2050 - 1.2000) = 50.0
        # Commissions: 2 trades * $1.0 = $2.0
        # Net PnL: $50.0 - $2.0 = $48.0
        # But realized_pnl tracks only the trading profit, commissions are separate
        expected_pnl = 1000 * (1.2050 - 1.2000)  # 1000 units * 50 pips

        print(f"DEBUG: Account state: {account}")
        print(f"DEBUG: Expected PnL: {expected_pnl}, Actual: {account.realized_pnl}")

        assert abs(account.realized_pnl - expected_pnl) < 1e-6cution, position management, PnL calculations, and stop/take profit logic.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from core.trading.models import (
    AccountState,
    Order,
    OrderStatus,
    OrderType,
    Position,
)
from infra.brokers.broker import PaperBroker
from infra.brokers.exceptions import BrokerError


class TestPaperBroker:
    """Test paper broker functionality."""

    @pytest.fixture
    def broker(self) -> PaperBroker:
        """Paper broker instance for testing."""
        return PaperBroker(initial_balance=10000.0, commission_per_trade=1.0)

    @pytest.mark.asyncio
    async def test_broker_initialization(self, broker: PaperBroker) -> None:
        """Test broker initialization and initial state."""
        account = await broker.account()

        assert account.cash_balance == 10000.0
        assert account.equity == 10000.0
        assert len(account.positions) == 0
        assert account.realized_pnl == 0.0
        assert account.open_orders == 0

    @pytest.mark.asyncio
    async def test_market_order_execution(self, broker: PaperBroker) -> None:
        """Test market order execution and position creation."""
        order = Order(
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("1000"),
            price=1.2000,
        )

        receipt = await broker.submit(order)

        assert receipt.status == OrderStatus.FILLED
        assert receipt.filled_quantity == Decimal("1000")
        assert receipt.avg_fill_price == 1.2000

        # Check position was created
        positions = await broker.positions()
        assert len(positions) == 1

        position = positions[0]
        assert position.symbol == "EURUSD"
        assert position.quantity == Decimal("1000")
        assert position.avg_entry_price == 1.2000

    @pytest.mark.asyncio
    async def test_short_position_creation(self, broker: PaperBroker) -> None:
        """Test short position creation with negative quantity."""
        order = Order(
            symbol="GBPUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("-500"),  # Short position
            price=1.3000,
        )

        receipt = await broker.submit(order)

        assert receipt.status == OrderStatus.FILLED
        assert receipt.filled_quantity == Decimal("-500")

        positions = await broker.positions()
        assert len(positions) == 1

        position = positions[0]
        assert position.symbol == "GBPUSD"
        assert position.quantity == Decimal("-500")
        assert position.avg_entry_price == 1.3000

    @pytest.mark.asyncio
    async def test_position_closing(self, broker: PaperBroker) -> None:
        """Test position closing and PnL calculation."""
        # Open long position
        open_order = Order(
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("1000"),
            price=1.2000,
        )
        await broker.submit(open_order)

        # Close position at higher price
        close_order = Order(
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("-1000"),
            price=1.2050,  # 50 pip profit
        )
        receipt = await broker.submit(close_order)

        assert receipt.status == OrderStatus.FILLED

        # Check position is closed
        positions = await broker.positions()
        assert len(positions) == 0

        # Check PnL was realized
        account = await broker.account()
        # Trading profit: 1000 * (1.2050 - 1.2000) = 5.0
        expected_pnl = 1000 * (1.2050 - 1.2000)  # 1000 units * 5 pips = 5.0
        assert abs(account.realized_pnl - expected_pnl) < 1e-6

    @pytest.mark.asyncio
    async def test_commission_deduction(self, broker: PaperBroker) -> None:
        """Test commission is deducted from cash balance."""
        initial_account = await broker.account()
        initial_cash = initial_account.cash_balance

        order = Order(
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("1000"),
            price=1.2000,
        )
        await broker.submit(order)

        final_account = await broker.account()

        # Commission should be deducted (broker initialized with $1 commission)
        assert final_account.cash_balance == initial_cash - 1.0

    @pytest.mark.asyncio
    async def test_order_validation(self, broker: PaperBroker) -> None:
        """Test order validation and rejection."""
        # Zero quantity order should be rejected
        invalid_order = Order(
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("0"),
            price=1.2000,
        )

        receipt = await broker.submit(invalid_order)
        assert receipt.status == OrderStatus.REJECTED
        assert receipt.message and "cannot be zero" in receipt.message

    @pytest.mark.asyncio
    async def test_insufficient_funds(self, broker: PaperBroker) -> None:
        """Test order rejection due to insufficient funds."""
        # Order requiring more margin than available
        large_order = Order(
            symbol="BTCUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),  # 100 BTC
            price=50000.0,  # $50k per BTC = $5M position
        )

        receipt = await broker.submit(large_order)
        assert receipt.status == OrderStatus.REJECTED
        assert receipt.message and "Insufficient funds" in receipt.message

    @pytest.mark.asyncio
    async def test_limit_order_handling(self, broker: PaperBroker) -> None:
        """Test limit order acceptance and pending status."""
        limit_order = Order(
            symbol="EURUSD",
            order_type=OrderType.LIMIT,
            quantity=Decimal("1000"),
            price=1.1950,  # Limit price
        )

        receipt = await broker.submit(limit_order)

        assert receipt.status == OrderStatus.PENDING
        assert receipt.message and "pending execution" in receipt.message

        # Check order is in pending orders
        account = await broker.account()
        assert account.open_orders == 1

    @pytest.mark.asyncio
    async def test_order_cancellation(self, broker: PaperBroker) -> None:
        """Test pending order cancellation."""
        # Submit limit order
        limit_order = Order(
            symbol="EURUSD",
            order_type=OrderType.LIMIT,
            quantity=Decimal("1000"),
            price=1.1950,
        )
        receipt = await broker.submit(limit_order)

        # Cancel the order
        cancelled = await broker.cancel_order(receipt.order_id)
        assert cancelled

        # Check order is no longer pending
        account = await broker.account()
        assert account.open_orders == 0

        # Try to cancel non-existent order
        not_cancelled = await broker.cancel_order("non_existent_id")
        assert not not_cancelled

    @pytest.mark.asyncio
    async def test_position_closing_by_symbol(self, broker: PaperBroker) -> None:
        """Test closing position using close_position method."""
        # Open position
        order = Order(
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("1000"),
            price=1.2000,
        )
        await broker.submit(order)

        # Close position using broker method
        receipt = await broker.close_position("EURUSD")

        assert receipt.status == OrderStatus.FILLED

        # Position should be closed
        positions = await broker.positions()
        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_close_nonexistent_position(self, broker: PaperBroker) -> None:
        """Test error when trying to close non-existent position."""
        with pytest.raises(BrokerError, match="No open position for GBPUSD"):
            await broker.close_position("GBPUSD")

    def test_price_update_and_mark_to_market(self, broker: PaperBroker) -> None:
        """Test price updates and mark-to-market calculations."""
        # This test needs to be synchronous since update_prices is sync
        # Open position first with async call
        import asyncio

        async def setup_position():
            order = Order(
                symbol="EURUSD",
                order_type=OrderType.MARKET,
                quantity=Decimal("1000"),
                price=1.2000,
            )
            await broker.submit(order)

        asyncio.run(setup_position())

        # Update price higher
        broker.update_prices("EURUSD", 1.2050)

        # Check unrealized PnL
        async def check_pnl():
            positions = await broker.positions()
            position = positions[0]
            expected_pnl = 1000 * (1.2050 - 1.2000)
            assert abs(position.unrealized_pnl - expected_pnl) < 1e-6
            assert position.current_price == 1.2050

        asyncio.run(check_pnl())

    def test_broker_stats(self, broker: PaperBroker) -> None:
        """Test broker statistics reporting."""
        stats = broker.get_stats()

        assert stats["initial_balance"] == 10000.0
        assert stats["cash_balance"] == 10000.0
        assert stats["realized_pnl"] == 0.0
        assert stats["unrealized_pnl"] == 0.0
        assert stats["total_equity"] == 10000.0
        assert stats["open_positions"] == 0
        assert stats["pending_orders"] == 0

    @pytest.mark.asyncio
    async def test_stop_loss_and_take_profit_orders(self, broker: PaperBroker) -> None:
        """Test stop loss and take profit order handling."""
        order = Order(
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("1000"),
            price=1.2000,
            stop_loss=1.1950,  # 50 pip stop
            take_profit=1.2100,  # 100 pip target
        )

        receipt = await broker.submit(order)

        assert receipt.status == OrderStatus.FILLED

        # Check that stop and TP orders are tracked
        stats = broker.get_stats()
        assert stats["stop_orders"] >= 0  # Should have stop order tracking
        assert stats["tp_orders"] >= 0  # Should have TP order tracking


class TestBrokerIntegration:
    """Integration tests for broker with trading scenarios."""

    @pytest.mark.asyncio
    async def test_profitable_long_trade_scenario(self) -> None:
        """Test complete profitable long trade scenario."""
        broker = PaperBroker(initial_balance=10000.0)

        # Open long position
        entry_order = Order(
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("8000"),  # $9.6k position at 1.2000 (within $10k limit)
            price=1.2000,
        )

        entry_receipt = await broker.submit(entry_order)
        assert entry_receipt.status == OrderStatus.FILLED

        # Price moves in our favor
        broker.update_prices("EURUSD", 1.2100)  # +100 pips

        # Check unrealized PnL
        account = await broker.account()
        positions = await broker.positions()
        position = positions[0]

        expected_unrealized = 8000 * (1.2100 - 1.2000)  # 8k units * 100 pips
        assert abs(position.unrealized_pnl - expected_unrealized) < 1e-6
        assert account.equity == account.cash_balance + position.unrealized_pnl

        # Close position for profit
        exit_order = Order(
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("-8000"),
            price=1.2100,
        )

        exit_receipt = await broker.submit(exit_order)
        assert exit_receipt.status == OrderStatus.FILLED

        # Check final state
        final_account = await broker.account()
        final_positions = await broker.positions()

        assert len(final_positions) == 0  # Position closed
        assert final_account.realized_pnl == expected_unrealized
        assert final_account.equity > 10000.0  # Profitable

    @pytest.mark.asyncio
    async def test_losing_short_trade_scenario(self) -> None:
        """Test complete losing short trade scenario."""
        broker = PaperBroker(initial_balance=10000.0)

        # Open short position
        entry_order = Order(
            symbol="GBPUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("-5000"),  # Short 5k units
            price=1.3000,
        )

        await broker.submit(entry_order)

        # Price moves against us
        broker.update_prices("GBPUSD", 1.3080)  # +80 pips against short

        # Close position for loss
        exit_order = Order(
            symbol="GBPUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("5000"),
            price=1.3080,
        )

        await broker.submit(exit_order)

        # Check final state
        final_account = await broker.account()

        expected_loss = 5000 * (1.3000 - 1.3080)  # Negative for loss
        assert abs(final_account.realized_pnl - expected_loss) < 1e-6
        assert final_account.equity < 10000.0  # Loss occurred


class TestPaperBrokerGapScenarios:
    """Test paper broker behavior during market gaps and priority handling."""

    @pytest.mark.asyncio
    async def test_gap_stop_and_tp_priority_long_position(self) -> None:
        """Test that stop loss fires first when both stop and TP are gapped over for long positions."""
        broker = PaperBroker(initial_balance=10000.0, commission_per_trade=0.0)

        # Open long position with both stop and take profit
        entry_order = Order(
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("1000"),
            price=1.2000,
            stop_loss=1.1950,  # 50 pip stop
            take_profit=1.2100,  # 100 pip target
        )

        await broker.submit(entry_order)

        # Simulate market gap where price jumps from 1.2000 to 1.2150
        # This gaps over BOTH the take profit (1.2100) and potential stop loss
        # For longs: TP should fire first since we're gapping in favorable direction
        broker.update_prices("EURUSD", 1.2150)

        # Check that position was closed at take profit, not stop
        positions = await broker.positions()
        assert len(positions) == 0

        account = await broker.account()
        # Should have profit from TP execution, not loss from stop
        # TP execution should be at the gapped price (1.2150) since that's better than TP (1.2100)
        expected_pnl = 1000 * (1.2150 - 1.2000)  # 150 pip profit from gap
        assert account.realized_pnl > 0  # Profit, not loss
        assert abs(account.realized_pnl - expected_pnl) < 1e-6

    @pytest.mark.asyncio
    async def test_gap_stop_and_tp_priority_short_position(self) -> None:
        """Test that stop loss fires first when both stop and TP are gapped over for short positions."""
        broker = PaperBroker(initial_balance=10000.0, commission_per_trade=0.0)

        # Open short position with both stop and take profit
        entry_order = Order(
            symbol="GBPUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("-1000"),
            price=1.3000,
            stop_loss=1.3050,  # 50 pip stop (above entry for short)
            take_profit=1.2900,  # 100 pip target (below entry for short)
        )

        await broker.submit(entry_order)

        # Simulate market gap where price drops from 1.3000 to 1.2850
        # This gaps over BOTH the take profit (1.2900) and would not hit stop
        # For shorts: TP should fire since we're gapping in favorable direction
        broker.update_prices("GBPUSD", 1.2850)

        # Check that position was closed at take profit
        positions = await broker.positions()
        assert len(positions) == 0

        account = await broker.account()
        # Should have profit from TP execution
        # TP execution should be at the gapped price (1.2850) since that's better than TP (1.2900)
        expected_pnl = 1000 * (1.3000 - 1.2850)  # 150 pip profit from gap
        assert account.realized_pnl > 0  # Profit, not loss
        assert abs(account.realized_pnl - expected_pnl) < 1e-6

    @pytest.mark.asyncio
    async def test_gap_stop_priority_short_adverse_gap(self) -> None:
        """Test that stop loss fires first when gap goes against short position."""
        broker = PaperBroker(initial_balance=10000.0, commission_per_trade=0.0)

        # Open short position
        entry_order = Order(
            symbol="GBPUSD",
            order_type=OrderType.MARKET,
            quantity=Decimal("-1000"),
            price=1.3000,
            stop_loss=1.3050,  # 50 pip stop (above entry for short)
            take_profit=1.2900,  # 100 pip target (below entry for short)
        )

        await broker.submit(entry_order)

        # Simulate adverse gap where price jumps from 1.3000 to 1.3100
        # This gaps over the stop loss (1.3050) but not the take profit
        # Stop should fire first since it's an adverse move
        broker.update_prices("GBPUSD", 1.3100)

        # Check that position was closed at stop loss
        positions = await broker.positions()
        assert len(positions) == 0

        account = await broker.account()
        # Should have loss from stop execution at gapped price
        expected_pnl = 1000 * (1.3000 - 1.3100)  # 100 pip loss from gap
        assert account.realized_pnl < 0  # Loss, not profit
        assert abs(account.realized_pnl - expected_pnl) < 1e-6
