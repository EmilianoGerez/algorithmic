#!/usr/bin/env python3
"""
Test Alpaca Integration

Simple test to verify Alpaca integration is working correctly.
"""

import os
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test that all required modules can be imported"""
    print("🔍 Testing imports...")

    try:
        from core.backtesting import BacktestConfig, CoreBacktestEngine
        from core.data.adapters import AlpacaAdapter, DataAdapterFactory
        from core.data.models import MarketData, TimeFrame
        from core.strategies import FVGStrategy

        print("✅ Core modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def test_alpaca_adapter_creation():
    """Test that AlpacaAdapter can be created"""
    print("🔧 Testing AlpacaAdapter creation...")

    try:
        from core.data.adapters import DataAdapterFactory

        # Test with dummy credentials
        adapter = DataAdapterFactory.create_adapter(
            "alpaca", api_key="test_key", secret_key="test_secret"
        )

        print("✅ AlpacaAdapter created successfully")
        return True
    except Exception as e:
        print(f"❌ AlpacaAdapter creation failed: {e}")
        return False


def test_sample_data_generation():
    """Test sample data generation for when Alpaca isn't available"""
    print("📊 Testing sample data generation...")

    try:
        from decimal import Decimal

        from core.data.models import Candle, MarketData, TimeFrame

        # Create sample market data
        market_data = MarketData(
            symbol="TEST",
            timeframe=TimeFrame.MINUTE_15,
            metadata={"source": "test"},
        )

        # Add a few sample candles
        base_time = datetime.now() - timedelta(hours=1)
        for i in range(5):
            candle = Candle(
                timestamp=base_time + timedelta(minutes=i * 15),
                open=Decimal("100.00"),
                high=Decimal("101.00"),
                low=Decimal("99.00"),
                close=Decimal("100.50"),
                volume=Decimal("1000"),
                symbol="TEST",
                timeframe=TimeFrame.MINUTE_15,
            )
            market_data.add_candle(candle)

        print(f"✅ Generated {len(market_data.candles)} sample candles")
        return True

    except Exception as e:
        print(f"❌ Sample data generation failed: {e}")
        return False


def test_strategy_initialization():
    """Test that FVG strategy can be initialized"""
    print("🧠 Testing strategy initialization...")

    try:
        from core.strategies import FVGStrategy, create_fvg_strategy_config

        # Create strategy with config
        config = create_fvg_strategy_config("TEST")
        strategy = FVGStrategy(config)
        strategy.initialize()

        print("✅ FVG strategy initialized successfully")
        return True

    except Exception as e:
        print(f"❌ Strategy initialization failed: {e}")
        return False


def test_backtest_config():
    """Test backtest configuration"""
    print("⚙️ Testing backtest configuration...")

    try:
        from decimal import Decimal

        from core.backtesting import BacktestConfig
        from core.risk import RiskLimits

        config = BacktestConfig(
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now(),
            initial_capital=Decimal("10000"),
            risk_limits=RiskLimits(),
        )

        print("✅ Backtest configuration created successfully")
        return True

    except Exception as e:
        print(f"❌ Backtest configuration failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🧪 Testing Alpaca Integration")
    print("=" * 35)

    tests = [
        ("Imports", test_imports),
        ("AlpacaAdapter Creation", test_alpaca_adapter_creation),
        ("Sample Data Generation", test_sample_data_generation),
        ("Strategy Initialization", test_strategy_initialization),
        ("Backtest Configuration", test_backtest_config),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            print()  # Empty line between tests
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            print()

    print("📊 TEST RESULTS")
    print("=" * 20)
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {passed/total*100:.1f}%")

    if passed == total:
        print("\\n🎉 All tests passed! System is ready for Alpaca integration.")
        print("\\n📚 Next steps:")
        print("1. Set up Alpaca API credentials in .env file")
        print("2. Run: python setup_alpaca.py")
        print("3. Run: python demo_alpaca_backtest.py")
    else:
        print("\\n⚠️  Some tests failed. Please check the errors above.")
        print("\\n🔧 Troubleshooting:")
        print("1. Make sure you're in the project root directory")
        print("2. Check that all files are in the correct locations")
        print("3. Verify the project structure matches the documentation")


if __name__ == "__main__":
    main()
