"""
Enhanced Cache Manager for Algorithmic Trading

This module provides a robust caching layer for:
- Market data (candles, bars)
- Liquidity pools (FVGs, pivots)
- Signal detection results
- Multi-timeframe analysis results

Supports both Redis and in-memory caching with TTL management.
"""

import json
import redis
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from dataclasses import asdict
import pickle
import logging

from src.core.liquidity.base_pool_manager import LiquidityPool


class CacheManager:
    """Enhanced cache manager with support for multiple cache types"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, 
                 use_memory_cache: bool = True, 
                 default_ttl: int = 3600):
        self.redis = redis_client
        self.use_memory_cache = use_memory_cache
        self.default_ttl = default_ttl
        self.logger = logging.getLogger(__name__)
        
        # In-memory cache for faster access
        self.memory_cache: Dict[str, Dict] = {}
        
        # Cache prefixes for different data types
        self.prefixes = {
            "bars": "bars:",
            "pools": "pools:",
            "signals": "signals:",
            "analysis": "analysis:",
            "structure": "structure:"
        }
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key from parameters"""
        key_parts = [f"{k}:{v}" for k, v in sorted(kwargs.items())]
        key_str = "-".join(key_parts)
        hash_key = sha256(key_str.encode()).hexdigest()[:16]
        return f"{prefix}{hash_key}"
    
    def _serialize_data(self, data: Any) -> str:
        """Serialize data for caching"""
        if isinstance(data, (list, dict)):
            return json.dumps(data, default=str)
        elif isinstance(data, LiquidityPool):
            return json.dumps(asdict(data), default=str)
        else:
            return pickle.dumps(data).decode('latin-1')
    
    def _deserialize_data(self, data: str) -> Any:
        """Deserialize data from cache"""
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            try:
                return pickle.loads(data.encode('latin-1'))
            except:
                return data
    
    def get_bars(self, symbol: str, timeframe: str, start: str, end: str) -> Optional[List[Dict]]:
        """Get cached market bars"""
        key = self._generate_key(
            self.prefixes["bars"],
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end
        )
        
        # Try memory cache first
        if self.use_memory_cache and key in self.memory_cache:
            cache_entry = self.memory_cache[key]
            if datetime.now(timezone.utc) < cache_entry["expires_at"]:
                self.logger.debug(f"Cache hit (memory): {key}")
                return cache_entry["data"]
            else:
                del self.memory_cache[key]
        
        # Try Redis cache
        if self.redis:
            try:
                cached_data = self.redis.get(key)
                if cached_data:
                    self.logger.debug(f"Cache hit (Redis): {key}")
                    # Handle both bytes and str from Redis
                    if isinstance(cached_data, bytes):
                        data = self._deserialize_data(cached_data.decode('utf-8'))
                    else:
                        data = self._deserialize_data(cached_data)
                    
                    # Store in memory cache for faster access
                    if self.use_memory_cache:
                        self.memory_cache[key] = {
                            "data": data,
                            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=self.default_ttl)
                        }
                    
                    return data
            except Exception as e:
                self.logger.error(f"Redis cache error: {e}")
        
        return None
    
    def set_bars(self, symbol: str, timeframe: str, start: str, end: str, 
                 data: List[Dict], ttl: Optional[int] = None) -> bool:
        """Cache market bars"""
        key = self._generate_key(
            self.prefixes["bars"],
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end
        )
        
        ttl = ttl or self.default_ttl
        serialized_data = self._serialize_data(data)
        
        # Store in memory cache
        if self.use_memory_cache:
            self.memory_cache[key] = {
                "data": data,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl)
            }
        
        # Store in Redis cache
        if self.redis:
            try:
                self.redis.setex(key, ttl, serialized_data)
                self.logger.debug(f"Cache set (Redis): {key}")
                return True
            except Exception as e:
                self.logger.error(f"Redis cache set error: {e}")
        
        return self.use_memory_cache
    
    def get_pools(self, symbol: str, timeframe: str, pool_type: str,
                  start: str, end: str) -> Optional[List[Dict]]:
        """Get cached liquidity pools"""
        key = self._generate_key(
            self.prefixes["pools"],
            symbol=symbol,
            timeframe=timeframe,
            pool_type=pool_type,
            start=start,
            end=end
        )
        
        return self._get_cached_data(key)
    
    def set_pools(self, symbol: str, timeframe: str, pool_type: str,
                  start: str, end: str, pools: List[LiquidityPool],
                  ttl: Optional[int] = None) -> bool:
        """Cache liquidity pools"""
        key = self._generate_key(
            self.prefixes["pools"],
            symbol=symbol,
            timeframe=timeframe,
            pool_type=pool_type,
            start=start,
            end=end
        )
        
        # Convert pools to dictionaries for serialization
        pools_data = [asdict(pool) for pool in pools]
        return self._set_cached_data(key, pools_data, ttl)
    
    def get_signals(self, symbol: str, timeframe: str, signal_type: str,
                   start: str, end: str) -> Optional[List[Dict]]:
        """Get cached signals"""
        key = self._generate_key(
            self.prefixes["signals"],
            symbol=symbol,
            timeframe=timeframe,
            signal_type=signal_type,
            start=start,
            end=end
        )
        
        return self._get_cached_data(key)
    
    def set_signals(self, symbol: str, timeframe: str, signal_type: str,
                   start: str, end: str, signals: List[Dict],
                   ttl: Optional[int] = None) -> bool:
        """Cache signals"""
        key = self._generate_key(
            self.prefixes["signals"],
            symbol=symbol,
            timeframe=timeframe,
            signal_type=signal_type,
            start=start,
            end=end
        )
        
        return self._set_cached_data(key, signals, ttl)
    
    def get_analysis_result(self, symbol: str, analysis_type: str,
                           **params) -> Optional[Dict]:
        """Get cached analysis result"""
        key = self._generate_key(
            self.prefixes["analysis"],
            symbol=symbol,
            analysis_type=analysis_type,
            **params
        )
        
        return self._get_cached_data(key)
    
    def set_analysis_result(self, symbol: str, analysis_type: str,
                           result: Dict, ttl: Optional[int] = None,
                           **params) -> bool:
        """Cache analysis result"""
        key = self._generate_key(
            self.prefixes["analysis"],
            symbol=symbol,
            analysis_type=analysis_type,
            **params
        )
        
        return self._set_cached_data(key, result, ttl)
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching a pattern"""
        invalidated = 0
        
        # Invalidate memory cache
        if self.use_memory_cache:
            keys_to_remove = [k for k in self.memory_cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self.memory_cache[key]
            invalidated += len(keys_to_remove)
        
        # Invalidate Redis cache
        if self.redis:
            try:
                keys = self.redis.keys(f"*{pattern}*")
                if keys:
                    self.redis.delete(*keys)
                    invalidated += len(keys)
            except Exception as e:
                self.logger.error(f"Redis cache invalidation error: {e}")
        
        return invalidated
    
    def invalidate_symbol(self, symbol: str) -> int:
        """Invalidate all cache entries for a symbol"""
        return self.invalidate_pattern(symbol)
    
    def cleanup_expired(self) -> int:
        """Clean up expired memory cache entries"""
        if not self.use_memory_cache:
            return 0
        
        now = datetime.now(timezone.utc)
        expired_keys = [
            k for k, v in self.memory_cache.items()
            if now >= v["expires_at"]
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        return len(expired_keys)
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        stats = {
            "memory_cache_size": len(self.memory_cache) if self.use_memory_cache else 0,
            "redis_connected": self.redis is not None and self._test_redis_connection(),
            "expired_cleaned": self.cleanup_expired()
        }
        
        if self.redis:
            try:
                info = self.redis.info()
                stats["redis_keys"] = info.get("db0", {}).get("keys", 0)
                stats["redis_memory"] = info.get("used_memory_human", "N/A")
            except Exception as e:
                stats["redis_error"] = str(e)
        
        return stats
    
    def _get_cached_data(self, key: str) -> Optional[Any]:
        """Generic method to get cached data"""
        # Try memory cache first
        if self.use_memory_cache and key in self.memory_cache:
            cache_entry = self.memory_cache[key]
            if datetime.now(timezone.utc) < cache_entry["expires_at"]:
                self.logger.debug(f"Cache hit (memory): {key}")
                return cache_entry["data"]
            else:
                del self.memory_cache[key]
        
        # Try Redis cache
        if self.redis:
            try:
                cached_data = self.redis.get(key)
                if cached_data:
                    self.logger.debug(f"Cache hit (Redis): {key}")
                    # Handle both bytes and str from Redis
                    if isinstance(cached_data, bytes):
                        data = self._deserialize_data(cached_data.decode('utf-8'))
                    else:
                        data = self._deserialize_data(cached_data)
                    
                    # Store in memory cache for faster access
                    if self.use_memory_cache:
                        self.memory_cache[key] = {
                            "data": data,
                            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=self.default_ttl)
                        }
                    
                    return data
            except Exception as e:
                self.logger.error(f"Redis cache error: {e}")
        
        return None
    
    def _set_cached_data(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """Generic method to set cached data"""
        ttl = ttl or self.default_ttl
        
        # Store in memory cache
        if self.use_memory_cache:
            self.memory_cache[key] = {
                "data": data,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl)
            }
        
        # Store in Redis cache
        if self.redis:
            try:
                serialized_data = self._serialize_data(data)
                self.redis.setex(key, ttl, serialized_data)
                self.logger.debug(f"Cache set (Redis): {key}")
                return True
            except Exception as e:
                self.logger.error(f"Redis cache set error: {e}")
        
        return self.use_memory_cache
    
    def _test_redis_connection(self) -> bool:
        """Test Redis connection"""
        try:
            self.redis.ping()
            return True
        except:
            return False
