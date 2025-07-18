# Development Guide

This guide covers development practices, testing, and code quality standards for the algorithmic trading system.

## 🛠️ Development Environment Setup

### Initial Setup

```bash
# Clone and setup environment
git clone <repository>
cd algorithmic
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r dev-requirements.txt

# Install pre-commit hooks
pre-commit install
```

### Development Dependencies

The project uses comprehensive development tooling:

- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **pytest-mock**: Mocking utilities
- **pytest-asyncio**: Async test support
- **black**: Code formatting
- **isort**: Import sorting
- **flake8**: PEP8 linting
- **pylint**: Advanced code analysis
- **mypy**: Static type checking
- **bandit**: Security vulnerability scanning
- **pre-commit**: Git hook management

## 🧪 Testing Strategy

### Test Structure

```
tests/
├── unit/                           # Unit tests (fast, isolated)
│   ├── test_data_models.py            # Data model validation
│   ├── test_fvg_detection.py          # FVG algorithm tests
│   └── test_*.py                      # Other unit tests
├── integration/                    # Integration tests (slower, E2E)
│   └── test_fvg_system_integration.py # System integration tests
├── fixtures/                       # Test data and fixtures
│   ├── market_data.json               # Sample market data
│   └── test_configs.py                # Test configurations
└── conftest.py                     # Shared test configuration
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=core --cov-report=html --cov-report=term

# Run specific categories
python -m pytest tests/unit/                # Unit tests only
python -m pytest tests/integration/         # Integration tests only

# Run specific test files
python -m pytest tests/unit/test_data_models.py

# Run specific test methods
python -m pytest tests/unit/test_data_models.py::TestCandle::test_candle_creation

# Run tests in parallel
python -m pytest -n auto

# Run tests with detailed output
python -m pytest -v -s
```

### Test Configuration

Tests are configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--strict-markers",
    "--tb=short",
    "--cov=core",
    "--cov-branch",
    "--cov-report=term-missing",
    "--cov-fail-under=80"
]
```

### Writing Tests

#### Unit Test Example

```python
# tests/unit/test_example.py
import pytest
from decimal import Decimal
from datetime import datetime
from core.data.models import Candle, TimeFrame

class TestCandle:
    """Test cases for Candle model."""

    def test_candle_creation(self):
        """Test basic candle creation."""
        candle = Candle(
            timestamp=datetime(2025, 1, 1, 9, 0),
            open=Decimal('50000'),
            high=Decimal('50100'),
            low=Decimal('49900'),
            close=Decimal('50050'),
            volume=Decimal('1000'),
            symbol="BTCUSD",
            timeframe=TimeFrame.MINUTE_1
        )

        assert candle.open == Decimal('50000')
        assert candle.symbol == "BTCUSD"
```

#### Integration Test Example

```python
# tests/integration/test_system.py
import pytest
from core.system import TradingSystem

class TestSystemIntegration:
    """Integration tests for trading system."""

    @pytest.mark.asyncio
    async def test_end_to_end_flow(self, mock_data_feed):
        """Test complete trading flow."""
        system = TradingSystem()
        await system.start()

        # Test system behavior
        result = await system.process_market_data(mock_data_feed)

        assert result.success
        await system.stop()
```

### Test Fixtures

Common test fixtures are defined in `tests/conftest.py`:

```python
@pytest.fixture
def sample_candles():
    """Sample candle data for testing."""
    # Returns list of sample candles

@pytest.fixture
def mock_fvg_detector():
    """Mock FVG detector for testing."""
    # Returns configured mock detector
```

## 🎯 Code Quality Standards

### Automated Formatting

```bash
# Format code
black .

# Sort imports
isort .

# Combined formatting
black . && isort .
```

### Linting and Analysis

```bash
# Basic linting
flake8 .

# Advanced analysis
pylint core/

# Type checking
mypy core/

# Security scanning
bandit -r core/
```

### Pre-commit Hooks

The project uses pre-commit hooks that run automatically on commit:

- Code formatting (black, isort)
- Linting (flake8, pylint)
- Type checking (mypy)
- Security scanning (bandit)
- Test execution

### Configuration Files

#### `.pre-commit-config.yaml`

Configures pre-commit hooks for automated quality checks.

#### `pyproject.toml`

Central configuration for:

- Black formatting
- isort import sorting
- MyPy type checking
- Pytest test configuration
- Coverage reporting

#### `.pylintrc`

Pylint configuration with project-specific rules.

## 🚀 CI/CD Pipeline

### GitHub Actions Workflow

The project includes a comprehensive CI/CD pipeline (`.github/workflows/ci.yml`) with multiple stages:

1. **Setup**: Python environment and dependencies
2. **Quality Checks**: Formatting, linting, type checking
3. **Security**: Vulnerability scanning
4. **Testing**: Unit and integration tests with coverage
5. **Build**: Package verification

### Pipeline Configuration

```yaml
name: CI/CD Pipeline

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r dev-requirements.txt
      - name: Run quality checks
        run: |
          black --check .
          isort --check-only .
          flake8 .
          pylint core/
          mypy core/
          bandit -r core/
      - name: Run tests
        run: |
          pytest --cov=core --cov-fail-under=80
```

### Quality Gates

The pipeline enforces quality gates:

- Code formatting compliance
- Linting without errors
- Type checking passes
- Security scan clean
- Test coverage ≥ 80%
- All tests passing

## 📊 Development Metrics

### Coverage Targets

- **Overall Coverage**: ≥ 80%
- **Core Modules**: ≥ 85%
- **Critical Paths**: ≥ 90%

### Performance Targets

- **Unit Tests**: < 5 seconds total
- **Integration Tests**: < 30 seconds total
- **Full Pipeline**: < 5 minutes

## 🔍 Debugging and Troubleshooting

### Common Issues

#### Import Errors

```bash
# Add project root to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### Test Discovery Issues

```bash
# Verify test collection
python -m pytest --collect-only
```

#### Coverage Issues

```bash
# Generate detailed coverage report
python -m pytest --cov=core --cov-report=html
open htmlcov/index.html
```

### Debug Configuration

For VS Code debugging, use this configuration in `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    },
    {
      "name": "Python: Pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["${workspaceFolder}/tests", "-v"],
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

## 📝 Best Practices

### Code Organization

- Keep modules focused and cohesive
- Use dependency injection for testability
- Follow SOLID principles
- Implement proper error handling
- Use type hints consistently

### Testing Best Practices

- Write tests before or alongside code (TDD)
- Keep tests simple and focused
- Use descriptive test names
- Mock external dependencies
- Test edge cases and error conditions
- Maintain high test coverage

### Git Workflow

- Use descriptive commit messages
- Keep commits small and focused
- Run tests before committing
- Use feature branches for development
- Submit pull requests for code review

### Documentation

- Keep README.md updated
- Document API changes
- Include examples in docstrings
- Update changelog for releases
- Maintain architectural documentation

---

For more information, see the [PROJECT_MANIFEST.md](PROJECT_MANIFEST.md) for complete project overview.
