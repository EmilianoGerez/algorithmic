"""
Example Usage of the New Core System

This script demonstrates how to use the new clean core system
to implement the FVG strategy.
."""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

# Add the core package to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import (  # Data models; Strategy system; Indicators; Signal processing
    Candle,
    FVGDetector,
    FVGFilterPresets,
    FVGStrategy,
    MarketData,
    TechnicalIndicators,
    TimeFrame,
    create_fvg_strategy_config,
    strategy_registry,
)


def create_sample_candles(
    symbol: str, timeframe: TimeFrame, count: int = 100
) -> list[Candle]:
    """Create sample candle data for testing."""
    candles = []
    base_price = Decimal("50000")  # BTC price
    base_time = datetime.utcnow() - timedelta(hours=count)

    for i in range(count):
        # Simple random walk for testing
        price_change = (i % 5 - 2) * Decimal("100")  # -200 to +200
        current_price = base_price + price_change

        # Create realistic OHLC
        open_price = current_price + Decimal("50")
        high_price = current_price + Decimal("150")
        low_price = current_price - Decimal("100")
        close_price = current_price

        candle = Candle(
            timestamp=base_time + timedelta(hours=i),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=Decimal("1000"),
            symbol=symbol,
            timeframe=timeframe,
        )

        candles.append(candle)

    return candles


def demonstrate_fvg_detection() -> None:
    """Demonstrate FVG detection with the new system."""
    print("🔍 FVG Detection Demo")
    print("=" * 50)

    # Create sample data
    symbol = "BTC/USD"
    candles = create_sample_candles(symbol, TimeFrame.HOUR_4, 50)

    # Initialize FVG detector
    detector = FVGDetector(FVGFilterPresets.balanced())

    # Detect FVGs
    fvg_zones = detector.detect_fvgs(candles)

    print(f"📊 Detected {len(fvg_zones)} FVG zones")

    for i, fvg in enumerate(fvg_zones[:5]):  # Show first 5
        print(
            f"  FVG {i+1}: {fvg.direction.value} | "
            f"Strength: {fvg.strength:.2f} | "
            f"Confidence: {fvg.confidence:.2f} | "
            f"Zone: {fvg.zone_low:.2f} - {fvg.zone_high:.2f}"
        )

    # Get quality metrics
    metrics = detector.get_quality_metrics()
    print("\n📈 Quality Metrics:")
    print(f"  High Quality FVGs: {metrics.get('high_quality_count', 0)}")
    print(f"  Average Strength: {metrics.get('average_strength', 0):.2f}")
    print(f"  Average Confidence: {metrics.get('average_confidence', 0):.2f}")


def demonstrate_ema_system() -> None:
    """Demonstrate EMA calculations."""
    print("\n📊 EMA System Demo")
    print("=" * 50)

    # Create sample data
    symbol = "BTC/USD"
    candles = create_sample_candles(symbol, TimeFrame.MINUTE_15, 100)

    # Calculate EMAs
    ema_9 = TechnicalIndicators.ema(candles, 9)
    ema_20 = TechnicalIndicators.ema(candles, 20)
    ema_50 = TechnicalIndicators.ema(candles, 50)

    print("📈 Calculated EMAs:")
    print(f"  EMA 9: {len(ema_9)} values")
    print(f"  EMA 20: {len(ema_20)} values")
    print(f"  EMA 50: {len(ema_50)} values")

    if ema_9 and ema_20 and ema_50:
        print("\n🎯 Latest EMA Values:")
        print(f"  EMA 9: {ema_9[-1].value:.2f}")
        print(f"  EMA 20: {ema_20[-1].value:.2f}")
        print(f"  EMA 50: {ema_50[-1].value:.2f}")


def demonstrate_strategy_system() -> None:
    """Demonstrate the strategy system."""
    print("\n🎯 Strategy System Demo")
    print("=" * 50)

    # Create strategy configuration
    config = create_fvg_strategy_config("BTC/USD")

    # Create strategy instance
    strategy = FVGStrategy(config)
    strategy.initialize()

    print("📋 Strategy Info:")
    print(f"  Name: {strategy.name}")
    print(f"  Symbol: {strategy.symbol}")
    print(
        f"  Required Timeframes: "
        f"{[tf.value for tf in strategy.get_required_timeframes()]}"
    )
    print(f"  Min History Length: {strategy.get_required_history_length()}")

    # Create market data
    market_data = {}

    # HTF data (4H)
    htf_candles = create_sample_candles("BTC/USD", TimeFrame.HOUR_4, 200)
    market_data[TimeFrame.HOUR_4] = MarketData(
        symbol="BTC/USD", timeframe=TimeFrame.HOUR_4, candles=htf_candles
    )

    # HTF data (1D)
    daily_candles = create_sample_candles("BTC/USD", TimeFrame.DAY_1, 50)
    market_data[TimeFrame.DAY_1] = MarketData(
        symbol="BTC/USD", timeframe=TimeFrame.DAY_1, candles=daily_candles
    )

    # LTF data (15min)
    ltf_candles = create_sample_candles("BTC/USD", TimeFrame.MINUTE_15, 500)
    market_data[TimeFrame.MINUTE_15] = MarketData(
        symbol="BTC/USD", timeframe=TimeFrame.MINUTE_15, candles=ltf_candles
    )

    # Generate signals
    signals = strategy.generate_signals(market_data)

    print(f"\n🚀 Generated {len(signals)} signals")

    for i, signal in enumerate(signals[:3]):  # Show first 3
        print(f"  Signal {i+1}:")
        print(f"    Direction: {signal.direction.value}")
        print(f"    Entry: {signal.entry_price:.2f}")
        print(f"    Stop: {signal.stop_loss:.2f}")
        print(f"    Target: {signal.take_profit:.2f}")
        print(f"    Confidence: {signal.confidence:.2f}")
        print(f"    R:R Ratio: {signal.get_actual_risk_reward_ratio():.2f}")

    # Get strategy status
    status = strategy.get_strategy_status()
    print("\n📊 Strategy Status:")
    print(f"  Active FVGs: {status['active_fvgs']}")
    print(f"  Initialized: {status['is_initialized']}")


def demonstrate_strategy_registry() -> None:
    """Demonstrate strategy registry."""
    print("\n📚 Strategy Registry Demo")
    print("=" * 50)

    # List registered strategies
    strategies = strategy_registry.list_strategies()
    print(f"📋 Registered Strategies: {strategies}")

    # Create strategy via registry
    config = create_fvg_strategy_config("BTC/USD")
    strategy = strategy_registry.create_strategy("FVGStrategy", config)

    print(f"✅ Created strategy: {strategy}")
    print(f"   Strategy type: {type(strategy).__name__}")
    print(f"   Strategy name: {strategy.name}")


def main() -> None:
    """Main demonstration function."""
    print("🚀 New Core System Demonstration")
    print("=" * 60)
    print("This demo shows the new clean, modular architecture")
    print("extracting proven logic from the legacy system.")
    print()

    try:
        # Run demonstrations
        demonstrate_fvg_detection()
        demonstrate_ema_system()
        demonstrate_strategy_system()
        demonstrate_strategy_registry()

        print("\n✅ All demonstrations completed successfully!")
        print("\n🎯 Key Benefits of New Architecture:")
        print("  ✓ Clean separation of concerns")
        print("  ✓ Reusable components")
        print("  ✓ Easy to test and maintain")
        print("  ✓ Plug-and-play strategies")
        print("  ✓ Platform-agnostic design")
        print("  ✓ Professional-grade structure")

    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
