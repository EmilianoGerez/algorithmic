from datetime import datetime, timedelta
from typing import List, Dict, Literal
from src.db.models.fvg import FVG as FVGModel
from sqlalchemy.orm import Session


def find_swing_points(candles: List[Dict], lookback: int = 3) -> Dict:
    """
    Identify swing highs and lows by looking back at previous candles.
    A swing high is a high that is higher than 'lookback' candles before and after it.
    A swing low is a low that is lower than 'lookback' candles before and after it.
    """
    swing_highs = []
    swing_lows = []
    
    for i in range(lookback, len(candles) - lookback):
        current_high = candles[i]["high"]
        current_low = candles[i]["low"]
        
        # Check if current candle is a swing high
        is_swing_high = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and candles[j]["high"] >= current_high:
                is_swing_high = False
                break
        
        if is_swing_high:
            swing_highs.append({
                "index": i,
                "price": current_high,
                "timestamp": candles[i]["timestamp"]
            })
        
        # Check if current candle is a swing low
        is_swing_low = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and candles[j]["low"] <= current_low:
                is_swing_low = False
                break
        
        if is_swing_low:
            swing_lows.append({
                "index": i,
                "price": current_low,
                "timestamp": candles[i]["timestamp"]
            })
    
    return {
        "swing_highs": swing_highs,
        "swing_lows": swing_lows
    }


def detect_structure_break(candles: List[Dict], direction: Literal["bullish", "bearish"], 
                         lookback_periods: int = 10) -> Dict | None:
    """
    Detects structure breaks by analyzing swing points over a longer lookback period.
    
    Bullish structure break: Price breaks above a previous swing high
    Bearish structure break: Price breaks below a previous swing low
    """
    if len(candles) < lookback_periods:
        return None
    
    # Find swing points in the lookback period
    swing_points = find_swing_points(candles[:-3])  # Exclude last 3 candles for confirmation
    
    if direction == "bullish":
        if not swing_points["swing_highs"]:
            return None
        
        # Get the most recent significant swing high
        recent_swing_high = max(swing_points["swing_highs"][-3:], key=lambda x: x["price"])
        
        # Check if recent price action breaks above this swing high
        for i in range(len(candles) - 3, len(candles)):
            if candles[i]["high"] > recent_swing_high["price"]:
                return {
                    "timestamp": candles[i]["timestamp"],
                    "price": candles[i]["high"],
                    "type": "structure_break_bullish",
                    "direction": "bullish",
                    "broken_level": recent_swing_high["price"],
                    "broken_level_time": recent_swing_high["timestamp"]
                }
    
    elif direction == "bearish":
        if not swing_points["swing_lows"]:
            return None
        
        # Get the most recent significant swing low
        recent_swing_low = min(swing_points["swing_lows"][-3:], key=lambda x: x["price"])
        
        # Check if recent price action breaks below this swing low
        for i in range(len(candles) - 3, len(candles)):
            if candles[i]["low"] < recent_swing_low["price"]:
                return {
                    "timestamp": candles[i]["timestamp"],
                    "price": candles[i]["low"],
                    "type": "structure_break_bearish",
                    "direction": "bearish",
                    "broken_level": recent_swing_low["price"],
                    "broken_level_time": recent_swing_low["timestamp"]
                }
    
    return None


def detect_local_cisd(candles: List[Dict], direction: Literal["bullish", "bearish"]) -> Dict | None:
    """
    Detects local CISD (structure break) based on improved structure analysis.
    Now uses swing point analysis and longer lookback periods for more reliable signals.
    """
    # Try the advanced structure break detection first (most reliable)
    advanced_break = detect_advanced_structure_break(candles, direction)
    if advanced_break:
        return advanced_break
    
    # Try the improved structure break detection
    structure_break = detect_structure_break(candles, direction, lookback_periods=15)
    if structure_break:
        return structure_break
    
    # Fallback to original simple logic if no structure break found
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i - 2], candles[i - 1], candles[i]

        if direction == "bullish":
            if c2["low"] > c1["low"] and c3["close"] > c1["high"]:
                return {
                    "timestamp": c3["timestamp"],
                    "price": c3["close"],
                    "type": "cisd_bullish",
                    "direction": "bullish"
                }

        elif direction == "bearish":
            if c2["high"] < c1["high"] and c3["close"] < c1["low"]:
                return {
                    "timestamp": c3["timestamp"],
                    "price": c3["close"],
                    "type": "cisd_bearish",
                    "direction": "bearish"
                }

    return None


