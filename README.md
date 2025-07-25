# Quant Algorithm Skeleton

Minimal starting point for the multi‑time‑frame liquidity‑pool strategy.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m services.backtester --file sample_data/your_file.csv
```

Next steps:

1. Implement TimeAggregator inside `core/strategy`.
2. Flesh out FVG & Pivot detectors.
3. Build ZoneWatcher & FSM.
4. Add broker integration in `infra/brokers`.

Refer to the `Quant Algorithm Platform – Technical Blueprint` notebook for full specs.
