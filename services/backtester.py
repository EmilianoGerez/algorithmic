"""Very small CLI backtester stub."""

import argparse
import asyncio
import csv
from datetime import datetime

from core.entities import Candle
from core.indicators.ema import EMA


async def csv_reader(path: str):
    with open(path, newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            yield Candle(
                ts=datetime.fromisoformat(row["timestamp"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )


async def run(file: str):
    ema21, ema50 = EMA(21), EMA(50)
    async for cdl in csv_reader(file):
        ema21.update(cdl)
        ema50.update(cdl)
        # Example print
        if ema21.value and ema50.value and ema21.value > ema50.value:
            print(cdl.ts, "EMA bull bias")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.file))