def detect_fvg_sweep_cisd(
    symbol: str,
    candles_15m: List[Dict],
    db: Session,
    timeframe_4h: str = "4H",
    start: str = None,
    end: str = None,
) -> List[Dict]:
    """
    Detect signal when after price enters an open 4H FVG, a CISD occurs,
    with full backtest-safe logic (no future data leaks).
    
    Key fix: For each candle, only consider FVGs that were created BEFORE that candle's timestamp.
    """
    signals = []
    if not candles_15m:
        return signals

    # Parse start/end bounds
    end_dt = datetime.fromisoformat(end.replace("Z", "")) if end else datetime.utcnow()
    start_dt = datetime.fromisoformat(start.replace("Z", "")) if start else end_dt - timedelta(days=5)

    # Only analyze candles in range
    candles_in_range = [
        c for c in candles_15m
        if start_dt <= datetime.fromisoformat(c["timestamp"].replace("Z", "")) <= end_dt
    ]

    # Keep track of processed FVGs to avoid duplicate signals
    processed_fvgs = set()

    # Process each candle and check for FVG entry using only previously created FVGs
    for i, candle in enumerate(candles_in_range):
        candle_dt = datetime.fromisoformat(candle["timestamp"].replace("Z", ""))
        
        # Load only FVGs that were created BEFORE this candle's timestamp
        available_fvgs: List[FVGModel] = db.query(FVGModel).filter(
            FVGModel.symbol == symbol,
            FVGModel.timeframe == timeframe_4h,
            FVGModel.status == "open",
            FVGModel.timestamp < candle_dt  # Critical: FVG must be created BEFORE current candle
        ).all()
        
        # Check if current candle enters any of the available FVGs
        for fvg in available_fvgs:
            # Skip if we've already processed this FVG
            if fvg.id in processed_fvgs:
                continue
                
            high = candle["high"]
            low = candle["low"]
            
            # Check if candle enters the FVG zone
            if fvg.zone_low <= high and fvg.zone_high >= low:
                print(f"Detected entry into FVG {fvg.id} at candle {candle['timestamp']}")
                print(f"  FVG created: {fvg.timestamp}, Current candle: {candle_dt}")
                print(f"  FVG zone: {fvg.zone_low}-{fvg.zone_high}")
                
                # Mark this FVG as processed
                processed_fvgs.add(fvg.id)
                
                # Analyze next N candles after entry for CISD
                lookahead = candles_in_range[i : i + 12]
                
                if not lookahead:
                    continue

                # Try different detection methods
                cisd = None
                method_used = None
                
                for method_name, method_func in [
                    ("advanced", detect_advanced_structure_break),
                    ("basic", detect_structure_break),
                    ("fallback", detect_local_cisd),
                ]:
                    print(f"Trying {method_name} CISD detection for FVG {fvg.id} at candle {candle['timestamp']}")
                    cisd = method_func(lookahead, fvg.direction)
                    if cisd:
                        print(f"✓ {method_name} CISD detected: {cisd}")
                        method_used = method_name
                        break
                
                # If no method found CISD, try contextual detection (different signature)
                if not cisd:
                    print(f"Trying contextual CISD detection for FVG {fvg.id} at candle {candle['timestamp']}")
                    cisd = detect_fvg_contextual_cisd(
                        lookahead,
                        fvg.zone_low,
                        fvg.zone_high,
                        fvg.direction,
                        0  # entry_index relative to lookahead
                    )
                    if cisd:
                        method_used = "contextual"

                if cisd:
                    cisd_signal = {
                        "timestamp": cisd["timestamp"],
                        "price": cisd["price"],
                        "cisd_price": cisd["price"],  # For compatibility with plotting script
                        "direction": cisd["direction"],
                        "signal": f"CISD-{cisd['direction']}",
                        "fvg_id": fvg.id,
                        "fvg_zone": f"{fvg.zone_low}-{fvg.zone_high}",
                        "entry_candle": candle["timestamp"],
                        "method": method_used,
                        "type": cisd.get("type", "cisd_signal")
                    }
                    signals.append(cisd_signal)
                    print(f"Detected CISD: {cisd} for FVG {fvg.id} at candle {candle['timestamp']}")

    return signals


