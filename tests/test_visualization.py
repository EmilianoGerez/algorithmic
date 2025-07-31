#!/usr/bin/env python3
"""
Test script to demonstrate the visualization capabilities.
"""

from pathlib import Path

import pandas as pd

from scripts.visualization.plot_builder import (
    build_plotly_from_data,
    build_static_chart_from_data,
    display_chart_in_chatgpt_from_data,
)


def create_sample_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create sample trade and event data for testing."""
    # Load actual BTC data
    data_path = Path("data/BTCUSDT_5m_2025-05-18_futures.csv")
    if not data_path.exists():
        # Skip test if no data available
        import pytest

        pytest.skip("No test data available")

    df = pd.read_csv(data_path).head(500)  # Use first 500 rows for demo
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Generate sample trades
    trades = []
    for i in range(0, len(df), 50):  # Every 50 candles
        if i + 10 < len(df):
            entry_price = df.iloc[i]["close"]
            exit_price = df.iloc[i + 10]["close"]
            pnl = (exit_price - entry_price) * 100  # Assume 100 units

            trades.append(
                {
                    "entry_time": df.iloc[i]["timestamp"],
                    "exit_time": df.iloc[i + 10]["timestamp"],
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "size": 100,
                    "side": "long",
                    "pnl": pnl,
                    "reason": "take_profit" if pnl > 0 else "stop_loss",
                }
            )

    trades_df = pd.DataFrame(trades)

    # Generate sample FVG events
    fvg_events = []
    for i in range(10, len(df), 100):  # Every 100 candles
        if i + 3 < len(df):
            fvg_events.append(
                {
                    "timestamp": df.iloc[i]["timestamp"],
                    "type": "fvg",
                    "high": df.iloc[i]["high"] * 1.001,
                    "low": df.iloc[i]["low"] * 0.999,
                    "direction": "bullish" if i % 2 == 0 else "bearish",
                }
            )

    events_df = pd.DataFrame(fvg_events)

    return df, trades_df, events_df


def test_static_chart() -> bool:
    """Test static mplfinance chart generation."""
    print("🔄 Testing static chart generation...")

    data_df, trades_df, events_df = create_sample_data()

    output_path = Path("test_static_chart.png")

    try:
        build_static_chart_from_data(
            data_df=data_df,
            trades_df=trades_df,
            events_df=events_df,
            output_path=str(output_path),
            title="Test Static Chart - BTC/USD 5M",
        )
        print(f"✅ Static chart saved to: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Static chart generation failed: {e}")
        return False


def test_interactive_chart() -> bool:
    """Test interactive Plotly chart generation."""
    print("🔄 Testing interactive chart generation...")

    data_df, trades_df, events_df = create_sample_data()

    try:
        fig = build_plotly_from_data(
            data_df=data_df,
            trades_df=trades_df,
            events_df=events_df,
            title="Test Interactive Chart - BTC/USD 5M",
        )

        # Save as HTML
        output_path = Path("results/test_interactive_chart.html")
        output_path.parent.mkdir(exist_ok=True)
        fig.write_html(str(output_path))
        print(f"✅ Interactive chart saved to: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Interactive chart generation failed: {e}")
        return False


def test_chatgpt_display() -> bool:
    """Test ChatGPT environment detection and display."""
    print("🔄 Testing ChatGPT display...")

    data_df, trades_df, events_df = create_sample_data()

    try:
        result = display_chart_in_chatgpt_from_data(
            data_df=data_df,
            trades_df=trades_df,
            events_df=events_df,
            title="Test ChatGPT Chart - BTC/USD 5M",
        )
        print(f"✅ ChatGPT display test completed: {result}")
        return True
    except Exception as e:
        print(f"❌ ChatGPT display failed: {e}")
        return False


def main() -> None:
    """Run all visualization tests."""
    print("🧪 Testing Visualization System")
    print("=" * 50)

    tests_passed = 0
    total_tests = 3

    # Test static chart
    if test_static_chart():
        tests_passed += 1

    print()

    # Test interactive chart
    if test_interactive_chart():
        tests_passed += 1

    print()

    # Test ChatGPT display
    if test_chatgpt_display():
        tests_passed += 1

    print()
    print("=" * 50)
    print(f"📊 Tests Summary: {tests_passed}/{total_tests} passed")

    if tests_passed == total_tests:
        print("🎉 All visualization features working correctly!")
    else:
        print("⚠️  Some visualization features need attention.")


if __name__ == "__main__":
    main()
