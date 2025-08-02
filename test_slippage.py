#!/usr/bin/env python3
"""
Test script for slippage implementation in MockPaperBroker.

This script tests both entry and exit slippage to ensure realistic
execution costs are properly simulated in backtests.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.entities import Candle
from core.strategy.factory import MockPaperBroker, TradingSignal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MockConfig:
    """Mock configuration for testing slippage."""

    class Account:
        initial_balance: float = 10000.0
        commission: float = 0.0  # No commission for cleaner slippage testing

    class Execution:
        class Slippage:
            entry_pct: float = 0.001  # 0.1% entry slippage
            exit_pct: float = 0.002  # 0.2% exit slippage

        slippage = Slippage()

    account = Account()
    execution = Execution()


def test_slippage():
    """Test entry and exit slippage calculations."""

    logger.info("🧪 Testing slippage implementation")

    # Create mock broker with slippage
    config = MockConfig()
    broker = MockPaperBroker(config)

    # Test parameters
    entry_price = 100.0
    size = 50.0  # Position value = 50 * 100 = $5000 (well under 80% limit of $8000)

    # Create a buy signal
    signal = TradingSignal(
        symbol="BTCUSDT",
        side="buy",
        entry_price=entry_price,
        stop_loss=95.0,
        take_profit=110.0,
        size=size,
        timestamp=datetime.now(),
        reason="test_signal",
    )

    logger.info(
        f"📊 Original signal: entry=${entry_price}, stop=${signal.stop_loss}, tp=${signal.take_profit}"
    )

    # Submit order (should apply entry slippage)
    trade_id = broker.submit_order(signal, size)

    if not trade_id:
        logger.error("❌ Trade was rejected!")
        return

    # Get the trade record
    trade = broker.positions[trade_id]

    # Expected entry slippage: 0.1% worse for buy = 100.0 * 1.001 = 100.1
    expected_entry_slipped = entry_price * (1 + config.execution.slippage.entry_pct)
    actual_entry_slipped = trade["entry_price"]

    logger.info("📈 Entry slippage:")
    logger.info(f"   Expected slipped entry: ${expected_entry_slipped:.2f}")
    logger.info(f"   Actual slipped entry:   ${actual_entry_slipped:.2f}")
    logger.info(f"   Entry slippage cost:    ${trade['entry_slippage']:.4f}")

    # Test exit slippage by simulating take profit hit
    exit_market_price = 110.0  # Take profit level

    # Create candle at TP level to trigger exit
    candle = Candle(
        ts=datetime.now(),
        open=109.0,
        high=111.0,
        low=108.0,
        close=exit_market_price,
        volume=1000.0,
    )

    # Update positions (should trigger TP and apply exit slippage)
    broker.update_positions(candle)

    # Find the closed trade
    closed_trade = None
    for t in broker.trades:
        if t["id"] == trade_id and t["status"] == "take_profit":
            closed_trade = t
            break

    if not closed_trade:
        logger.error("❌ Trade was not closed as expected!")
        return

    # Expected exit slippage: 0.2% worse for sell = 110.0 * (1 - 0.002) = 109.78
    expected_exit_slipped = exit_market_price * (1 - config.execution.slippage.exit_pct)
    actual_exit_slipped = closed_trade["exit_price"]

    logger.info("📉 Exit slippage:")
    logger.info(f"   Market exit price:      ${exit_market_price:.2f}")
    logger.info(f"   Expected slipped exit:  ${expected_exit_slipped:.2f}")
    logger.info(f"   Actual slipped exit:    ${actual_exit_slipped:.2f}")
    logger.info(f"   Exit slippage cost:     ${closed_trade['exit_slippage']:.4f}")

    # Calculate PnL impact
    # Perfect execution PnL: (110.0 - 100.0) * 50 units = $10 * 50 = $500
    perfect_pnl = (exit_market_price - entry_price) * size

    # Actual PnL with slippage: (109.78 - 100.10) * 50 = $9.68 * 50 = $484
    actual_pnl = closed_trade["pnl"]

    # Total slippage cost in dollar terms
    entry_slippage_cost = closed_trade.get("entry_slippage", 0) * size  # 0.10 * 50 = $5
    exit_slippage_cost = (
        closed_trade.get("exit_slippage", 0) * size
    )  # -0.22 * 50 = -$11
    total_slippage_cost_dollars = (
        entry_slippage_cost + exit_slippage_cost
    )  # $5 + (-$11) = -$6

    logger.info("💰 PnL Analysis:")
    logger.info(f"   Perfect execution PnL:    ${perfect_pnl:.2f}")
    logger.info(f"   Actual PnL with slippage: ${actual_pnl:.2f}")
    logger.info(f"   Entry slippage cost:      ${entry_slippage_cost:.2f}")
    logger.info(f"   Exit slippage cost:       ${exit_slippage_cost:.2f}")
    logger.info(f"   Total slippage impact:    ${total_slippage_cost_dollars:.2f}")
    logger.info(
        f"   PnL reduction:            ${perfect_pnl - actual_pnl:.2f} ({((perfect_pnl - actual_pnl) / perfect_pnl * 100):.2f}%)"
    )

    # Verify calculations
    entry_tolerance = 0.001
    exit_tolerance = 0.001

    entry_correct = abs(actual_entry_slipped - expected_entry_slipped) < entry_tolerance
    exit_correct = abs(actual_exit_slipped - expected_exit_slipped) < exit_tolerance

    if entry_correct and exit_correct:
        logger.info("✅ Slippage implementation working correctly!")
    else:
        logger.error("❌ Slippage calculations are incorrect!")
        if not entry_correct:
            logger.error(
                f"   Entry slippage error: expected {expected_entry_slipped}, got {actual_entry_slipped}"
            )
        if not exit_correct:
            logger.error(
                f"   Exit slippage error: expected {expected_exit_slipped}, got {actual_exit_slipped}"
            )


def test_zero_slippage():
    """Test that zero slippage works correctly."""

    logger.info("\n🧪 Testing zero slippage mode")

    @dataclass
    class ZeroSlippageConfig:
        class Account:
            initial_balance: float = 10000.0
            commission: float = 0.0

        class Execution:
            class Slippage:
                entry_pct: float = 0.0
                exit_pct: float = 0.0

            slippage = Slippage()

        account = Account()
        execution = Execution()

    config = ZeroSlippageConfig()
    broker = MockPaperBroker(config)

    entry_price = 100.0
    signal = TradingSignal(
        symbol="BTCUSDT",
        side="buy",
        entry_price=entry_price,
        stop_loss=95.0,
        take_profit=105.0,
        size=50.0,  # Position value = 50 * 100 = $5000
        timestamp=datetime.now(),
        reason="zero_slippage_test",
    )

    trade_id = broker.submit_order(signal, 50.0)
    trade = broker.positions[trade_id]

    # With zero slippage, entry price should be unchanged
    if abs(trade["entry_price"] - entry_price) < 0.0001:
        logger.info("✅ Zero slippage working correctly!")
    else:
        logger.error(
            f"❌ Zero slippage failed: expected {entry_price}, got {trade['entry_price']}"
        )


if __name__ == "__main__":
    test_slippage()
    test_zero_slippage()
    logger.info("\n🎯 Slippage testing complete!")
