#!/usr/bin/env python3
"""
BTC/USD Alpaca Backtest Configuration.

Specific setup for Bitcoin backtesting with Alpaca data.
Period: May 18, 2025 to July 18, 2025
."""

import os
from datetime import datetime
from typing import Any

# BTC/USD Backtest Configuration
BACKTEST_CONFIG: dict[str, Any] = {
    "symbol": "BTCUSD",
    "start_date": "2025-05-18",
    "end_date": "2025-07-18",
    "timeframe": "5Min",
    "initial_capital": 50000,
    "commission": 0.0025,  # 0.25% typical for crypto
    "slippage": 0.001,  # 0.1% for crypto volatility
    "risk_per_trade": 0.015,  # 1.5% risk per trade
    "max_drawdown": 0.20,  # 20% max drawdown
    "strategy_params": {
        "confidence_threshold": 0.8,
        "nyc_hours_only": False,  # Crypto trades 24/7
        "swing_lookback": 30,
        "fvg_filter_preset": "balanced",
        "risk_reward_ratio": 2.0,
    },
}

# Alpaca API Settings
ALPACA_CONFIG: dict[str, Any] = {
    "base_url": "https://paper-api.alpaca.markets",
    "data_source": "crypto",  # Alpaca crypto data
    "rate_limit": 200,  # requests per minute
    "max_bars_per_request": 10000,
}

# Expected Performance Metrics (for validation)
EXPECTED_METRICS: dict[str, Any] = {
    "min_total_return": 0.05,  # 5% minimum return
    "max_drawdown_limit": 0.25,  # 25% max acceptable drawdown
    "min_win_rate": 0.45,  # 45% minimum win rate
    "min_sharpe_ratio": 0.5,  # 0.5 minimum Sharpe ratio
    "target_total_trades": 50,  # Expected number of trades
}

# Risk Management Rules
RISK_RULES: dict[str, Any] = {
    "max_position_size": 0.05,  # 5% max position size
    "max_portfolio_risk": 0.015,  # 1.5% max portfolio risk
    "max_correlation": 0.8,  # 80% max correlation
    "stop_loss_buffer": 0.001,  # 0.1% buffer on stops
    "take_profit_multiplier": 2.0,  # 1:2 R:R ratio
}


def get_btc_backtest_summary():
    """Get formatted summary of BTC backtest configuration."""
    separator = "=" * 50
    return f"""
🚀 BTC/USD Alpaca Backtest Configuration
{separator}

📊 Market Data:
   Symbol: {BACKTEST_CONFIG['symbol']}
   Period: {BACKTEST_CONFIG['start_date']} to {BACKTEST_CONFIG['end_date']}
   Timeframe: {BACKTEST_CONFIG['timeframe']} (5-minute candles)
   Duration: ~2 months of crypto data

💰 Capital & Risk:
   Initial Capital: ${BACKTEST_CONFIG['initial_capital']:,}
   Commission: {BACKTEST_CONFIG['commission']:.2%}
   Slippage: {BACKTEST_CONFIG['slippage']:.2%}
   Risk per Trade: {BACKTEST_CONFIG['risk_per_trade']:.1%}
   Max Drawdown: {BACKTEST_CONFIG['max_drawdown']:.0%}

🎯 Strategy Settings:
   Confidence Threshold: {BACKTEST_CONFIG['strategy_params']['confidence_threshold']:.0%}
   24/7 Trading: {not BACKTEST_CONFIG['strategy_params']['nyc_hours_only']}
   Swing Lookback: {BACKTEST_CONFIG['strategy_params']['swing_lookback']} periods
   Filter Preset: {BACKTEST_CONFIG['strategy_params']['fvg_filter_preset']}
   Risk/Reward: 1:{BACKTEST_CONFIG['strategy_params']['risk_reward_ratio']:.0f}

🎲 Expected Performance:
   Min Return: {EXPECTED_METRICS['min_total_return']:.0%}
   Max Drawdown: {EXPECTED_METRICS['max_drawdown_limit']:.0%}
   Min Win Rate: {EXPECTED_METRICS['min_win_rate']:.0%}
   Target Trades: {EXPECTED_METRICS['target_total_trades']}+

🔧 Technical Setup:
   Data Source: Alpaca Markets
   Rate Limit: {ALPACA_CONFIG['rate_limit']} req/min
   Max Bars/Request: {ALPACA_CONFIG['max_bars_per_request']:,}
   {separator}
."""


def validate_environment():
    """Validate that environment is ready for BTC backtest."""
    issues = []

    # Check API credentials
    if not os.getenv("ALPACA_API_KEY"):
        issues.append("❌ ALPACA_API_KEY not set")

    if not os.getenv("ALPACA_SECRET_KEY"):
        issues.append("❌ ALPACA_SECRET_KEY not set")

    # Check date range
    start_date = datetime.strptime(BACKTEST_CONFIG["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(BACKTEST_CONFIG["end_date"], "%Y-%m-%d")

    if start_date >= end_date:
        issues.append("❌ Invalid date range")

    if (end_date - start_date).days < 30:
        issues.append("⚠️  Short backtest period (< 30 days)")

    return issues


if __name__ == "__main__":
    print(get_btc_backtest_summary())

    issues = validate_environment()
    if issues:
        print("🔧 Environment Issues:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ Environment ready for BTC backtest!")
