from datetime import datetime, timedelta
from typing import List, Dict, Literal
from src.db.models.fvg import FVG as FVGModel
from src.db.models.pivot import Pivot
from sqlalchemy.orm import Session


def is_cisd(candle: Dict, pivots: List[Pivot], direction: Literal["bullish", "bearish"]) -> bool:
    """
    CISD = candle closes beyond the body of last pivot (swing high/low)
    """
    if direction == "bullish":
        highs = [p for p in pivots if p.type == "high"]
        if not highs:
            return False
        last_high = sorted(highs, key=lambda x: x.timestamp)[-1]
        return candle["close"] > last_high.price

    else:
        lows = [p for p in pivots if p.type == "low"]
        if not lows:
            return False
        last_low = sorted(lows, key=lambda x: x.timestamp)[-1]
        return candle["close"] < last_low.price


def detect_fvg_sweep_cisd(
    symbol: str,
    candles_15m: List[Dict],
    db: Session,
    timeframe_4h: str = "1D",
) -> List[Dict]:
    """
    Detect signal when 15m candle enters an open 4H FVG and performs CISD.
    """
    signals = []

    # Load open FVGs in 4H
    open_fvgs: List[FVGModel] = db.query(FVGModel).filter(
        FVGModel.symbol == symbol,
        FVGModel.timeframe == timeframe_4h,
        FVGModel.status == "open"
    ).all()

    # Parse timestamp and compute lookback window
    lookback_start = datetime.fromisoformat(candles_15m[0]["timestamp"].replace("Z", "")) - timedelta(days=3)

    # Load recent pivots in 15m for CISD check
    recent_pivots: List[Pivot] = db.query(Pivot).filter(
        Pivot.symbol == symbol,
        Pivot.timeframe == "15T",
        Pivot.timestamp >= lookback_start
    ).all()

    for candle in candles_15m:
        ts = candle["timestamp"]

        for fvg in open_fvgs:
            if fvg.zone_low <= candle["high"] and fvg.zone_high >= candle["low"]:
                # Enters the FVG zone
                direction = fvg.direction
                if is_cisd(candle, recent_pivots, direction):
                    signals.append({
                        "symbol": symbol,
                        "timeframe": "15T",
                        "timestamp": ts,
                        "type": "fvg_sweep_cisd",
                        "fvg_id": str(fvg.id),
                        "direction": direction,
                    })

    return signals
