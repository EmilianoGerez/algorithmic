# Quant Algorithm Skeleton

Minimal starting point for the multi‑time‑frame liquidity‑pool strategy.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set up pre-commit hooks for code quality (recommended)
./setup-precommit.sh

python -m services.backtester --file sample_data/your_file.csv
```

Next steps:

1. Implement TimeAggregator inside `core/strategy`.
2. Flesh out FVG & Pivot detectors.
3. Build ZoneWatcher & FSM.
4. Add broker integration in `infra/brokers`.

Refer to the `Quant Algorithm Platform – Technical Blueprint` notebook for full specs.

## Development

### Code Quality

This project uses automated code quality checks:

- **Pre-commit hooks**: Run `./setup-precommit.sh` to install (see [PRE-COMMIT.md](PRE-COMMIT.md))
- **Linting**: Ruff with auto-fixing
- **Formatting**: Ruff formatter
- **Type checking**: MyPy in strict mode
- **Testing**: Pytest with coverage

### Running Checks Manually

```bash
# All quality checks
.venv/bin/pre-commit run --all-files

# Individual tools
.venv/bin/ruff check . --fix
.venv/bin/ruff format .
.venv/bin/mypy core/ --strict
.venv/bin/pytest tests/ -v
```
