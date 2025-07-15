def detect_cisd_signals(candles: List[Dict], lookback: int = 50) -> List[Dict]:
    signals = []

    for i in range(lookback, len(candles)):
        current = candles[i]
        previous = candles[i - 1]

        # Find recent swing highs/lows in lookback window
        recent_swing_highs = [
            c for j, c in enumerate(candles[i - lookback:i])
            if c.get("potential_swing_high")
        ]
        recent_swing_lows = [
            c for j, c in enumerate(candles[i - lookback:i])
            if c.get("potential_swing_low")
        ]

        # Bullish CISD: close above body of previous swing high
        for swing in reversed(recent_swing_highs):
            body_high = max(swing["open"], swing["close"])
            if current["close"] > body_high:
                signals.append({
                    "type": "bullish_cisd",
                    "timestamp": current["timestamp"],
                    "index": i,
                    "reference_swing_timestamp": swing["timestamp"],
                    "zone": [body_high, current["close"]],
                })
                break

        # Bearish CISD: close below body of previous swing low
        for swing in reversed(recent_swing_lows):
            body_low = min(swing["open"], swing["close"])
            if current["close"] < body_low:
                signals.append({
                    "type": "bearish_cisd",
                    "timestamp": current["timestamp"],
                    "index": i,
                    "reference_swing_timestamp": swing["timestamp"],
                    "zone": [current["close"], body_low],
                })
                break

    return signals
