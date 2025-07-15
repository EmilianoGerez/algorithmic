from typing import List, Dict

def detect_swing_points(candles: List[Dict], lookback: int = 3) -> List[Dict]:
    result = []

    for i in range(len(candles)):
        swing_high = swing_low = False
        if i >= lookback and i < len(candles) - lookback:
            high = candles[i]["high"]
            low = candles[i]["low"]
            highs = [candles[j]["high"] for j in range(i - lookback, i + lookback + 1)]
            lows = [candles[j]["low"] for j in range(i - lookback, i + lookback + 1)]
            if high == max(highs): swing_high = True
            if low == min(lows): swing_low = True

        result.append({
            **candles[i],
            "swing_high": swing_high,
            "swing_low": swing_low,
        })
    return result