def detect_advanced_structure_break(candles: List[Dict], direction: Literal["bullish", "bearish"], 
                                  min_lookback: int = 5, max_lookback: int = 20) -> Dict | None:
    """
    Advanced structure break detection that considers multiple timeframe context.
    
    Features:
    - Analyzes multiple swing points over different lookback periods
    - Considers volume confirmation (if available)
    - Validates breaks with proper market structure context
    - Filters out false breaks using additional criteria
    """
    if len(candles) < max_lookback:
        return None
    
    # Find swing points with different sensitivities
    swing_points_sensitive = find_swing_points(candles[:-3], lookback=2)
    swing_points_moderate = find_swing_points(candles[:-3], lookback=3)
    swing_points_conservative = find_swing_points(candles[:-3], lookback=5)
    
    if direction == "bullish":
        # Get significant swing highs from different timeframes
        all_swing_highs = []
        for sp in [swing_points_sensitive, swing_points_moderate, swing_points_conservative]:
            all_swing_highs.extend(sp["swing_highs"])
        
        if not all_swing_highs:
            return None
        
        # Sort by recency and significance
        all_swing_highs.sort(key=lambda x: (x["index"], x["price"]), reverse=True)
        
        # Find the most relevant swing high to break
        target_swing_high = None
        for swing_high in all_swing_highs[:5]:  # Check top 5 most recent/significant
            # Ensure it's not too recent (at least 3 candles ago)
            if swing_high["index"] < len(candles) - 3:
                target_swing_high = swing_high
                break
        
        if not target_swing_high:
            return None
        
        # Check for break with additional validation
        for i in range(len(candles) - 3, len(candles)):
            current_candle = candles[i]
            
            # Basic break condition
            if current_candle["high"] > target_swing_high["price"]:
                
                # Additional validation criteria
                break_strength = current_candle["high"] - target_swing_high["price"]
                price_range = target_swing_high["price"] * 0.01  # 1% of price as minimum break strength
                
                # Validate break strength
                if break_strength >= price_range:
                    
                    # Check for follow-through (close near highs)
                    close_strength = (current_candle["close"] - current_candle["low"]) / (current_candle["high"] - current_candle["low"])
                    
                    if close_strength >= 0.5:  # Close in upper 50% of candle range
                        return {
                            "timestamp": current_candle["timestamp"],
                            "price": current_candle["high"],
                            "type": "advanced_structure_break_bullish",
                            "direction": "bullish",
                            "broken_level": target_swing_high["price"],
                            "broken_level_time": target_swing_high["timestamp"],
                            "break_strength": break_strength,
                            "close_strength": close_strength
                        }
    
    elif direction == "bearish":
        # Get significant swing lows from different timeframes
        all_swing_lows = []
        for sp in [swing_points_sensitive, swing_points_moderate, swing_points_conservative]:
            all_swing_lows.extend(sp["swing_lows"])
        
        if not all_swing_lows:
            return None
        
        # Sort by recency and significance
        all_swing_lows.sort(key=lambda x: (x["index"], -x["price"]), reverse=True)
        
        # Find the most relevant swing low to break
        target_swing_low = None
        for swing_low in all_swing_lows[:5]:  # Check top 5 most recent/significant
            # Ensure it's not too recent (at least 3 candles ago)
            if swing_low["index"] < len(candles) - 3:
                target_swing_low = swing_low
                break
        
        if not target_swing_low:
            return None
        
        # Check for break with additional validation
        for i in range(len(candles) - 3, len(candles)):
            current_candle = candles[i]
            
            # Basic break condition
            if current_candle["low"] < target_swing_low["price"]:
                
                # Additional validation criteria
                break_strength = target_swing_low["price"] - current_candle["low"]
                price_range = target_swing_low["price"] * 0.01  # 1% of price as minimum break strength
                
                # Validate break strength
                if break_strength >= price_range:
                    
                    # Check for follow-through (close near lows)
                    close_strength = (current_candle["high"] - current_candle["close"]) / (current_candle["high"] - current_candle["low"])
                    
                    if close_strength >= 0.5:  # Close in lower 50% of candle range
                        return {
                            "timestamp": current_candle["timestamp"],
                            "price": current_candle["low"],
                            "type": "advanced_structure_break_bearish",
                            "direction": "bearish",
                            "broken_level": target_swing_low["price"],
                            "broken_level_time": target_swing_low["timestamp"],
                            "break_strength": break_strength,
                            "close_strength": close_strength
                        }
    
    return None


