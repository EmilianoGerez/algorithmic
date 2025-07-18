# Alpaca Backtesting Implementation Guide

## 📊 Overview

This guide provides everything needed to implement backtesting with Alpaca historical data in your algorithmic trading system.

## 🎯 Required Components

### 1. Dependencies

Add these to your `requirements.txt`:

```
alpaca-trade-api>=3.0.0
pandas>=1.5.0
numpy>=1.21.0
```

### 2. Environment Variables

Add to your `.env` file:

```bash
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # or live URL
```

### 3. Complete AlpacaAdapter Implementation

The current `AlpacaAdapter` in `core/data/adapters.py` needs these methods implemented:

#### Key Methods to Implement:

- `_get_client()` - Initialize Alpaca REST client
- `get_historical_data()` - Fetch historical bars
- `_convert_alpaca_bar()` - Convert Alpaca data to Candle format
- `get_latest_candle()` - Get most recent candle
- `validate_symbol()` - Check if symbol exists

### 4. Alpaca-Specific Configuration

#### Timeframe Mapping:

```python
ALPACA_TIMEFRAME_MAP = {
    TimeFrame.MINUTE_1: "1Min",
    TimeFrame.MINUTE_5: "5Min",
    TimeFrame.MINUTE_15: "15Min",
    TimeFrame.MINUTE_30: "30Min",
    TimeFrame.HOUR_1: "1Hour",
    TimeFrame.DAY_1: "1Day"
}
```

#### Data Limits:

- **Minute data**: Up to 1000 bars per request
- **Daily data**: Up to 10,000 bars per request
- **Rate limits**: 200 requests per minute

### 5. Implementation Steps

#### Step 1: Complete AlpacaAdapter

```python
from alpaca_trade_api import REST
from alpaca_trade_api.common import URL

class AlpacaAdapter(DataAdapter):
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://paper-api.alpaca.markets"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = REST(
                self.api_key,
                self.secret_key,
                base_url=URL(self.base_url)
            )
        return self._client

    def get_historical_data(self, symbol, timeframe, start_date, end_date, limit=None):
        # Implementation details below...
```

#### Step 2: Create Alpaca Backtest Demo

A demo script showing:

- Data fetching from Alpaca
- Strategy execution
- Performance analysis
- Results visualization

#### Step 3: Add Data Quality Checks

- Missing data handling
- Corporate actions adjustment
- Weekend/holiday filtering
- Volume validation

## 🚀 Usage Example

```python
from core.data.adapters import DataAdapterFactory
from core.backtesting import CoreBacktestEngine, BacktestConfig
from core.strategies import FVGStrategy
from datetime import datetime, timedelta

# Create Alpaca adapter
adapter = DataAdapterFactory.create_adapter(
    "alpaca",
    api_key="YOUR_API_KEY",
    secret_key="YOUR_SECRET_KEY"
)

# Fetch historical data
market_data = adapter.get_historical_data(
    symbol="AAPL",
    timeframe=TimeFrame.MINUTE_15,
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now()
)

# Configure backtest
config = BacktestConfig(
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    initial_capital=Decimal('10000'),
    commission=Decimal('0.001')
)

# Run backtest
engine = CoreBacktestEngine(adapter)
strategy = FVGStrategy()
results = engine.run_backtest(strategy, market_data, config)
```

## 🔍 Data Quality Considerations

### 1. Market Hours

- Filter data to trading hours (9:30 AM - 4:00 PM ET)
- Handle pre-market and after-hours data separately
- Account for early closes and holidays

### 2. Corporate Actions

- Stock splits adjustment
- Dividend adjustments
- Merger/acquisition handling

### 3. Data Gaps

- Weekend gaps
- Holiday gaps
- Halted trading periods

## 📈 Performance Optimization

### 1. Data Caching

- Cache historical data locally
- Implement incremental updates
- Use Redis for session caching

### 2. Batch Processing

- Request data in optimal batch sizes
- Implement parallel requests for multiple symbols
- Use connection pooling

### 3. Memory Management

- Stream large datasets
- Implement data pagination
- Clear unused data from memory

## 🛠️ Implementation Files Needed

1. **Complete AlpacaAdapter** (`core/data/adapters.py`)
2. **Alpaca Demo Script** (`demo_alpaca_backtest.py`)
3. **Data Quality Utilities** (`core/data/quality.py`)
4. **Caching System** (`core/data/cache.py`)
5. **Performance Metrics** (`core/backtesting/metrics.py`)

## 🧪 Testing Strategy

### Unit Tests

- Adapter functionality
- Data conversion accuracy
- Error handling

### Integration Tests

- Full backtest pipeline
- Multi-symbol backtests
- Edge case handling

### Performance Tests

- Large dataset handling
- Memory usage optimization
- Speed benchmarks

## 🔐 Security Considerations

1. **API Key Management**

   - Use environment variables
   - Implement key rotation
   - Add usage monitoring

2. **Rate Limiting**

   - Implement request throttling
   - Add retry logic with exponential backoff
   - Monitor API usage

3. **Data Validation**
   - Validate all incoming data
   - Check for anomalies
   - Implement data sanitization

## 📊 Expected Results

Once implemented, you'll have:

- ✅ **Real market data** from Alpaca
- ✅ **Institutional-grade backtesting**
- ✅ **Multiple asset support**
- ✅ **Professional performance metrics**
- ✅ **Scalable architecture**

## 🎯 Next Steps

1. **Install Dependencies**: Add alpaca-trade-api to requirements
2. **Complete Adapter**: Implement all AlpacaAdapter methods
3. **Create Demo**: Build demonstration script
4. **Add Tests**: Implement comprehensive test suite
5. **Optimize**: Add caching and performance improvements

## 📚 Additional Resources

- [Alpaca API Documentation](https://alpaca.markets/docs/)
- [Alpaca Python SDK](https://github.com/alpacahq/alpaca-trade-api-python)
- [Market Data API Reference](https://alpaca.markets/docs/api-documentation/api-v2/market-data/)

---

This guide provides the complete roadmap for implementing Alpaca backtesting in your system. The existing architecture is well-designed and only needs these specific components to be production-ready.
