#!/usr/bin/env python3
"""
Alpaca Integration Setup Script

This script helps set up everything needed for Alpaca backtesting:
- Installs required packages
- Sets up environment variables
- Tests Alpaca connection
- Validates data fetching
- Runs sample backtest
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta


def check_python_version():
    """Check if Python version is compatible"""
    print("🐍 Checking Python version...")

    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required. Current version:", sys.version)
        return False

    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} is compatible")
    return True


def install_packages():
    """Install required packages"""
    print("\\n📦 Installing required packages...")

    packages = [
        "alpaca-trade-api>=3.0.0",
        "yfinance>=0.2.0",
        "pandas>=1.5.0",
        "numpy>=1.21.0",
    ]

    for package in packages:
        try:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            return False

    return True


def setup_environment():
    """Set up environment variables"""
    print("\\n🔧 Setting up environment variables...")

    env_file = ".env"

    # Check if .env already exists
    if os.path.exists(env_file):
        print(f"✅ {env_file} already exists")
        return True

    # Create .env template
    env_template = """# Alpaca API Configuration
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Database Configuration (optional)
DATABASE_URL=postgresql://user:pass@localhost/trading_db
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO
"""

    try:
        with open(env_file, "w") as f:
            f.write(env_template)
        print(f"✅ Created {env_file} template")
        print("⚠️  Please update the API credentials in .env file")
        return True
    except Exception as e:
        print(f"❌ Failed to create {env_file}: {e}")
        return False


def test_alpaca_connection():
    """Test Alpaca API connection"""
    print("\\n🔌 Testing Alpaca connection...")

    try:
        # Try to import alpaca-trade-api
        from alpaca_trade_api import REST
        from alpaca_trade_api.common import URL

        print("✅ Alpaca Trade API imported successfully")

        # Load environment variables
        from dotenv import load_dotenv

        load_dotenv()

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

        if not api_key or api_key == "your_alpaca_api_key_here":
            print("⚠️  Alpaca API credentials not configured")
            print("Please update your .env file with actual credentials")
            return False

        # Test connection
        client = REST(api_key, secret_key, base_url=URL(base_url))
        account = client.get_account()

        print(f"✅ Connected to Alpaca successfully")
        print(f"📊 Account Status: {account.status}")
        print(f"💰 Buying Power: ${account.buying_power}")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install required packages first")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("Please check your API credentials")
        return False


def test_data_fetching():
    """Test historical data fetching"""
    print("\\n📊 Testing data fetching...")

    try:
        # Add project root to path
        project_root = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, project_root)

        from datetime import datetime, timedelta

        # Load environment variables
        from dotenv import load_dotenv

        from core.data.adapters import DataAdapterFactory
        from core.data.models import TimeFrame

        load_dotenv()

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or api_key == "your_alpaca_api_key_here":
            print("⚠️  Skipping data test - credentials not configured")
            return False

        # Create adapter
        adapter = DataAdapterFactory.create_adapter(
            "alpaca", api_key=api_key, secret_key=secret_key
        )

        # Test symbol validation
        if not adapter.validate_symbol("AAPL"):
            print("❌ Symbol validation failed")
            return False

        print("✅ Symbol validation successful")

        # Test data fetching
        end_date = datetime.now()
        start_date = end_date - timedelta(days=2)

        market_data = adapter.get_historical_data(
            symbol="AAPL",
            timeframe=TimeFrame.MINUTE_15,
            start_date=start_date,
            end_date=end_date,
            limit=10,
        )

        if "error" in market_data.metadata:
            print(f"❌ Data fetching error: {market_data.metadata['error']}")
            return False

        bars_count = len(market_data.candles)
        print(f"✅ Successfully fetched {bars_count} bars")

        if bars_count > 0:
            first_candle = market_data.candles[0]
            print(f"📈 Sample data: {first_candle.timestamp} - ${first_candle.close}")

        return True

    except Exception as e:
        print(f"❌ Data fetching test failed: {e}")
        return False


def run_sample_backtest():
    """Run a sample backtest"""
    print("\\n🧪 Running sample backtest...")

    try:
        # Run the demo script
        demo_script = "demo_alpaca_backtest.py"

        if not os.path.exists(demo_script):
            print(f"❌ {demo_script} not found")
            return False

        print("Running Alpaca backtest demo...")
        subprocess.run([sys.executable, demo_script], check=True)

        print("✅ Sample backtest completed successfully")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Sample backtest failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error running sample backtest: {e}")
        return False


def main():
    """Main setup function"""
    print("🚀 Alpaca Integration Setup")
    print("=" * 40)

    # Step 1: Check Python version
    if not check_python_version():
        return

    # Step 2: Install packages
    if not install_packages():
        print("❌ Package installation failed")
        return

    # Step 3: Setup environment
    if not setup_environment():
        print("❌ Environment setup failed")
        return

    # Step 4: Test connection (optional if credentials are configured)
    connection_ok = test_alpaca_connection()

    # Step 5: Test data fetching (optional if credentials are configured)
    if connection_ok:
        test_data_fetching()

    # Step 6: Run sample backtest
    if connection_ok:
        run_sample_backtest()

    print("\\n🎉 Setup Complete!")
    print("\\n📚 Next Steps:")

    if not connection_ok:
        print("1. Update .env with your Alpaca API credentials")
        print("2. Run: python setup_alpaca.py (to test connection)")
        print("3. Run: python demo_alpaca_backtest.py (to run backtest)")
    else:
        print("1. Run: python demo_alpaca_backtest.py (to run more backtests)")
        print("2. Customize strategies in core/strategies/")
        print("3. Explore the API at http://localhost:8000/docs")

    print("\\n📖 Resources:")
    print("- Alpaca API Docs: https://alpaca.markets/docs/")
    print("- Get API Keys: https://app.alpaca.markets/")
    print("- Project Guide: ALPACA_BACKTEST_GUIDE.md")


if __name__ == "__main__":
    main()
