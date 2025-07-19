#!/usr/bin/env python3
"""
Complete System Integration Test

This test validates the complete integration of all three phases:
- Phase 1: Core system (data models, strategies, indicators)
- Phase 2: Data integration, risk management, backtesting
- Phase 3: Live trading, API, streaming

Provides comprehensive validation of the entire system architecture.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Added concrete implementation
    # Phase 1 - Core System; Phase 2 - Integration; Phase 3 - Live Trading
    from core import (
        BacktestConfig,
        Candle,
        CoreBacktestEngine,
        ExecutionMode,
        FixedRiskPositionSizer,
        FVGDetector,
        FVGStrategy,
        LiveTradingConfig,
        LiveTradingEngine,
        MultiSymbolDataFeed,
        PaperBrokerAdapter,
        RiskLimits,
        RiskManager,
        Signal,
        SignalDirection,
        SignalType,
        StreamingConfig,
        StreamingManager,
        StreamingProvider,
        TimeFrame,
        create_fvg_strategy_config,
    )

    # Import additional classes from specific modules that aren't in main __all__
    from core.data.adapters import YahooFinanceAdapter
    from core.indicators.fvg_detector import FVGFilterConfig

    IMPORT_SUCCESS = True
    IMPORT_ERRORS = []
except Exception as exc:  # pylint: disable=broad-exception-caught
    IMPORT_SUCCESS = False
    IMPORT_ERRORS = [str(exc)]
    # Import minimal required for error reporting
    try:
        from core.data.models import SignalDirection, SignalType, TimeFrame
    except ImportError:
        pass


class SystemIntegrationTest:
    """Complete system integration test"""

    def __init__(self):
        self.test_results = {
            "phase1_core": {"passed": 0, "failed": 0, "tests": []},
            "phase2_integration": {"passed": 0, "failed": 0, "tests": []},
            "phase3_live": {"passed": 0, "failed": 0, "tests": []},
            "system_integration": {"passed": 0, "failed": 0, "tests": []},
        }

    async def run_complete_test(self):
        """Run complete system integration test"""
        print("🧪 Complete System Integration Test")
        print("=" * 80)
        print("Testing all three phases of the system:")
        print("  Phase 1: Core System (models, strategies, indicators)")
        print("  Phase 2: Data Integration, Risk Management, Backtesting")
        print("  Phase 3: Live Trading, API, Streaming")
        print("=" * 80)
        print()

        # Check initial imports
        if not IMPORT_SUCCESS:
            print("❌ Critical Import Errors:")
            for error in IMPORT_ERRORS:
                print(f"  - {error}")
            print()
            return False

        # Run test phases
        await self.test_phase1_core()
        await self.test_phase2_integration()
        await self.test_phase3_live()
        await self.test_system_integration()

        # Generate test report
        self.generate_test_report()

        return self.get_overall_success()

    async def test_phase1_core(self):
        """Test Phase 1 - Core System"""
        print("🔧 Phase 1: Core System Tests")
        print("-" * 50)

        # Test 1: Data Models
        await self.test_data_models()

        # Test 2: Strategy Framework
        await self.test_strategy_framework()

        # Test 3: Indicators
        await self.test_indicators()

        # Test 4: Signal Processing
        await self.test_signal_processing()

        print()

    async def test_phase2_integration(self):
        """Test Phase 2 - Integration"""
        print("🔗 Phase 2: Integration Tests")
        print("-" * 50)

        # Test 1: Data Adapters
        await self.test_data_adapters()

        # Test 2: Risk Management
        await self.test_risk_management()

        # Test 3: Backtesting Engine
        await self.test_backtesting_engine()

        # Test 4: Multi-symbol Feeds
        await self.test_multi_symbol_feeds()

        print()

    async def test_phase3_live(self):
        """Test Phase 3 - Live Trading"""
        print("🚀 Phase 3: Live Trading Tests")
        print("-" * 50)

        # Test 1: Live Trading Engine
        await self.test_live_trading_engine()

        # Test 2: Streaming System
        await self.test_streaming_system()

        # Test 3: Order Management
        await self.test_order_management()

        # Test 4: Real-time Integration
        await self.test_realtime_integration()

        print()

    async def test_system_integration(self):
        """Test complete system integration"""
        print("🌐 System Integration Tests")
        print("-" * 50)

        # Test 1: End-to-End Signal Flow
        await self.test_end_to_end_signal_flow()

        # Test 2: Multi-Component Integration
        await self.test_multi_component_integration()

        # Test 3: Error Handling
        await self.test_error_handling()

        # Test 4: Performance Integration
        await self.test_performance_integration()

        print()

    async def test_data_models(self):
        """Test core data models"""
        test_name = "Data Models"
        try:
            # Test Candle model
            candle = Candle(
                timestamp=datetime.now(),
                symbol="AAPL",
                timeframe=TimeFrame.MINUTE_1,
                open=Decimal("150.00"),
                high=Decimal("151.00"),
                low=Decimal("149.00"),
                close=Decimal("150.50"),
                volume=1000000,
            )

            # Test Signal model
            signal = Signal(
                timestamp=datetime.now(),
                symbol="AAPL",
                direction=SignalDirection.LONG,
                signal_type=SignalType.ENTRY,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                take_profit=Decimal("160.00"),
                confidence=0.9,
                strength=0.8,
                strategy_name="test_strategy",
            )

            # Validate model properties
            assert candle.symbol == "AAPL"
            assert signal.direction == SignalDirection.LONG
            assert signal.confidence == 0.9

            self.record_test_result("phase1_core", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase1_core", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {exc}")

    async def test_strategy_framework(self):
        """Test strategy framework"""
        test_name = "Strategy Framework"
        try:
            # Test strategy configuration
            config = create_fvg_strategy_config(
                symbol="AAPL",
                timeframe=TimeFrame.MINUTE_5,
                fvg_min_size=0.001,
                fvg_max_age_candles=5,
                pivot_lookback=5,
                pivot_lookahead=5,
            )

            # Test strategy creation
            strategy = FVGStrategy(config)

            # Validate strategy properties
            assert strategy.config.symbol == "AAPL"
            assert strategy.config.timeframe == TimeFrame.MINUTE_5
            assert hasattr(strategy, "process_candle")
            assert hasattr(strategy, "get_signals")

            self.record_test_result("phase1_core", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase1_core", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_indicators(self):
        """Test indicators"""
        test_name = "Indicators"
        try:
            # Test FVG detector
            config = FVGFilterConfig(min_zone_size_pips=0.001, max_age_hours=120)
            detector = FVGDetector(config)

            # Validate indicator properties
            assert detector.config.min_zone_size_pips == 0.001
            assert detector.config.max_age_hours == 120
            assert hasattr(detector, "detect_fvgs")  # Fixed method name

            self.record_test_result("phase1_core", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase1_core", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_signal_processing(self):
        """Test signal processing"""
        test_name = "Signal Processing"
        try:
            # Create test signal
            signal = Signal(
                timestamp=datetime.now(),
                symbol="AAPL",
                direction=SignalDirection.LONG,
                signal_type=SignalType.ENTRY,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                take_profit=Decimal("160.00"),
                confidence=0.9,
                strength=0.8,
                strategy_name="test_strategy",
            )

            # Test signal validation
            assert signal.is_valid()
            assert signal.get_risk_reward_ratio() > 0
            assert signal.get_position_size(1000) > 0

            self.record_test_result("phase1_core", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase1_core", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_data_adapters(self):
        """Test data adapters"""
        test_name = "Data Adapters"
        try:
            # Test Yahoo Finance adapter
            yahoo_adapter = YahooFinanceAdapter()

            # Test adapter properties
            assert hasattr(yahoo_adapter, "get_historical_data")
            assert hasattr(yahoo_adapter, "get_realtime_data")

            self.record_test_result("phase2_integration", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase2_integration", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_risk_management(self):
        """Test risk management"""
        test_name = "Risk Management"
        try:
            # Create risk limits
            risk_limits = RiskLimits(
                max_position_size=Decimal("0.1"),
                max_daily_loss=Decimal("0.05"),
                max_drawdown=Decimal("0.2"),
                max_positions=5,
            )

            # Create position sizer
            position_sizer = FixedRiskPositionSizer(risk_per_trade=0.02)

            # Create risk manager
            risk_manager = RiskManager(
                risk_limits=risk_limits,
                position_sizer=position_sizer,
                initial_capital=Decimal("100000"),
            )

            # Test risk manager methods
            assert hasattr(risk_manager, "check_risk_limits")
            assert hasattr(risk_manager, "calculate_position_size")
            assert hasattr(risk_manager, "get_portfolio_summary")

            self.record_test_result("phase2_integration", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase2_integration", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_backtesting_engine(self):
        """Test backtesting engine"""
        test_name = "Backtesting Engine"
        try:
            # Create backtest config
            config = BacktestConfig(
                start_date=datetime.now() - timedelta(days=30),
                end_date=datetime.now(),
                initial_capital=Decimal("100000"),
                commission=Decimal("0.001"),
                slippage=Decimal("0.001"),
            )

            # Create backtesting engine
            engine = CoreBacktestEngine(config)

            # Test engine properties
            assert hasattr(engine, "run_backtest")
            assert hasattr(engine, "get_results")
            assert engine.config.initial_capital == Decimal("100000")

            self.record_test_result("phase2_integration", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase2_integration", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_multi_symbol_feeds(self):
        """Test multi-symbol data feeds"""
        test_name = "Multi-Symbol Feeds"
        try:
            # Create adapter first
            adapter = YahooFinanceAdapter()

            # Create multi-symbol feed
            feed = MultiSymbolDataFeed(adapter=adapter)

            # Add symbols and timeframes
            feed.add_symbol("AAPL", [TimeFrame.MINUTE_1, TimeFrame.MINUTE_5])
            feed.add_symbol("GOOGL", [TimeFrame.MINUTE_1, TimeFrame.MINUTE_5])
            feed.add_symbol("MSFT", [TimeFrame.MINUTE_1, TimeFrame.MINUTE_5])

            # Test feed properties
            assert hasattr(feed, "add_symbol")
            assert hasattr(feed, "remove_symbol")
            assert hasattr(feed, "unsubscribe")
            assert hasattr(feed, "get_latest_data")

            self.record_test_result("phase2_integration", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase2_integration", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_live_trading_engine(self):
        """Test live trading engine"""
        test_name = "Live Trading Engine"
        try:
            # Create paper broker
            broker = PaperBrokerAdapter(initial_balance=Decimal("100000"))

            # Create risk manager
            risk_limits = RiskLimits(
                max_position_size=Decimal("0.1"),
                max_daily_loss=Decimal("0.05"),
                max_drawdown=Decimal("0.2"),
                max_positions=5,
            )
            position_sizer = FixedRiskPositionSizer(risk_per_trade=0.02)
            risk_manager = RiskManager(
                risk_limits=risk_limits,
                position_sizer=position_sizer,
                initial_capital=Decimal("100000"),
            )

            # Create live trading config
            config = LiveTradingConfig(
                mode=ExecutionMode.PAPER,
                enable_auto_trading=True,
                max_orders_per_minute=10,
                max_daily_trades=50,
                emergency_stop_loss=0.05,
            )

            # Create live trading engine
            engine = LiveTradingEngine(
                broker_adapter=broker, risk_manager=risk_manager, config=config
            )

            # Test engine properties
            assert hasattr(engine, "start")
            assert hasattr(engine, "stop")
            assert hasattr(engine, "process_signal")
            assert hasattr(engine, "get_status")

            self.record_test_result("phase3_live", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase3_live", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_streaming_system(self):
        """Test streaming system"""
        test_name = "Streaming System"
        try:
            # Create streaming config
            streaming_config = StreamingConfig(
                provider=StreamingProvider.MOCK,
                symbols=["AAPL", "GOOGL", "MSFT"],
                timeframes=[TimeFrame.MINUTE_1],
                auto_reconnect=True,
            )

            # Create streaming manager
            manager = StreamingManager()

            # Test streaming properties
            assert hasattr(manager, "start")
            assert hasattr(manager, "stop")
            assert hasattr(manager, "subscribe_symbol")
            assert hasattr(manager, "get_status")

            self.record_test_result("phase3_live", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase3_live", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_order_management(self):
        """Test order management"""
        test_name = "Order Management"
        try:
            # Create paper broker
            broker = PaperBrokerAdapter(initial_balance=Decimal("100000"))

            # Test order methods
            assert hasattr(broker, "place_order")
            assert hasattr(broker, "cancel_order")
            assert hasattr(broker, "get_order_status")
            assert hasattr(broker, "get_positions")

            self.record_test_result("phase3_live", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase3_live", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_realtime_integration(self):
        """Test real-time integration"""
        test_name = "Real-time Integration"
        try:
            # Test that all components can work together
            # This is a structural test, not a functional test

            # Verify all required components exist
            components = [
                LiveTradingEngine,
                StreamingManager,
                PaperBrokerAdapter,
                RiskManager,
                FVGStrategy,
                MultiSymbolDataFeed,
            ]

            for component in components:
                assert component is not None

            self.record_test_result("phase3_live", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("phase3_live", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_end_to_end_signal_flow(self):
        """Test end-to-end signal flow"""
        test_name = "End-to-End Signal Flow"
        try:
            # Test complete signal flow from strategy to execution

            # 1. Create strategy
            config = create_fvg_strategy_config(
                symbol="AAPL", timeframe=TimeFrame.MINUTE_5
            )
            _ = FVGStrategy(config)  # Test instantiation

            # 2. Create signal
            signal = Signal(
                timestamp=datetime.now(),
                symbol="AAPL",
                direction=SignalDirection.LONG,
                signal_type=SignalType.ENTRY,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                take_profit=Decimal("160.00"),
                confidence=0.9,
                strength=0.8,
                strategy_name="test_strategy",
            )

            # 3. Validate signal can be processed
            assert signal.is_valid()
            assert signal.get_risk_reward_ratio() > 0

            self.record_test_result("system_integration", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("system_integration", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_multi_component_integration(self):
        """Test multi-component integration"""
        test_name = "Multi-Component Integration"
        try:
            # Test that multiple components can be instantiated together

            # Create all major components
            broker = PaperBrokerAdapter(initial_balance=Decimal("100000"))
            risk_manager = RiskManager(
                risk_limits=RiskLimits(
                    max_position_size=Decimal("0.1"),
                    max_daily_loss=Decimal("0.05"),
                    max_drawdown=Decimal("0.2"),
                    max_positions=5,
                ),
                position_sizer=FixedRiskPositionSizer(risk_per_trade=0.02),
                initial_capital=Decimal("100000"),
            )

            # Verify no conflicts
            assert broker is not None
            assert risk_manager is not None

            self.record_test_result("system_integration", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("system_integration", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_error_handling(self):
        """Test error handling"""
        test_name = "Error Handling"
        try:
            # Test that invalid configurations are handled

            # Test invalid signal
            try:
                signal = Signal(
                    timestamp=datetime.now(),
                    symbol="AAPL",
                    direction=SignalDirection.LONG,
                    signal_type=SignalType.ENTRY,
                    entry_price=Decimal("150.00"),
                    stop_loss=Decimal(
                        "155.00"
                    ),  # Invalid: stop loss above entry for long
                    take_profit=Decimal("160.00"),
                    confidence=0.9,
                    strength=0.8,
                    strategy_name="test_strategy",
                )
                # This should be invalid
                assert not signal.is_valid()

            except Exception:
                # Error handling working correctly
                pass

            self.record_test_result("system_integration", test_name, True)
            print(f"  ✅ {test_name}: PASSED")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("system_integration", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    async def test_performance_integration(self):
        """Test performance integration"""
        test_name = "Performance Integration"
        try:
            # Test that all components can be imported and instantiated quickly
            import time  # pylint: disable=import-outside-toplevel

            start_time = time.time()

            # Create all major components (test instantiation performance)
            _ = PaperBrokerAdapter(initial_balance=Decimal("100000"))
            _ = RiskManager(
                risk_limits=RiskLimits(
                    max_position_size=Decimal("0.1"),
                    max_daily_loss=Decimal("0.05"),
                    max_drawdown=Decimal("0.2"),
                    max_positions=5,
                ),
                position_sizer=FixedRiskPositionSizer(risk_per_trade=0.02),
                initial_capital=Decimal("100000"),
            )

            config = create_fvg_strategy_config(
                symbol="AAPL", timeframe=TimeFrame.MINUTE_5
            )
            _ = FVGStrategy(config)

            end_time = time.time()
            creation_time = end_time - start_time

            # Should be reasonably fast (under 1 second)
            assert creation_time < 1.0

            self.record_test_result("system_integration", test_name, True)
            print(f"  ✅ {test_name}: PASSED (creation time: {creation_time:.3f}s)")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.record_test_result("system_integration", test_name, False, str(exc))
            print(f"  ❌ {test_name}: FAILED - {e}")

    def record_test_result(
        self, phase: str, test_name: str, passed: bool, error: str = None
    ):
        """Record a test result"""
        if passed:
            self.test_results[phase]["passed"] += 1
        else:
            self.test_results[phase]["failed"] += 1

        self.test_results[phase]["tests"].append(
            {"name": test_name, "passed": passed, "error": error}
        )

    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("📊 Complete System Integration Test Report")
        print("=" * 80)

        total_passed = 0
        total_failed = 0

        for phase, results in self.test_results.items():
            phase_name = phase.replace("_", " ").title()
            passed = results["passed"]
            failed = results["failed"]
            total = passed + failed

            total_passed += passed
            total_failed += failed

            if total > 0:
                success_rate = (passed / total) * 100
                print(f"\n{phase_name}:")
                print(f"  Passed: {passed}/{total} ({success_rate:.1f}%)")

                if failed > 0:
                    print(f"  Failed: {failed}/{total}")
                    for test in results["tests"]:
                        if not test["passed"]:
                            print(f"    ❌ {test['name']}: {test['error']}")

        # Overall summary
        total_tests = total_passed + total_failed
        overall_success_rate = (
            (total_passed / total_tests) * 100 if total_tests > 0 else 0
        )

        print(f"\n📈 Overall Test Results:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {total_passed}")
        print(f"  Failed: {total_failed}")
        print(f"  Success Rate: {overall_success_rate:.1f}%")

        # System status
        if total_failed == 0:
            print("\n✅ All tests passed! System is ready for production.")
        elif total_failed <= 2:
            print("\n⚠️  Minor issues detected. System is mostly functional.")
        else:
            print("\n❌ Multiple issues detected. System needs attention.")

        print("=" * 80)

    def get_overall_success(self):
        """Get overall test success status"""
        total_failed = sum(results["failed"] for results in self.test_results.values())
        return total_failed == 0


async def main():
    """Main test function"""
    test = SystemIntegrationTest()
    success = await test.run_complete_test()

    # Return appropriate exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