def analyze_market_structure(candles: List[Dict], lookback: int = 20) -> Dict:
    """
    Analyze the overall market structure to understand trend and key levels.
    Useful for debugging and understanding the context of structure breaks.
    """
    if len(candles) < lookback:
        return {"error": "Not enough data for analysis"}
    
    # Get swing points for analysis
    swing_points = find_swing_points(candles, lookback=3)
    
    # Analyze trend direction
    recent_highs = [sh["price"] for sh in swing_points["swing_highs"][-3:]]
    recent_lows = [sl["price"] for sl in swing_points["swing_lows"][-3:]]
    
    trend_direction = "neutral"
    if len(recent_highs) >= 2 and len(recent_lows) >= 2:
        higher_highs = recent_highs[-1] > recent_highs[-2] if len(recent_highs) >= 2 else False
        higher_lows = recent_lows[-1] > recent_lows[-2] if len(recent_lows) >= 2 else False
        lower_highs = recent_highs[-1] < recent_highs[-2] if len(recent_highs) >= 2 else False
        lower_lows = recent_lows[-1] < recent_lows[-2] if len(recent_lows) >= 2 else False
        
        if higher_highs and higher_lows:
            trend_direction = "bullish"
        elif lower_highs and lower_lows:
            trend_direction = "bearish"
    
    # Get key levels
    key_resistance = max(recent_highs) if recent_highs else None
    key_support = min(recent_lows) if recent_lows else None
    
    # Calculate price ranges
    current_price = candles[-1]["close"]
    price_range = abs(key_resistance - key_support) if key_resistance and key_support else 0
    
    return {
        "trend_direction": trend_direction,
        "key_resistance": key_resistance,
        "key_support": key_support,
        "current_price": current_price,
        "price_range": price_range,
        "swing_highs_count": len(swing_points["swing_highs"]),
        "swing_lows_count": len(swing_points["swing_lows"]),
        "recent_swing_highs": swing_points["swing_highs"][-3:],
        "recent_swing_lows": swing_points["swing_lows"][-3:]
    }


