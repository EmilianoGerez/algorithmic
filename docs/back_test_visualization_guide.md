# Back‑test Visualization Guide

> *Goal*: Show candles + FVG zones (+ optional Pivots & trade marks) for any back‑test run. Works in three contexts: (1) quick PNG, (2) interactive Plotly, (3) inline ChatGPT via `--plot` flag.
>
> *Prereqs*: `results/<run‑dir>/` contains `data.csv`, `trades.csv`, `events.parquet`.

---

## 1  Quick static chart (mplfinance)

### 1.1 Install

```bash
pip install mplfinance
```

### 1.2 Script – `scripts/plot_static.py`

```python
import pandas as pd, mplfinance as mpf, pathlib, datetime as dt
run = pathlib.Path('results')/max(pathlib.Path('results').iterdir())  # latest run dir

bars   = pd.read_csv(run/'data.csv', index_col='timestamp', parse_dates=True)
trades = pd.read_csv(run/'trades.csv')
events = pd.read_parquet(run/'events.parquet')

fvg_rects = [dict(x0=row.ts,
                  x1=row.ts+pd.Timedelta('2h'),
                  y0=row.bottom, y1=row.top,
                  facecolor='cornflowerblue', alpha=.15)
             for _, row in events.query("type=='FVGEvent'").iterrows()]

plots = [mpf.make_addplot(trades['entry_price'], type='scatter', marker='^', color='lime', markersize=70),
         mpf.make_addplot(trades['exit_price'],  type='scatter', marker='x', color='red',  markersize=70)]

mpf.plot(bars, type='candle', addplot=plots, alines=fvg_rects,
         style='yahoo', figratio=(16,9), tight_layout=True,
         title=f"{run.name} – FVG & Trades")
```

Run:

```bash
python scripts/plot_static.py  # pops a PNG window or savefig if headless
```

---

## 2  Interactive Plotly notebook

### 2.1 Install

```bash
pip install plotly pandas
```

### 2.2 Notebook cell

```python
import pandas as pd, plotly.graph_objects as go, pathlib, datetime as dt
run = pathlib.Path('results/2025-07-30T12-45-01_git3e5f')

bars   = pd.read_csv(run/'data.csv')
trades = pd.read_csv(run/'trades.csv')
events = pd.read_parquet(run/'events.parquet')

fig = go.Figure(go.Candlestick(x=bars['timestamp'], open=bars['open'],
                               high=bars['high'], low=bars['low'], close=bars['close']))
# FVG bands
for _, r in events.query("type=='FVGEvent'").iterrows():
    fig.add_shape(type='rect', x0=r.ts, x1=pd.to_datetime(r.ts)+pd.Timedelta('2H'),
                  y0=r.bottom, y1=r.top,
                  fillcolor='rgba(0,120,255,0.15)', line=dict(width=0))
# Trades
fig.add_trace(go.Scatter(x=trades['entry_ts'], y=trades['entry_price'], mode='markers',
                         name='Entry', marker_symbol='triangle-up', marker_size=12, marker_color='lime'))
fig.add_trace(go.Scatter(x=trades['exit_ts'], y=trades['exit_price'], mode='markers',
                         name='Exit', marker_symbol='x', marker_size=12, marker_color='red'))
fig.update_layout(height=800,title='Interactive Back‑test Chart')
fig.show()
```

*Hover*, *zoom*, *toggle traces*.

---

## 3  Inline chart via `--plot` flag (ChatGPT only)

### 3.1 Extend CLI (`cli.py`)

```python
if args.plot:
    from quant_algo.visual.plot_builder import build_plotly
    fig = build_plotly(run_ctx)
    if os.getenv('CHATGPT_ENV') == '1':
        from python_user_visible import display_plotly
        display_plotly(fig)            # renders in chat
    else:
        fig.write_image(run_ctx.out_dir/'equity.png')
```

### 3.2 Helper – `quant_algo/visual/plot_builder.py`

```python
import pandas as pd, plotly.graph_objects as go

def build_plotly(run_ctx):
    bars   = pd.read_csv(run_ctx.data_path)
    trades = pd.read_csv(run_ctx.trades_path)
    events = pd.read_parquet(run_ctx.events_path)
    # (reuse code above, return fig)
```

Run:

```bash
CHATGPT_ENV=1 quantbt run data/BTC_5m.csv --config … --plot
```

Inside ChatGPT the interactive Plotly appears; in CI a PNG is saved.

---

## 4  Overlay key-map

| Layer | Source event               | Visual                            |
| ----- | -------------------------- | --------------------------------- |
| FVG   | `FVGEvent`                 | Semi‑transparent rectangle        |
| Pivot | `PivotEvent`               | Horizontal dotted line at `price` |
| Entry | `TradingSignal` (side=BUY) | Green ▲ marker                    |
| Exit  | OrderReceipt exit          | Red × marker                      |

---

## 5  Troubleshooting

| Issue                                | Fix                                                                                  |
| ------------------------------------ | ------------------------------------------------------------------------------------ |
| `events.parquet` missing             | run back-test with `runtime.dump_events: true`                                       |
| Timestamps mis‑align                 | ensure `data.date_format` matches file; ISO UTC recommended                          |
| Plotly “figure too large” in ChatGPT | Slice run dataset (e.g. `--limit-bars 2000`) or down‑sample bars before building fig |

---

*Guide version 0.1 – 30 Jul 2025*

