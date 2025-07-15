from typing import Dict, List, Literal
from src.db.models.candle import Candle
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.core.signals import pivot_points, fvg, fvg_tracker
import redis
import json
from hashlib import sha256
from src.db.models.fvg import FVG
from src.db.models.pivot import Pivot
from sqlalchemy.orm import Session
from datetime import datetime
from src.services.cisd_into_4H_fvg import detect_fvg_sweep_cisd


class SignalDetectionService:
    def __init__(self, repo: AlpacaCryptoRepository, redis_client: redis.Redis, db_session: Session):
        self.repo = repo
        self.redis = redis_client
        self.db = db_session

    def _cache_key(self, symbol: str, timeframe: str, start: str, end: str) -> str:
        key_str = f"{symbol}-{timeframe}-{start}-{end}"
        return f"bars:{sha256(key_str.encode()).hexdigest()}"

    def detect_signals(
        self,
        symbol: str,
        signal_type: str,
        timeframe: str = "15Min",
        start: str = None,
        end: str = None,
    ) -> dict:
        key = self._cache_key(symbol, timeframe, start, end)
        cached = self.redis.get(key)

        if cached:
            print("✅ Using cached bars")
            candles = json.loads(cached)
        else:
            print("📡 Fetching bars from Alpaca")
            bars: List[Candle] = self.repo.get_bars(
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
            )
            candles = [bar.dict() for bar in bars]
            self.redis.setex(key, 3600 * 24, json.dumps(candles))

        if signal_type in ["pivot", "fvg_and_pivot"]:
            pivots = pivot_points.detect_pivots(candles)
            self.save_pivots(pivots, symbol, timeframe)
            return {"candles": pivots, "tracked_fvgs": []}

        elif signal_type in ["fvg", "fvg_and_pivot"]:
            detected = fvg.detect_fvg(candles)
            tracked = fvg_tracker.track_fvg_status(candles, detected)
            self.save_tracked_fvgs(tracked, symbol, timeframe)
            return {"candles": detected, "tracked_fvgs": tracked}

        elif signal_type == "fvg_sweep_cisd":
            candles_15m = candles
            signals = detect_fvg_sweep_cisd(symbol, candles_15m, self.db)
            return {"candles": candles_15m, "signals": signals, "tracked_fvgs": []}

        else:
            raise ValueError(f"Unknown signal type: {signal_type}")

    def save_tracked_fvgs(self, tracked: List[dict], symbol: str, timeframe: str):
        for f in tracked:
            self.db.add(FVG(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.fromisoformat(f["timestamp"].replace("Z", "")),
                direction=f["direction"],
                zone_low=f["zone"][0],
                zone_high=f["zone"][1],
                status=f["status"],
                iFVG=f["iFVG"],
                touched=True,
                created_by_index=f["index"],
                mitigation_by=f["mitigation_by"],
                invalidated_by=f["invalidated_by"],
                retested=f["retested"],
                retested_at=datetime.fromisoformat(f["retested_at"].replace("Z", "")) if f["retested_at"] else None
            ))
        self.db.commit()

    def save_pivots(self, pivot_data: List[Dict], symbol: str, timeframe: str):
        for i, item in enumerate(pivot_data):
            if item.get("potential_swing_high"):
                pivot = Pivot(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=item["timestamp"],
                    price=item["high"],
                    index=i,
                    type="high"
                )
                self.db.add(pivot)
            elif item.get("potential_swing_low"):
                pivot = Pivot(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=item["timestamp"],
                    price=item["low"],
                    index=i,
                    type="low"
                )
                self.db.add(pivot)
        self.db.commit()