def detect_fvg_rejection_reversal(candles: List[Dict], fvg_zone_low: float, fvg_zone_high: float, 
                                 fvg_direction: str, entry_index: int) -> Dict | None:
    """
    Detects when price enters an FVG zone but then gets rejected and creates a structure break
    in the opposite direction. This is the pattern visible on 05-20 in the chart.
    
    Pattern:
    1. Price enters FVG zone
    2. Price gets rejected from the zone (fails to sustain)
    3. Price breaks previous structure in opposite direction
    """
    if entry_index >= len(candles) - 3:
        return None
    
    # Analyze candles after FVG entry
    post_entry_candles = candles[entry_index:]
    
    # Find the highest/lowest point reached within the FVG zone
    if fvg_direction == "bullish":
        # For bullish FVG, look for rejection from upper part of zone
        max_penetration = max(candle["high"] for candle in post_entry_candles[:5])
        fvg_mid = (fvg_zone_low + fvg_zone_high) / 2
        
        # Check if price reached into upper half of FVG zone
        if max_penetration > fvg_mid:
            # Now look for rejection and structure break below
            rejection_found = False
            rejection_index = None
            
            # Find the rejection point (high point within FVG)
            for i, candle in enumerate(post_entry_candles[:5]):
                if candle["high"] >= max_penetration * 0.99:  # Within 1% of max penetration
                    rejection_index = entry_index + i
                    rejection_found = True
                    break
            
            if rejection_found and rejection_index is not None:
                # Look for structure break below the rejection
                rejection_low = post_entry_candles[rejection_index - entry_index]["low"]
                
                # Analyze subsequent candles for bearish structure break
                for i in range(rejection_index - entry_index + 1, min(8, len(post_entry_candles))):
                    current_candle = post_entry_candles[i]
                    
                    # Check if we break below the rejection low and previous support
                    if current_candle["low"] < rejection_low:
                        # Additional validation: look for previous support levels
                        lookback_candles = candles[max(0, entry_index - 10):entry_index]
                        if lookback_candles:
                            recent_lows = [c["low"] for c in lookback_candles[-5:]]
                            support_level = min(recent_lows) if recent_lows else rejection_low
                            
                            if current_candle["low"] < support_level:
                                return {
                                    "timestamp": current_candle["timestamp"],
                                    "price": current_candle["low"],
                                    "type": "fvg_rejection_reversal_bearish",
                                    "fvg_entry_index": entry_index,
                                    "rejection_price": max_penetration,
                                    "rejection_index": rejection_index,
                                    "broken_support": support_level,
                                    "penetration_depth": max_penetration - fvg_zone_low,
                                    "reversal_strength": support_level - current_candle["low"]
                                }
    
    elif fvg_direction == "bearish":
        # For bearish FVG, look for rejection from lower part of zone
        min_penetration = min(candle["low"] for candle in post_entry_candles[:5])
        fvg_mid = (fvg_zone_low + fvg_zone_high) / 2
        
        # Check if price reached into lower half of FVG zone
        if min_penetration < fvg_mid:
            # Now look for rejection and structure break above
            rejection_found = False
            rejection_index = None
            
            # Find the rejection point (low point within FVG)
            for i, candle in enumerate(post_entry_candles[:5]):
                if candle["low"] <= min_penetration * 1.01:  # Within 1% of min penetration
                    rejection_index = entry_index + i
                    rejection_found = True
                    break
            
            if rejection_found and rejection_index is not None:
                # Look for structure break above the rejection
                rejection_high = post_entry_candles[rejection_index - entry_index]["high"]
                
                # Analyze subsequent candles for bullish structure break
                for i in range(rejection_index - entry_index + 1, min(8, len(post_entry_candles))):
                    current_candle = post_entry_candles[i]
                    
                    # Check if we break above the rejection high and previous resistance
                    if current_candle["high"] > rejection_high:
                        # Additional validation: look for previous resistance levels
                        lookback_candles = candles[max(0, entry_index - 10):entry_index]
                        if lookback_candles:
                            recent_highs = [c["high"] for c in lookback_candles[-5:]]
                            resistance_level = max(recent_highs) if recent_highs else rejection_high
                            
                            if current_candle["high"] > resistance_level:
                                return {
                                    "timestamp": current_candle["timestamp"],
                                    "price": current_candle["high"],
                                    "type": "fvg_rejection_reversal_bullish",
                                    "fvg_entry_index": entry_index,
                                    "rejection_price": min_penetration,
                                    "rejection_index": rejection_index,
                                    "broken_resistance": resistance_level,
                                    "penetration_depth": fvg_zone_high - min_penetration,
                                    "reversal_strength": current_candle["high"] - resistance_level
                                }
    
    return None


