from typing import List, Dict
import uuid


def track_fvg_status(candles: List[Dict], fvg_candidates: List[Dict], max_lookahead: int = 20) -> List[Dict]:
    tracked_fvgs = []

    for i, candle in enumerate(fvg_candidates):
        if not candle.get("fvg_zone"):
            continue

        fvg_id = f"fvg_{i}_{uuid.uuid4().hex[:6]}"
        zone_low, zone_high = sorted(candle["fvg_zone"])
        direction = "bullish" if candle.get("fvg_bullish") else "bearish"
        status = "open"
        invalidated_by = None
        mitigation_by = None
        i_fvg = False
        retested = False
        retested_at = None

        for j in range(i + 1, min(i + max_lookahead + 1, len(candles))):
            future = candles[j]
            open_ = future["open"]
            close = future["close"]
            high = future["high"]
            low = future["low"]

            body_high = max(open_, close)
            body_low = min(open_, close)

            if direction == "bullish":
                # ✅ Only mitigate if candle body overlaps the FVG
                if body_low < zone_high and body_high > zone_low:
                    status = "mitigated"
                    mitigation_by = j
                    break

                # ❌ Invalidate if candle closes below FVG
                if close < zone_low:
                    status = "invalidated"
                    invalidated_by = j
                    if j + 1 < len(candles) and candles[j + 1]["close"] < close:
                        status = "iFVG"
                        i_fvg = True

                        # 🔁 Look for retest after iFVG
                        for k in range(j + 2, min(j + 10, len(candles))):
                            future_retest = candles[k]
                            if future_retest["high"] >= zone_low:
                                retested = True
                                retested_at = future_retest["timestamp"]
                                break
                    break

            else:  # bearish
                if body_low < zone_high and body_high > zone_low:
                    status = "mitigated"
                    mitigation_by = j
                    break

                if close > zone_high:
                    status = "invalidated"
                    invalidated_by = j
                    if j + 1 < len(candles) and candles[j + 1]["close"] > close:
                        status = "iFVG"
                        i_fvg = True

                        for k in range(j + 2, min(j + 10, len(candles))):
                            future_retest = candles[k]
                            if future_retest["low"] <= zone_high:
                                retested = True
                                retested_at = future_retest["timestamp"]
                                break
                    break

        tracked_fvgs.append({
            "fvg_id": fvg_id,
            "index": i,
            "timestamp": candle["timestamp"],
            "zone": [zone_low, zone_high],
            "direction": direction,
            "status": status,
            "invalidated_by": invalidated_by,
            "mitigation_by": mitigation_by,
            "iFVG": i_fvg,
            "retested": retested,
            "retested_at": retested_at,
        })

    return tracked_fvgs
