from typing import List, Dict


def detect_pivots(candles: List[Dict], lookback: int = 3) -> List[Dict]:
    """
    Detect potential swing highs and lows (pivot points).
    These are not yet confirmed HH/LLs in market structure.
    
    Returns candles with potential_swing_high/low flags.
    """
    result = []

    for i in range(len(candles)):
        pivot_high = pivot_low = False

        if i >= lookback and i < len(candles) - lookback:
            high = candles[i]["high"]
            low = candles[i]["low"]

            is_high = all(high > candles[j]["high"] for j in range(i - lookback, i + lookback + 1) if j != i)
            is_low = all(low < candles[j]["low"] for j in range(i - lookback, i + lookback + 1) if j != i)

            if is_high:
                pivot_high = True
            if is_low:
                pivot_low = True

        result.append({
            **candles[i],
            "potential_swing_high": pivot_high,
            "potential_swing_low": pivot_low,
        })

    return result
