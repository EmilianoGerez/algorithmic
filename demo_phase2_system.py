#!/usr/bin/env python3
"""
Phase 2 Core System Demonstration

This demo showcases the complete Phase 2 implementation including:
- Data integration and adapters
- Risk management system
- Backtesting engine
- Multi-symbol data feeds
- Portfolio management
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import (  # Data models; Data integration; Strategy system; Risk management; Backtesting
    BacktestConfig,
    BacktestDataFeed,
    BacktestRunner,
    Candle,
    CoreBacktestEngine,
    DataAdapterFactory,
    FVGStrategy,
    MarketData,
    MultiSymbolDataFeed,
    PositionSizer,
    RiskLimits,
    RiskManager,
    Signal,
    SignalDirection,
    SignalType,
    TimeFrame,
    create_fvg_strategy_config,
)


def create_sample_market_data(symbol: str, days: int = 30) -> MarketData:
    """Create sample market data for demonstration"""
    market_data = MarketData(
        symbol=symbol,
        timeframe=TimeFrame.MINUTE_15,
        metadata={"source": "demo", "generated": True},
    )

    base_price = Decimal("100.00")
    base_time = datetime.now() - timedelta(days=days)

    for i in range(days * 24 * 4):  # 15-minute intervals
        timestamp = base_time + timedelta(minutes=i * 15)

        # Simple price movement simulation
        price_change = Decimal("0.1") if i % 10 < 5 else Decimal("-0.1")
        base_price += price_change

        # Ensure high >= low
        open_price = base_price
        close_price = base_price + (Decimal("0.05") if i % 3 == 0 else Decimal("-0.05"))
        high_price = max(open_price, close_price) + Decimal("0.02")
        low_price = min(open_price, close_price) - Decimal("0.02")

        candle = Candle(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=Decimal("1000"),
            symbol=symbol,
            timeframe=TimeFrame.MINUTE_15,
        )

        market_data.add_candle(candle)

    return market_data


def demo_data_adapters():
    """Demonstrate data adapter system"""
    print("🔌 Data Adapters Demo")
    print("=" * 50)

    # Create different adapters
    try:
        yahoo_adapter = DataAdapterFactory.create_adapter("yahoo")
        print("✅ Yahoo Finance adapter created")
    except Exception as e:
        print(f"❌ Yahoo Finance adapter failed: {e}")

    try:
        backtrader_adapter = DataAdapterFactory.create_adapter("backtrader")
        print("✅ Backtrader adapter created")
    except Exception as e:
        print(f"❌ Backtrader adapter failed: {e}")

    try:
        alpaca_adapter = DataAdapterFactory.create_adapter(
            "alpaca", api_key="demo_key", secret_key="demo_secret"
        )
        print("✅ Alpaca adapter created")
    except Exception as e:
        print(f"❌ Alpaca adapter failed: {e}")

    # Show available adapters
    available = DataAdapterFactory.get_available_adapters()
    print(f"📊 Available adapters: {', '.join(available)}")
    print()


def demo_risk_management():
    """Demonstrate risk management system"""
    print("🛡️ Risk Management Demo")
    print("=" * 50)

    # Create risk limits
    risk_limits = RiskLimits(
        max_position_size=Decimal("0.1"),  # 10% max position
        max_daily_loss=Decimal("0.05"),  # 5% daily loss limit
        max_drawdown=Decimal("0.15"),  # 15% max drawdown
        max_positions=5,
    )

    # Create risk manager
    from core.risk import FixedRiskPositionSizer

    position_sizer = FixedRiskPositionSizer(risk_per_trade=0.02)

    risk_manager = RiskManager(
        risk_limits=risk_limits,
        position_sizer=position_sizer,
        initial_capital=Decimal("100000"),
    )

    print(f"💰 Initial capital: ${risk_manager.initial_capital:,.2f}")
    print(f"📊 Max position size: {risk_limits.max_position_size * 100}%")
    print(f"🚨 Max daily loss: {risk_limits.max_daily_loss * 100}%")
    print(f"📈 Max drawdown: {risk_limits.max_drawdown * 100}%")

    # Create a test signal
    test_signal = Signal(
        timestamp=datetime.now(),
        symbol="AAPL",
        direction=SignalDirection.LONG,
        signal_type=SignalType.ENTRY,
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("145.00"),
        take_profit=Decimal("160.00"),
        confidence=0.9,
        strength=0.8,
        strategy_name="FVG",
    )

    # Evaluate signal
    assessment = risk_manager.evaluate_signal(test_signal)
    print(f"\n🎯 Signal Assessment:")
    print(f"   Approved: {assessment['approved']}")
    print(f"   Position size: {assessment['position_size']:.2f} shares")
    print(f"   Risk amount: ${assessment.get('risk_amount', 0):.2f}")

    if assessment["approved"]:
        # Add position
        position = risk_manager.add_position(test_signal, assessment["position_size"])
        print(f"   Position added: {position.symbol} - {position.quantity} shares")

        # Show portfolio summary
        summary = risk_manager.get_portfolio_summary()
        print(f"\n📊 Portfolio Summary:")
        print(f"   Total value: ${summary['total_value']:,.2f}")
        print(f"   Available cash: ${summary['available_cash']:,.2f}")
        print(f"   Active positions: {summary['active_positions']}")

    print()


def demo_backtesting_engine():
    """Demonstrate backtesting engine"""
    print("🔄 Backtesting Engine Demo")
    print("=" * 50)

    # Create sample data
    market_data = create_sample_market_data("AAPL", days=10)
    print(f"📊 Created sample data: {len(market_data.candles)} candles")

    # Create data adapter and backtest runner
    backtrader_adapter = DataAdapterFactory.create_adapter("backtrader")
    backtest_runner = BacktestRunner(backtrader_adapter)

    # Create strategy
    config = create_fvg_strategy_config(
        symbol="AAPL",
        timeframes=[TimeFrame.MINUTE_15],
        confidence_threshold=0.8,
    )
    strategy = FVGStrategy(config)

    # Run backtest
    result = backtest_runner.core_engine.run_backtest(
        strategy=strategy,
        market_data=market_data,
        config=BacktestConfig(
            start_date=datetime.now() - timedelta(days=10),
            end_date=datetime.now(),
            initial_capital=Decimal("100000"),
        ),
    )

    print(f"\n📈 Backtest Results:")
    print(f"   Strategy: {result.strategy_name}")
    print(f"   Symbol: {result.symbol}")
    print(f"   Initial capital: ${result.initial_capital:,.2f}")
    print(f"   Final capital: ${result.final_capital:,.2f}")
    print(f"   Total return: {result.calculate_return_percentage():.2f}%")
    print(f"   Total trades: {result.total_trades}")
    print(f"   Win rate: {result.calculate_win_rate():.1f}%")
    print(f"   Max drawdown: {result.max_drawdown}")
    print(f"   Signals generated: {len(result.signals)}")

    print()


def demo_multi_symbol_feed():
    """Demonstrate multi-symbol data feed"""
    print("📡 Multi-Symbol Data Feed Demo")
    print("=" * 50)

    # Create adapter
    adapter = DataAdapterFactory.create_adapter("backtrader")

    # Create multi-symbol feed
    multi_feed = MultiSymbolDataFeed(adapter)

    # Add symbols
    symbols = ["AAPL", "GOOGL", "MSFT"]
    timeframes = [TimeFrame.MINUTE_15, TimeFrame.HOUR_1]

    for symbol in symbols:
        multi_feed.add_symbol(symbol, timeframes)
        print(f"➕ Added {symbol} with timeframes: {[tf.value for tf in timeframes]}")

    # Create market data collection for backtest
    market_data_collection = {}
    for symbol in symbols:
        market_data_collection[symbol] = create_sample_market_data(symbol, days=5)

    # Set up signal receiver
    received_signals = []

    def on_candle_received(candle):
        received_signals.append(candle)
        if len(received_signals) <= 5:  # Show first 5 only
            print(
                f"📊 Received: {candle.symbol} - {candle.timestamp} - Close: ${candle.close}"
            )

    # Subscribe to feed
    multi_feed.subscribe(on_candle_received)

    # Start backtest feed
    multi_feed.start_backtest(market_data_collection)

    print(f"\n📈 Total candles received: {len(received_signals)}")
    print(f"🎯 Symbols processed: {len(set(c.symbol for c in received_signals))}")

    # Stop feed
    multi_feed.stop()
    print()


def demo_portfolio_management():
    """Demonstrate portfolio management features"""
    print("💼 Portfolio Management Demo")
    print("=" * 50)

    # Create risk manager with multiple position sizers
    risk_limits = RiskLimits(max_positions=3, max_position_size=Decimal("0.15"))

    # Test different position sizers
    from core.risk import FixedRiskPositionSizer, VolatilityPositionSizer

    sizers = [
        ("Fixed Risk", FixedRiskPositionSizer(0.02)),
        ("Volatility", VolatilityPositionSizer(0.02, 2.0)),
    ]

    for sizer_name, sizer in sizers:
        print(f"\n📊 {sizer_name} Position Sizing:")

        risk_manager = RiskManager(
            risk_limits=risk_limits,
            position_sizer=sizer,
            initial_capital=Decimal("100000"),
        )

        # Test signals with different characteristics
        test_signals = [
            Signal(
                timestamp=datetime.now(),
                symbol="AAPL",
                direction=SignalDirection.LONG,
                signal_type=SignalType.ENTRY,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                confidence=0.9,
                metadata={"atr": 2.5},
            ),
            Signal(
                timestamp=datetime.now(),
                symbol="GOOGL",
                direction=SignalDirection.SHORT,
                signal_type=SignalType.ENTRY,
                entry_price=Decimal("120.00"),
                stop_loss=Decimal("125.00"),
                confidence=0.8,
                metadata={"atr": 3.0},
            ),
        ]

        for signal in test_signals:
            assessment = risk_manager.evaluate_signal(signal)
            print(
                f"   {signal.symbol}: {assessment['position_size']:.2f} shares (${assessment.get('risk_amount', 0):.2f} risk)"
            )

    print()


def main():
    """Main demonstration function"""
    print("🚀 Phase 2 Core System Demonstration")
    print("=" * 60)
    print("This demo showcases the complete Phase 2 implementation:")
    print("- Data integration and adapters")
    print("- Risk management system")
    print("- Backtesting engine")
    print("- Multi-symbol data feeds")
    print("- Portfolio management")
    print("=" * 60)
    print()

    try:
        # Run all demos
        demo_data_adapters()
        demo_risk_management()
        demo_backtesting_engine()
        demo_multi_symbol_feed()
        demo_portfolio_management()

        print("🎉 Phase 2 System Features:")
        print("  ✅ Data Integration - Multiple adapters for different data sources")
        print(
            "  ✅ Risk Management - Position sizing, portfolio limits, drawdown control"
        )
        print(
            "  ✅ Backtesting Engine - Comprehensive backtesting with risk integration"
        )
        print("  ✅ Multi-Symbol Feeds - Live and backtest data feeds")
        print("  ✅ Portfolio Management - Multiple position sizing algorithms")
        print()
        print("✅ All Phase 2 demonstrations completed successfully!")

    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
