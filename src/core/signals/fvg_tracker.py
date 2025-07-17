from typing import List, Dict
import uuid
from src.core.liquidity.unified_fvg_manager import UnifiedFVGManager, FVGZone, FVGStatus
from sqlalchemy.orm import Session


def track_fvg_status(candles: List[Dict], fvg_candidates: List[Dict], 
                    max_lookahead: int = 20, db_session: Session = None) -> List[Dict]:
    """
    Updated FVG tracker using unified FVG management system
    This function maintains backward compatibility while using the new unified system
    """
    if db_session is None:
        # Fallback to legacy tracking if no database session provided
        return _legacy_track_fvg_status(candles, fvg_candidates, max_lookahead)
    
    # Use unified FVG manager
    unified_manager = UnifiedFVGManager(db_session)
    
    # Convert candidates to FVG zones
    zones = []
    for i, candle in enumerate(fvg_candidates):
        if not candle.get("fvg_zone"):
            continue
            
        zone_low, zone_high = sorted(candle["fvg_zone"])
        direction = "bullish" if candle.get("fvg_bullish") else "bearish"
        
        zone = FVGZone(
            id=f"fvg_{i}_{uuid.uuid4().hex[:6]}",
            symbol=candle.get("symbol", "UNKNOWN"),
            timeframe=candle.get("timeframe", "15T"),
            timestamp=candle["timestamp"],
            direction=direction,
            zone_low=zone_low,
            zone_high=zone_high
        )
        zones.append(zone)
    
    # Update zones with price action
    updated_zones = unified_manager.update_fvg_status(zones, candles)
    
    # Convert back to legacy format for backward compatibility
    tracked_fvgs = []
    for zone in updated_zones:
        tracked_fvgs.append({
            "fvg_id": zone.id,
            "index": 0,  # Legacy field
            "timestamp": zone.timestamp,
            "zone": [zone.zone_low, zone.zone_high],
            "direction": zone.direction,
            "status": zone.status,
            "invalidated_by": None,  # Legacy field - handled by unified system
            "mitigation_by": None,   # Legacy field - handled by unified system
            "iFVG": False,           # Removed as requested
            "retested": zone.touch_count > 1,
            "retested_at": zone.last_touch_time,
            "touch_count": zone.touch_count,
            "max_penetration_pct": zone.max_penetration_pct,
            "confidence": zone.confidence,
            "strength": zone.strength
        })
    
    return tracked_fvgs


def _legacy_track_fvg_status(candles: List[Dict], fvg_candidates: List[Dict], 
                           max_lookahead: int = 20) -> List[Dict]:
    """
    Legacy FVG tracking - kept for backward compatibility
    """
    tracked_fvgs = []

    for i, candle in enumerate(fvg_candidates):
        if not candle.get("fvg_zone"):
            continue

        fvg_id = f"fvg_{i}_{uuid.uuid4().hex[:6]}"
        zone_low, zone_high = sorted(candle["fvg_zone"])
        direction = "bullish" if candle.get("fvg_bullish") else "bearish"
        status = FVGStatus.ACTIVE
        invalidated_by = None
        mitigation_by = None
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
                # Mitigate if candle body overlaps the FVG
                if body_low < zone_high and body_high > zone_low:
                    status = FVGStatus.MITIGATED
                    mitigation_by = j
                    break

                # Invalidate if candle closes below FVG
                if close < zone_low:
                    status = FVGStatus.INVALIDATED
                    invalidated_by = j
                    break

            else:  # bearish
                if body_low < zone_high and body_high > zone_low:
                    status = FVGStatus.MITIGATED
                    mitigation_by = j
                    break

                if close > zone_high:
                    status = FVGStatus.INVALIDATED
                    invalidated_by = j
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
            "iFVG": False,  # Removed as requested
            "retested": retested,
            "retested_at": retested_at,
        })

    return tracked_fvgs
