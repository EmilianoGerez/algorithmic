#!/usr/bin/env python3
"""
Debug FVG Mitigation Time Issues
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
import pandas as pd
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


def debug_fvg_mitigation():
    """Debug FVG mitigation time issues"""
    
    print("🔍 Debugging FVG Mitigation Time Issues")
    print("=" * 50)
    
    # Initialize dependencies
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    # Get FVG data
    symbol = "BTC/USD"
    htf = "4H"
    
    htf_pools = service.get_liquidity_pools(symbol, htf, "all")
    fvg_pools = htf_pools.get('fvg_pools', [])
    
    print(f"📊 Found {len(fvg_pools)} FVG pools")
    
    # Check for mitigation_time field
    mitigation_count = 0
    
    for i, fvg in enumerate(fvg_pools[:10]):  # Check first 10
        print(f"\n🔍 FVG #{i+1}: {fvg['timestamp']}")
        
        # Check if has mitigation_time
        if 'mitigation_time' in fvg:
            print(f"   Has mitigation_time: {fvg['mitigation_time']} (type: {type(fvg['mitigation_time'])})")
            if fvg['mitigation_time'] is not None:
                mitigation_count += 1
                
                # Test parsing
                try:
                    parsed = pd.to_datetime(fvg['mitigation_time'], utc=True)
                    print(f"   Parsed mitigation_time: {parsed}")
                except Exception as e:
                    print(f"   Parse error: {e}")
        else:
            print(f"   No mitigation_time field")
    
    print(f"\n📊 Summary:")
    print(f"   • Total FVGs: {len(fvg_pools)}")
    print(f"   • With mitigation_time: {mitigation_count}")
    
    # Test our _is_fvg_active_at_time method
    print(f"\n🔍 Testing _is_fvg_active_at_time method:")
    
    # Manual test
    evaluation_time = pd.to_datetime("2025-05-29T13:00:00Z", utc=True)
    
    for i, fvg in enumerate(fvg_pools[:5]):
        print(f"\n   FVG #{i+1}: {fvg['timestamp']}")
        
        # Manual check
        if 'mitigation_time' not in fvg or fvg['mitigation_time'] is None:
            print(f"      No mitigation_time → Active")
        else:
            try:
                mitigation_time = pd.to_datetime(fvg['mitigation_time'], utc=True)
                is_active = mitigation_time > evaluation_time
                print(f"      Mitigation: {mitigation_time}")
                print(f"      Evaluation: {evaluation_time}")
                print(f"      Is Active: {is_active}")
            except Exception as e:
                print(f"      Error checking mitigation: {e}")
    
    print(f"\n✅ Debug Complete!")
    db.close()


if __name__ == "__main__":
    debug_fvg_mitigation()
