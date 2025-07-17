"""
Unified FVG Manager - Consolidates all FVG handling logic
Implements standardized touch detection, improved invalidation, unified status system, and confidence scoring
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
import numpy as np
from sqlalchemy.orm import Session
from src.db.models.fvg import FVG as FVGModel
from src.db.models.candle import Candle


@dataclass
class FVGStatus:
    """Unified FVG status system"""
    ACTIVE = "active"           # FVG is active and untested
    TESTED = "tested"           # FVG has been touched but not invalidated
    MITIGATED = "mitigated"     # FVG has been significantly filled
    INVALIDATED = "invalidated" # FVG has been completely invalidated
    EXPIRED = "expired"         # FVG has expired due to time/conditions


@dataclass
class FVGZone:
    """Represents an FVG zone with all necessary information"""
    id: str
    symbol: str
    timeframe: str
    timestamp: datetime
    direction: str  # "bullish" or "bearish"
    zone_low: float
    zone_high: float
    status: str = FVGStatus.ACTIVE
    
    # Touch tracking
    touch_count: int = 0
    last_touch_time: Optional[datetime] = None
    max_penetration_pct: float = 0.0
    
    # Confidence scoring
    confidence: float = 0.5
    strength: float = 0.5
    volume_confirmation: bool = False
    
    # Invalidation tracking
    invalidated_by_candle: Optional[datetime] = None
    invalidated_price: Optional[float] = None
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class UnifiedFVGManager:
    """
    Unified FVG Manager that consolidates all FVG handling logic
    
    Key Features:
    - Standardized touch detection using full candle range
    - Improved invalidation logic based on closes and significant penetration
    - Unified status system across all components
    - Confidence scoring based on multiple factors
    - Timeframe-specific rules and thresholds
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
        # Configuration for different timeframes
        self.timeframe_config = {
            "15T": {
                "invalidation_threshold": 0.7,  # 70% penetration for invalidation
                "mitigation_threshold": 0.3,    # 30% penetration for mitigation
                "max_age_hours": 24,             # 24 hours max age
                "min_zone_size_pips": 1.0,      # Minimum zone size
                "volume_weight": 0.2             # Volume influence on confidence
            },
            "1H": {
                "invalidation_threshold": 0.8,  # 80% penetration for invalidation
                "mitigation_threshold": 0.4,    # 40% penetration for mitigation
                "max_age_hours": 72,             # 72 hours max age
                "min_zone_size_pips": 2.0,      # Minimum zone size
                "volume_weight": 0.3             # Volume influence on confidence
            },
            "4H": {
                "invalidation_threshold": 0.85, # 85% penetration for invalidation
                "mitigation_threshold": 0.5,    # 50% penetration for mitigation
                "max_age_hours": 168,            # 1 week max age
                "min_zone_size_pips": 5.0,      # Minimum zone size
                "volume_weight": 0.4             # Volume influence on confidence
            },
            "1D": {
                "invalidation_threshold": 0.9,  # 90% penetration for invalidation
                "mitigation_threshold": 0.6,    # 60% penetration for mitigation
                "max_age_hours": 720,            # 1 month max age
                "min_zone_size_pips": 10.0,     # Minimum zone size
                "volume_weight": 0.5             # Volume influence on confidence
            }
        }
    
    def detect_fvg_zones(self, candles: List[Dict]) -> List[FVGZone]:
        """
        Detect FVG zones from candle data with enhanced filtering
        """
        zones = []
        
        for i in range(1, len(candles) - 1):
            prev_candle = candles[i - 1]
            curr_candle = candles[i]
            next_candle = candles[i + 1]
            
            # Check for bullish FVG
            if prev_candle["high"] < next_candle["low"]:
                zone = self._create_fvg_zone(
                    candles=candles,
                    index=i,
                    direction="bullish",
                    zone_low=prev_candle["high"],
                    zone_high=next_candle["low"],
                    formation_candles=[prev_candle, curr_candle, next_candle]
                )
                if zone:
                    zones.append(zone)
            
            # Check for bearish FVG
            elif prev_candle["low"] > next_candle["high"]:
                zone = self._create_fvg_zone(
                    candles=candles,
                    index=i,
                    direction="bearish",
                    zone_low=next_candle["high"],
                    zone_high=prev_candle["low"],
                    formation_candles=[prev_candle, curr_candle, next_candle]
                )
                if zone:
                    zones.append(zone)
        
        return zones
    
    def _create_fvg_zone(self, candles: List[Dict], index: int, direction: str, 
                        zone_low: float, zone_high: float, 
                        formation_candles: List[Dict]) -> Optional[FVGZone]:
        """
        Create an FVG zone with quality filtering and confidence scoring
        """
        curr_candle = candles[index]
        symbol = curr_candle.get("symbol", "UNKNOWN")
        timeframe = curr_candle.get("timeframe", "15T")
        
        # Get timeframe configuration
        config = self.timeframe_config.get(timeframe, self.timeframe_config["15T"])
        
        # Calculate zone size
        zone_size = abs(zone_high - zone_low)
        
        # Filter by minimum size
        if zone_size < config["min_zone_size_pips"]:
            return None
        
        # Calculate confidence and strength
        confidence = self._calculate_confidence(
            formation_candles=formation_candles,
            zone_size=zone_size,
            surrounding_candles=candles[max(0, index-5):index+6],
            timeframe=timeframe
        )
        
        strength = self._calculate_strength(
            formation_candles=formation_candles,
            zone_size=zone_size,
            timeframe=timeframe
        )
        
        # Filter by minimum confidence
        if confidence < 0.3:  # Minimum confidence threshold
            return None
        
        # Create FVG zone
        zone = FVGZone(
            id=f"fvg_{symbol}_{timeframe}_{index}_{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime.fromisoformat(curr_candle["timestamp"].replace("Z", "+00:00")),
            direction=direction,
            zone_low=zone_low,
            zone_high=zone_high,
            confidence=confidence,
            strength=strength,
            volume_confirmation=self._has_volume_confirmation(formation_candles)
        )
        
        return zone
    
    def update_fvg_status(self, zones: List[FVGZone], candles: List[Dict]) -> List[FVGZone]:
        """
        Update FVG status based on current market data
        Implements unified touch detection and invalidation logic
        """
        updated_zones = []
        
        for zone in zones:
            if zone.status == FVGStatus.INVALIDATED or zone.status == FVGStatus.EXPIRED:
                updated_zones.append(zone)
                continue
            
            # Find relevant candles after FVG formation
            relevant_candles = [
                c for c in candles 
                if datetime.fromisoformat(c["timestamp"].replace("Z", "+00:00")) > zone.timestamp
            ]
            
            # Update zone status based on price action
            updated_zone = self._update_zone_with_candles(zone, relevant_candles)
            updated_zones.append(updated_zone)
        
        return updated_zones
    
    def _update_zone_with_candles(self, zone: FVGZone, candles: List[Dict]) -> FVGZone:
        """
        Update a single FVG zone with new candle data
        """
        config = self.timeframe_config.get(zone.timeframe, self.timeframe_config["15T"])
        
        # Check for expiration
        if self._is_zone_expired(zone, config):
            zone.status = FVGStatus.EXPIRED
            zone.updated_at = datetime.now(timezone.utc)
            return zone
        
        # Process each candle
        for candle in candles:
            candle_time = datetime.fromisoformat(candle["timestamp"].replace("Z", "+00:00"))
            
            # Skip if candle is before zone formation
            if candle_time <= zone.timestamp:
                continue
            
            # Check for touch
            if self._is_zone_touched(zone, candle):
                zone.touch_count += 1
                zone.last_touch_time = candle_time
                
                # Calculate penetration percentage
                penetration_pct = self._calculate_penetration_percentage(zone, candle)
                zone.max_penetration_pct = max(zone.max_penetration_pct, penetration_pct)
                
                # Update status based on penetration and close behavior
                new_status = self._determine_new_status(zone, candle, penetration_pct, config)
                if new_status != zone.status:
                    zone.status = new_status
                    zone.updated_at = datetime.now(timezone.utc)
                    
                    # Track invalidation details
                    if new_status == FVGStatus.INVALIDATED:
                        zone.invalidated_by_candle = candle_time
                        zone.invalidated_price = candle["close"]
                
                # Stop processing if invalidated
                if zone.status == FVGStatus.INVALIDATED:
                    break
        
        return zone
    
    def _is_zone_touched(self, zone: FVGZone, candle: Dict) -> bool:
        """
        Standardized touch detection using full candle range
        """
        candle_high = candle["high"]
        candle_low = candle["low"]
        
        # Check if candle overlaps with FVG zone
        return not (candle_high < zone.zone_low or candle_low > zone.zone_high)
    
    def _calculate_penetration_percentage(self, zone: FVGZone, candle: Dict) -> float:
        """
        Calculate how much of the FVG zone has been penetrated
        """
        candle_high = candle["high"]
        candle_low = candle["low"]
        zone_size = zone.zone_high - zone.zone_low
        
        if zone_size <= 0:
            return 0.0
        
        # Calculate overlap
        overlap_low = max(candle_low, zone.zone_low)
        overlap_high = min(candle_high, zone.zone_high)
        
        if overlap_high <= overlap_low:
            return 0.0
        
        overlap_size = overlap_high - overlap_low
        return overlap_size / zone_size
    
    def _determine_new_status(self, zone: FVGZone, candle: Dict, 
                            penetration_pct: float, config: Dict) -> str:
        """
        Determine new FVG status based on penetration and close behavior
        """
        close_price = candle["close"]
        
        # Check for invalidation first (most important)
        if self._is_zone_invalidated(zone, candle, config):
            return FVGStatus.INVALIDATED
        
        # Check for mitigation
        if penetration_pct >= config["mitigation_threshold"]:
            return FVGStatus.MITIGATED
        
        # Check for tested status
        if penetration_pct >= config["mitigation_threshold"] * 0.5:  # 50% of mitigation threshold
            return FVGStatus.TESTED
        
        return zone.status
    
    def _is_zone_invalidated(self, zone: FVGZone, candle: Dict, config: Dict) -> bool:
        """
        Enhanced invalidation logic based on closes and significant penetration
        """
        close_price = candle["close"]
        penetration_pct = self._calculate_penetration_percentage(zone, candle)
        
        # Rule 1: Close through the zone (traditional invalidation)
        if zone.direction == "bullish" and close_price < zone.zone_low:
            return True
        elif zone.direction == "bearish" and close_price > zone.zone_high:
            return True
        
        # Rule 2: Significant penetration (enhanced invalidation)
        if penetration_pct >= config["invalidation_threshold"]:
            return True
        
        # Rule 3: Body close through significant portion of zone
        candle_open = candle["open"]
        body_high = max(candle_open, close_price)
        body_low = min(candle_open, close_price)
        
        if zone.direction == "bullish":
            # For bullish FVG, check if body closes below 80% of zone
            threshold_price = zone.zone_low + (zone.zone_high - zone.zone_low) * 0.2
            if body_high < threshold_price:
                return True
        else:
            # For bearish FVG, check if body closes above 80% of zone
            threshold_price = zone.zone_high - (zone.zone_high - zone.zone_low) * 0.2
            if body_low > threshold_price:
                return True
        
        return False
    
    def _is_zone_expired(self, zone: FVGZone, config: Dict) -> bool:
        """
        Check if FVG zone has expired based on time and conditions
        """
        age_hours = (datetime.now(timezone.utc) - zone.timestamp).total_seconds() / 3600
        return age_hours > config["max_age_hours"]
    
    def _calculate_confidence(self, formation_candles: List[Dict], zone_size: float, 
                            surrounding_candles: List[Dict], timeframe: str) -> float:
        """
        Calculate confidence score based on multiple factors
        """
        confidence = 0.5  # Base confidence
        config = self.timeframe_config.get(timeframe, self.timeframe_config["15T"])
        
        # Factor 1: Zone size relative to average range
        if surrounding_candles:
            avg_range = np.mean([c["high"] - c["low"] for c in surrounding_candles])
            if avg_range > 0:
                size_factor = min(zone_size / avg_range, 3.0) / 3.0
                confidence += size_factor * 0.2
        
        # Factor 2: Volume confirmation
        if self._has_volume_confirmation(formation_candles):
            confidence += 0.15
        
        # Factor 3: Formation quality
        formation_quality = self._assess_formation_quality(formation_candles)
        confidence += formation_quality * 0.2
        
        # Factor 4: Market context
        market_context = self._assess_market_context(surrounding_candles)
        confidence += market_context * 0.15
        
        return min(confidence, 1.0)
    
    def _calculate_strength(self, formation_candles: List[Dict], zone_size: float, 
                          timeframe: str) -> float:
        """
        Calculate strength score based on formation characteristics
        """
        strength = 0.5  # Base strength
        
        # Factor 1: Imbalance size
        middle_candle = formation_candles[1]
        candle_range = middle_candle["high"] - middle_candle["low"]
        if candle_range > 0:
            imbalance_ratio = zone_size / candle_range
            strength += min(imbalance_ratio, 2.0) * 0.25
        
        # Factor 2: Volume spike
        if self._has_volume_spike(formation_candles):
            strength += 0.2
        
        # Factor 3: Clean formation
        if self._is_clean_formation(formation_candles):
            strength += 0.15
        
        return min(strength, 1.0)
    
    def _has_volume_confirmation(self, formation_candles: List[Dict]) -> bool:
        """Check if formation has volume confirmation"""
        if not all("volume" in c for c in formation_candles):
            return False
        
        middle_volume = formation_candles[1].get("volume", 0)
        avg_volume = np.mean([c.get("volume", 0) for c in formation_candles])
        
        return middle_volume > avg_volume * 1.2
    
    def _has_volume_spike(self, formation_candles: List[Dict]) -> bool:
        """Check if formation has significant volume spike"""
        if not all("volume" in c for c in formation_candles):
            return False
        
        middle_volume = formation_candles[1].get("volume", 0)
        avg_volume = np.mean([c.get("volume", 0) for c in formation_candles])
        
        return middle_volume > avg_volume * 1.5
    
    def _assess_formation_quality(self, formation_candles: List[Dict]) -> float:
        """Assess the quality of FVG formation"""
        prev_candle, curr_candle, next_candle = formation_candles
        
        quality = 0.5  # Base quality
        
        # Check if middle candle is a strong directional candle
        middle_body = abs(curr_candle["close"] - curr_candle["open"])
        middle_range = curr_candle["high"] - curr_candle["low"]
        
        if middle_range > 0:
            body_ratio = middle_body / middle_range
            quality += body_ratio * 0.3
        
        # Check if gap is clean (no overlap)
        gap_size = abs(prev_candle["high"] - next_candle["low"]) if prev_candle["high"] < next_candle["low"] else abs(prev_candle["low"] - next_candle["high"])
        total_range = (prev_candle["high"] - prev_candle["low"]) + (curr_candle["high"] - curr_candle["low"]) + (next_candle["high"] - next_candle["low"])
        
        if total_range > 0:
            gap_ratio = gap_size / total_range
            quality += gap_ratio * 0.2
        
        return min(quality, 1.0)
    
    def _is_clean_formation(self, formation_candles: List[Dict]) -> bool:
        """Check if FVG formation is clean"""
        prev_candle, curr_candle, next_candle = formation_candles
        
        # Check if middle candle doesn't overlap with gap
        if prev_candle["high"] < next_candle["low"]:  # Bullish FVG
            return curr_candle["low"] > prev_candle["high"] and curr_candle["high"] < next_candle["low"]
        elif prev_candle["low"] > next_candle["high"]:  # Bearish FVG
            return curr_candle["high"] < prev_candle["low"] and curr_candle["low"] > next_candle["high"]
        
        return False
    
    def _assess_market_context(self, surrounding_candles: List[Dict]) -> float:
        """Assess market context for FVG formation"""
        if len(surrounding_candles) < 3:
            return 0.0
        
        # Calculate volatility
        ranges = [c["high"] - c["low"] for c in surrounding_candles]
        avg_range = np.mean(ranges)
        volatility = np.std(ranges) / avg_range if avg_range > 0 else 0
        
        # Moderate volatility is better for FVG formation
        optimal_volatility = 0.3
        volatility_score = 1.0 - abs(volatility - optimal_volatility) / optimal_volatility
        
        return max(0.0, min(volatility_score, 1.0))
    
    def save_zones(self, zones: List[FVGZone]) -> bool:
        """
        Save FVG zones to database with unified model
        """
        try:
            for zone in zones:
                # Check if FVG already exists
                existing_fvg = self.db.query(FVGModel).filter(
                    FVGModel.timestamp == zone.timestamp,
                    FVGModel.timeframe == zone.timeframe,
                    FVGModel.symbol == zone.symbol
                ).first()
                
                if existing_fvg:
                    # Update existing FVG
                    existing_fvg.direction = zone.direction
                    existing_fvg.zone_low = zone.zone_low
                    existing_fvg.zone_high = zone.zone_high
                    existing_fvg.status = zone.status
                    existing_fvg.touched = zone.touch_count > 0
                    existing_fvg.penetration_pct = zone.max_penetration_pct
                    existing_fvg.iFVG = False  # Remove iFVG for now as requested
                else:
                    # Create new FVG
                    fvg_model = FVGModel(
                        id=uuid.uuid4(),
                        symbol=zone.symbol,
                        timeframe=zone.timeframe,
                        timestamp=zone.timestamp,
                        direction=zone.direction,
                        zone_low=zone.zone_low,
                        zone_high=zone.zone_high,
                        status=zone.status,
                        iFVG=False,  # Remove iFVG for now as requested
                        touched=zone.touch_count > 0,
                        penetration_pct=zone.max_penetration_pct
                    )
                    self.db.add(fvg_model)
            
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error saving FVG zones: {e}")
            self.db.rollback()
            return False
    
    def load_active_zones(self, symbol: str, timeframe: str, 
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[FVGZone]:
        """
        Load active FVG zones from database
        """
        query = self.db.query(FVGModel).filter(
            FVGModel.symbol == symbol,
            FVGModel.timeframe == timeframe,
            FVGModel.status.in_([FVGStatus.ACTIVE, FVGStatus.TESTED, FVGStatus.MITIGATED])
        )
        
        if start_time:
            query = query.filter(FVGModel.timestamp >= start_time)
        if end_time:
            query = query.filter(FVGModel.timestamp <= end_time)
        
        fvg_models = query.all()
        
        zones = []
        for model in fvg_models:
            zone = FVGZone(
                id=f"fvg_{model.symbol}_{model.timeframe}_{str(model.id)[:8]}",
                symbol=model.symbol,
                timeframe=model.timeframe,
                timestamp=model.timestamp,
                direction=model.direction,
                zone_low=model.zone_low,
                zone_high=model.zone_high,
                status=model.status,
                touch_count=1 if model.touched else 0,
                max_penetration_pct=model.penetration_pct or 0.0
            )
            zones.append(zone)
        
        return zones
    
    def get_zone_summary(self, zones: List[FVGZone]) -> Dict:
        """
        Get summary statistics for FVG zones
        """
        if not zones:
            return {"total": 0, "by_status": {}, "by_direction": {}, "by_timeframe": {}}
        
        summary = {
            "total": len(zones),
            "by_status": {},
            "by_direction": {},
            "by_timeframe": {},
            "avg_confidence": np.mean([z.confidence for z in zones]),
            "avg_strength": np.mean([z.strength for z in zones])
        }
        
        for zone in zones:
            # Count by status
            summary["by_status"][zone.status] = summary["by_status"].get(zone.status, 0) + 1
            
            # Count by direction
            summary["by_direction"][zone.direction] = summary["by_direction"].get(zone.direction, 0) + 1
            
            # Count by timeframe
            summary["by_timeframe"][zone.timeframe] = summary["by_timeframe"].get(zone.timeframe, 0) + 1
        
        return summary
