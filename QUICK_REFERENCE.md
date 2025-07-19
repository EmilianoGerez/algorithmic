# QUICK REFERENCE GUIDE

**For Future LLMs and Developers**
**Last Updated**: July 18, 2025
**Version**: 3.0.0

---

## 🚀 QUICK START COMMANDS

### Project Setup

```bash
# Clone and setup environment
git clone <repository>
cd algorithmic
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Run tests to verify setup
python test_phase3_system.py
```

### Development Workflow

```bash
# Start development server
cd api && python main.py

# Run demo systems
python demo_phase3_system.py       # Complete system demo
python demo_phase2_system.py       # Integration demo
python demo_core_system.py         # Core system demo

# Run tests
python test_phase3_system.py       # Phase 3 tests
python test_complete_system.py     # Full system tests
```

### Code Quality

```bash
# Format code
black --line-length 100 .
isort --profile black .

# Run linting
flake8 core/ api/ scripts/

# Type checking
mypy core/ --ignore-missing-imports
```

---

## 📁 KEY FILES TO UNDERSTAND

### Essential Reading Order

1. **PROJECT_MANIFEST.md** - Complete project overview (this is the master document)
2. **PHASE3_COMPLETE_SUMMARY.md** - Current system state
3. **core/**init**.py** - Core exports and structure
4. **core/data/models.py** - Domain models
5. **core/strategies/fvg_strategy.py** - Main trading strategy
6. **api/main.py** - API interface

### Architecture Files

```
core/
├── data/models.py           # 🏗️ Domain models (START HERE)
├── strategies/base_strategy.py  # 🧠 Strategy framework
├── live/__init__.py         # 🔥 Live trading engine
├── streaming/__init__.py    # 📡 Real-time data
├── risk/__init__.py         # 🛡️ Risk management
└── backtesting/__init__.py  # 🔄 Backtesting engine
```

### Demo & Test Files

```
demo_phase3_system.py        # 🎯 Best place to see system in action
test_phase3_system.py        # 🧪 Comprehensive tests
demo_core_system.py          # 📚 Core concepts demonstration
```

---

## 🔧 COMMON DEVELOPMENT TASKS

### Adding a New Strategy

1. **Create strategy file**: `core/strategies/my_strategy.py`
2. **Inherit from BaseStrategy**: Implement required methods
3. **Register strategy**: Use `@register_strategy` decorator
4. **Create configuration**: Factory function for strategy config
5. **Add tests**: Test file with strategy validation
6. **Update exports**: Add to `core/strategies/__init__.py`

```python
# Template for new strategy
from .base_strategy import BaseStrategy, register_strategy

@register_strategy
class MyStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)

    def initialize(self):
        # Strategy initialization
        pass

    def generate_signals(self, market_data):
        # Signal generation logic
        return []

    def validate_signal(self, signal):
        # Signal validation
        return True

    def get_required_timeframes(self):
        return [TimeFrame.MINUTE_15]

    def get_required_history_length(self):
        return 100
```

### Adding a New Data Adapter

1. **Create adapter file**: `core/data/adapters/my_adapter.py`
2. **Inherit from DataAdapter**: Implement required methods
3. **Register adapter**: Add to `DataAdapterFactory`
4. **Add tests**: Test data retrieval and formatting
5. **Update documentation**: Add to adapter list

### Adding New API Endpoints

1. **Create route file**: `api/routes/my_routes.py`
2. **Define Pydantic models**: Request/response models
3. **Implement endpoints**: Async functions with proper error handling
4. **Add to main app**: Include router in `api/main.py`
5. **Test endpoints**: API integration tests

---

## 🧪 TESTING GUIDELINES

### Test Structure

```
tests/
├── unit/              # Unit tests for individual components
├── integration/       # Integration tests for component interaction
├── system/           # End-to-end system tests
└── fixtures/         # Test data and fixtures
```

### Writing Tests

```python
# Example test structure
import pytest
from core import FVGStrategy, create_fvg_strategy_config

@pytest.mark.asyncio
async def test_strategy_signal_generation():
    """Test that strategy generates valid signals."""
    # Arrange
    config = create_fvg_strategy_config("EURUSD")
    strategy = FVGStrategy(config)
    market_data = create_test_market_data()

    # Act
    signals = strategy.generate_signals(market_data)

    # Assert
    assert len(signals) >= 0
    for signal in signals:
        assert strategy.validate_signal(signal)
```

### Test Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest test_phase3_system.py -v

# Run with coverage
pytest --cov=core --cov-report=html

# Run async tests
pytest -k "async" --asyncio-mode=auto
```

---

## 📊 MONITORING & DEBUGGING

### System Health Checks

```python
# Check API health
curl http://localhost:8000/health

# Check WebSocket connection
wscat -c ws://localhost:8000/ws

# Check system status
curl http://localhost:8000/system/status
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debugger
python -m pdb demo_phase3_system.py

# API debug mode
uvicorn api.main:app --reload --log-level debug
```

### Performance Monitoring

```python
# Monitor live trading
curl http://localhost:8000/trading/status

# Monitor portfolio
curl http://localhost:8000/portfolio/summary

# Monitor positions
curl http://localhost:8000/positions
```

---

## 🔐 CONFIGURATION MANAGEMENT

### Environment Variables

```bash
# Required variables
DATABASE_URL=postgresql://user:pass@localhost/trading_db
REDIS_URL=redis://localhost:6379

# Optional variables
API_KEY_ALPACA=your_alpaca_key
SECRET_KEY_ALPACA=your_alpaca_secret
JWT_SECRET=your_jwt_secret
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### Configuration Files

- **alembic.ini**: Database migration settings
- **requirements.txt**: Python dependencies
- **.env**: Environment-specific variables
- **api/config.py**: API configuration settings

---

## 🚨 TROUBLESHOOTING

### Common Issues

#### Import Errors

```python
# Problem: ModuleNotFoundError
# Solution: Add project root to Python path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

#### Database Issues

```bash
# Problem: Database connection errors
# Solution: Run migrations
alembic upgrade head

# Reset database
alembic downgrade base
alembic upgrade head
```

#### API Issues

```bash
# Problem: API not starting
# Solution: Check port availability
lsof -i :8000

# Check environment variables
env | grep -E "(DATABASE|REDIS|API_KEY)"
```

#### WebSocket Issues

```bash
# Problem: WebSocket connection failures
# Solution: Check firewall and ports
netstat -tlnp | grep :8000

# Test WebSocket manually
wscat -c ws://localhost:8000/ws
```

### Debug Techniques

1. **Enable debug logging**: Set `LOG_LEVEL=DEBUG`
2. **Use debugger**: `python -m pdb script.py`
3. **Check logs**: Monitor application logs
4. **Verify configuration**: Check environment variables
5. **Test components**: Run individual component tests

---

## 📈 PERFORMANCE OPTIMIZATION

### Code Optimization

```python
# Use async/await for I/O operations
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Use proper data structures
from collections import deque
recent_candles = deque(maxlen=100)  # Fixed-size queue

# Cache expensive operations
from functools import lru_cache
@lru_cache(maxsize=128)
def calculate_indicators(candles):
    # Expensive calculation
    pass
```

### Database Optimization

```python
# Use database indexes
# Create index on frequently queried columns
CREATE INDEX idx_candles_symbol_time ON candles(symbol, timestamp);

# Use connection pooling
from sqlalchemy import create_engine
engine = create_engine(url, pool_size=10, max_overflow=20)
```

### Memory Management

```python
# Use generators for large datasets
def process_candles(candles):
    for candle in candles:
        yield process_single_candle(candle)

# Clean up resources
async def cleanup():
    await broker.disconnect()
    await streaming_manager.stop()
```

---

## 🎯 PRODUCTION DEPLOYMENT

### Pre-deployment Checklist

- [ ] All tests passing (100% coverage)
- [ ] Environment variables configured
- [ ] Database migrations up to date
- [ ] SSL certificates configured
- [ ] Monitoring and logging setup
- [ ] Backup and recovery procedures
- [ ] Performance testing completed

### Docker Deployment

```dockerfile
# Dockerfile example
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: "3.8"
services:
  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    environment:
      - DATABASE_URL=postgresql://user:pass@db/trading_db
      - REDIS_URL=redis://redis:6379

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=trading_db
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass

  redis:
    image: redis:7-alpine
```

---

## 📚 ADDITIONAL RESOURCES

### Documentation

- **OpenAPI Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Architecture Diagrams**: In docs/ folder
- **Strategy Guides**: Strategy-specific documentation

### External Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **SQLAlchemy Documentation**: https://docs.sqlalchemy.org/
- **Pydantic Documentation**: https://docs.pydantic.dev/
- **Async Python**: https://docs.python.org/3/library/asyncio.html

### Community

- **Issues**: Use GitHub issues for bugs and feature requests
- **Discussions**: Use GitHub discussions for questions
- **Code Review**: All PRs require code review
- **Documentation**: Update docs with any changes

---

**END OF QUICK REFERENCE**

_This guide provides essential information for working with the algorithmic trading system. Refer to PROJECT_MANIFEST.md for comprehensive details._