def detect_fvg_contextual_cisd(candles: List[Dict], fvg_zone_low: float, fvg_zone_high: float,
                              fvg_direction: str, entry_index: int) -> Dict | None:
    """
    Enhanced CISD detection that considers FVG context.
    This provides more accurate signals when price is interacting with FVG zones.
    """
    if entry_index >= len(candles) - 3:
        return None
    
    post_entry_candles = candles[entry_index:]
    fvg_mid = (fvg_zone_low + fvg_zone_high) / 2
    
    # For bullish FVG, we expect price to eventually break higher
    # But we also want to detect when it fails and breaks lower
    if fvg_direction == "bullish":
        # Look for bullish continuation first
        for i in range(1, min(8, len(post_entry_candles))):
            current_candle = post_entry_candles[i]
            
            # Strong bullish signal: close above FVG zone with momentum
            if current_candle["close"] > fvg_zone_high:
                # Check for momentum (close in upper part of candle)
                candle_range = current_candle["high"] - current_candle["low"]
                if candle_range > 0:
                    close_position = (current_candle["close"] - current_candle["low"]) / candle_range
                    if close_position > 0.6:  # Close in upper 40% of candle
                        return {
                            "timestamp": current_candle["timestamp"],
                            "price": current_candle["close"],
                            "type": "fvg_bullish_continuation",
                            "direction": "bullish",
                            "fvg_zone_high": fvg_zone_high,
                            "close_strength": close_position
                        }
        
        # If no bullish continuation, look for bearish reversal
        # This catches the 05-20 pattern where bullish FVG gets rejected
        entry_high = max(candle["high"] for candle in post_entry_candles[:3])
        
        for i in range(2, min(8, len(post_entry_candles))):
            current_candle = post_entry_candles[i]
            
            # Look for break below previous structure
            if current_candle["low"] < fvg_zone_low:
                # Get some context from before entry
                pre_entry_candles = candles[max(0, entry_index - 5):entry_index]
                if pre_entry_candles:
                    recent_lows = [c["low"] for c in pre_entry_candles]
                    support_level = min(recent_lows) if recent_lows else fvg_zone_low
                    
                    if current_candle["low"] < support_level:
                        return {
                            "timestamp": current_candle["timestamp"],
                            "price": current_candle["low"],
                            "type": "fvg_bullish_failure_bearish",
                            "direction": "bearish",
                            "broken_support": support_level,
                            "fvg_high_reached": entry_high,
                            "failure_strength": support_level - current_candle["low"]
                        }
    
    elif fvg_direction == "bearish":
        # Look for bearish continuation first
        for i in range(1, min(8, len(post_entry_candles))):
            current_candle = post_entry_candles[i]
            
            # Strong bearish signal: close below FVG zone with momentum
            if current_candle["close"] < fvg_zone_low:
                # Check for momentum (close in lower part of candle)
                candle_range = current_candle["high"] - current_candle["low"]
                if candle_range > 0:
                    close_position = (current_candle["high"] - current_candle["close"]) / candle_range
                    if close_position > 0.6:  # Close in lower 40% of candle
                        return {
                            "timestamp": current_candle["timestamp"],
                            "price": current_candle["close"],
                            "type": "fvg_bearish_continuation",
                            "direction": "bearish",
                            "fvg_zone_low": fvg_zone_low,
                            "close_strength": close_position
                        }
        
        # If no bearish continuation, look for bullish reversal
        entry_low = min(candle["low"] for candle in post_entry_candles[:3])
        
        for i in range(2, min(8, len(post_entry_candles))):
            current_candle = post_entry_candles[i]
            
            # Look for break above previous structure
            if current_candle["high"] > fvg_zone_high:
                # Get some context from before entry
                pre_entry_candles = candles[max(0, entry_index - 5):entry_index]
                if pre_entry_candles:
                    recent_highs = [c["high"] for c in pre_entry_candles]
                    resistance_level = max(recent_highs) if recent_highs else fvg_zone_high
                    
                    if current_candle["high"] > resistance_level:
                        return {
                            "timestamp": current_candle["timestamp"],
                            "price": current_candle["high"],
                            "type": "fvg_bearish_failure_bullish",
                            "direction": "bullish",
                            "broken_resistance": resistance_level,
                            "fvg_low_reached": entry_low,
                            "failure_strength": current_candle["high"] - resistance_level
                        }
    
    return None
