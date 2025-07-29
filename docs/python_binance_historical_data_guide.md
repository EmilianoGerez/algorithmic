# Python‑Binance Historical Data Guide

> **Purpose**  Enable deterministic back‑tests using raw candles pulled directly from Binance Futures (or Spot) with the *official* **python‑binance** SDK. This guide covers installation, data extraction, CSV generation that matches the engine’s loader spec, plus acceptance tests to guarantee consistency.

---

## 1  Install & set up

```bash
pip install python-binance pandas tqdm
```

Create `.env` (or export in shell):

```
BINANCE_API_KEY=YOUR_TESTNET_KEY
BINANCE_API_SECRET=YOUR_TESTNET_SECRET
```

*Spot data doesn’t require keys, but authenticated calls lift weight limits and let you query **`fapi`** endpoints for Futures.*

---

## 2  Single‑symbol extractor script

Save as `scripts/fetch_binance_klines.py`:

```python
import os, csv, time, argparse, datetime as dt
from pathlib import Path
from binance import Client
from tqdm import tqdm

TF_MAP = {"1m": 60_000, "3m": 180_000, "5m": 300_000,
          "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000,
          "1d": 86_400_000}

def iso(t_ms):
    return dt.datetime.utcfromtimestamp(t_ms/1000).strftime("%Y-%m-%dT%H:%M:%SZ")

def fetch(symbol: str, tf: str, start: str, end: str, outfile: Path, futures: bool):
    api_key, api_secret = os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET")
    client = Client(api_key, api_secret, testnet=futures)
    kl_func = client.futures_klines if futures else client.get_historical_klines
    ms = TF_MAP[tf]
    start_ms = int(dt.datetime.fromisoformat(start).timestamp()*1000)
    end_ms   = int(dt.datetime.fromisoformat(end).timestamp()*1000)

    outfile.parent.mkdir(exist_ok=True)
    with outfile.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp","open","high","low","close","volume"])
        pbar = tqdm(total=(end_ms-start_ms)//ms)
        while start_ms < end_ms:
            chunk = kl_func(symbol=symbol, interval=tf, start_str=start_ms,
                            end_str=min(start_ms+ms*1000, end_ms), limit=1000)
            if not chunk:
                break
            for k in chunk:
                w.writerow([iso(k[0]), k[1], k[2], k[3], k[4], k[5]])
            start_ms = chunk[-1][0] + ms
            pbar.update(len(chunk))
            time.sleep(0.2)  # weight cushion
        pbar.close()
    print("Saved", outfile)

if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("symbol")
    a.add_argument("tf", choices=TF_MAP.keys())
    a.add_argument("start")
    a.add_argument("end")
    a.add_argument("--futures", action="store_true")
    args = a.parse_args()
    out = Path(f"data/{args.symbol}_{args.tf}_{args.start[:10]}.csv")
    fetch(args.symbol.upper(), args.tf, args.start, args.end, out, args.futures)
```

Usage example:

```bash
python scripts/fetch_binance_klines.py BTCUSDT 5m 2025-05-15T00:00:00 2025-05-20T00:00:00 --futures
```

This creates `data/BTCUSDT_5m_2025-05-15.csv` with **UTC ISO timestamps** and the column order expected by the loader.

---

## 3  Batch / multi‑month downloads

Binance bulk ZIPs deliver day‑files:

```bash
wget https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/5m/BTCUSDT-5m-2025-05-15.zip
unzip BTCUSDT-5m-2025-05-15.zip -d data/raw
```

Combine:

```python
import glob, pandas as pd, pathlib
files = sorted(glob.glob('data/raw/BTCUSDT-5m-2025-05-*.csv'))
frames = [pd.read_csv(f, header=None, usecols=range(6),
          names=['timestamp','open','high','low','close','volume']) for f in files]
all_bars = pd.concat(frames)
all_bars['timestamp'] = pd.to_datetime(all_bars['timestamp'], unit='ms').dt.strftime('%Y-%m-%dT%H:%M:%SZ')
all_bars.to_csv('data/BTCUSDT_5m_May2025.csv', index=False)
```

---

## 4  Config example

```yaml
# configs/htf_5m_binance.yaml
feeds:
  base_tf: 5m
  source: csv
  path: data/BTCUSDT_5m_2025-05-15.csv

aggregation:
  source_tf_minutes: 5
  target_timeframes_minutes: [240, 1440]
  fill_missing: "ffill"   # gap‑fill for any missing slots

execution:
  mode: backtest
  broker: paper
```

Run:

```bash
quantbt run data/BTCUSDT_5m_2025-05-15.csv \
        --config configs/htf_5m_binance.yaml --plot
```

---

## 5  Acceptance tests

Create `tests/integration/test_binance_csv.py`:

```python
import pandas as pd, subprocess, os, pytest, pathlib, yaml
from services.runner import BacktestRunner

def test_binance_csv_pipeline(tmp_path):
    # 1) generate a tiny slice (5 hours) via script
    outcsv = tmp_path/"slice.csv"
    subprocess.check_call([
        "python","scripts/fetch_binance_klines.py","BTCUSDT","5m",
        "2025-05-19T00:00:00","2025-05-19T05:00:00","--futures",
        "--output", str(outcsv)
    ])
    bars = pd.read_csv(outcsv)
    assert set(bars.columns)=={"timestamp","open","high","low","close","volume"}
    # 2) run back‑test
    cfg = yaml.safe_load(open("configs/tests/min_backtest.yaml"))
    cfg["data"]["path"] = str(outcsv)
    runner = BacktestRunner(cfg, out_dir=tmp_path)
    res = runner.run()
    # 3) acceptance: at least 1 pool created and strategy runs without error
    assert res.total_pools >= 1
```

Add small `configs/tests/min_backtest.yaml` that disables volume filter and uses H4 only.

CI now guarantees new data loader paths stay green.

---

## 6  Rate‑limit & clock drift tips

- Binance weight limit: 1 200 / min on API key. With `limit=1000` & 0.2 s sleep you stay at \~300.
- Futures testnet sometimes lags; catch `-1021 Timestamp for this request was 1000ms ahead` → call `client.futures_time()` and adjust epoch.

---

## 7  Next‑level enhancements

| Idea                       | Benefit                                                         |
| -------------------------- | --------------------------------------------------------------- |
| **Async fetcher using **`` | 4–6× faster multi‑symbol pulls while respecting weight.         |
| **Store as Parquet**       | 60 % smaller, faster Pandas load; loader already reads Parquet. |
| **Incremental updater**    | Cron script appends yesterday’s file daily.                     |

---

Created 30 Jul 2025 • v0.1

