from typing import List, Dict

def detect_fvg(candles: List[Dict]) -> List[Dict]:
    result = []

    for i in range(len(candles)):
        fvg_bullish = False
        fvg_bearish = False
        fvg_zone = None

        if i >= 1 and i < len(candles) - 1:
            c_prev = candles[i - 1]
            c_next = candles[i + 1]

            # Bullish FVG: previous high < next low
            if c_prev["high"] < c_next["low"]:
                fvg_bullish = True
                fvg_zone = [c_prev["high"], c_next["low"]]

            # Bearish FVG: previous low > next high
            if c_prev["low"] > c_next["high"]:
                fvg_bearish = True
                fvg_zone = [c_next["high"], c_prev["low"]]

        result.append({
            **candles[i],
            "fvg_bullish": fvg_bullish,
            "fvg_bearish": fvg_bearish,
            "fvg_zone": fvg_zone
        })

    return result

