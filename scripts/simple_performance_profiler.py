#!/usr/bin/env python3
"""
Simple Performance Profiler for Trading Strategy
Focuses on existing system performance without external API calls
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import cProfile
import pstats
import io
import psutil
import tracemalloc
import json
from datetime import datetime

from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.db.models.fvg import FVG
from src.db.models.pivot import Pivot

class SimplePerformanceProfiler:
    def __init__(self):
        self.timings = {}
        self.memory_snapshots = []
        
    def measure_memory_usage(self, description=""):
        """Measure current memory usage"""
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        snapshot = {
            'timestamp': time.time(),
            'description': description,
            'memory_mb': memory_mb,
            'memory_percent': process.memory_percent()
        }
        
        self.memory_snapshots.append(snapshot)
        print(f"💾 Memory Usage ({description}): {memory_mb:.2f} MB ({process.memory_percent():.1f}%)")
        return memory_mb
    
    def time_operation(self, operation_name, func, *args, **kwargs):
        """Time a specific operation"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        self.timings[operation_name] = execution_time
        print(f"⏱️  {operation_name}: {execution_time:.4f}s")
        return result
    
    def profile_database_operations(self, db):
        """Profile database performance"""
        print("\n🔍 Database Performance Analysis:")
        
        # Count operations
        fvg_count = self.time_operation("FVG Count Query", 
                                        lambda: db.query(FVG).count())
        
        pivot_count = self.time_operation("Pivot Count Query", 
                                         lambda: db.query(Pivot).count())
        
        # Active FVG query
        active_fvgs = self.time_operation("Active FVG Query", 
                                         lambda: db.query(FVG).filter(FVG.status == "active").count())
        
        # Recent FVG query
        recent_fvgs = self.time_operation("Recent FVG Query", 
                                         lambda: db.query(FVG).limit(100).all())
        
        print(f"  📊 Database Records: {fvg_count} FVGs, {pivot_count} Pivots")
        print(f"  📊 Active FVGs: {active_fvgs}")
        print(f"  📊 Recent FVGs loaded: {len(recent_fvgs)}")
        
        return {
            'fvg_count': fvg_count,
            'pivot_count': pivot_count,
            'active_fvgs': active_fvgs,
            'recent_fvgs_count': len(recent_fvgs)
        }
    
    def profile_cache_operations(self, redis_conn):
        """Profile cache performance"""
        print("\n🚀 Cache Performance Analysis:")
        
        # Redis ping
        self.time_operation("Redis Ping", lambda: redis_conn.ping())
        
        # Cache operations
        test_data = json.dumps({"test": "performance", "value": 12345})
        
        self.time_operation("Cache Write", 
                           lambda: redis_conn.set("perf_test", test_data, ex=60))
        
        cached_result = self.time_operation("Cache Read", 
                                          lambda: redis_conn.get("perf_test"))
        
        # Cache info
        try:
            cache_info = self.time_operation("Cache Info", 
                                           lambda: redis_conn.info("memory"))
            used_memory = cache_info.get('used_memory_human', 'N/A')
            print(f"  📊 Redis Memory Usage: {used_memory}")
        except Exception as e:
            print(f"  ⚠️  Cache info error: {e}")
        
        # Cleanup
        redis_conn.delete("perf_test")
        
        return cached_result is not None
    
    def profile_service_operations(self, service):
        """Profile service layer operations"""
        print("\n🎯 Service Layer Performance:")
        
        symbol = "BTC/USD"
        
        # Cache stats
        cache_stats = self.time_operation("Cache Stats", 
                                        lambda: service.get_cache_stats())
        
        print(f"  📊 Cache Stats: {cache_stats}")
        
        # Try to get liquidity pools (this should use cached data)
        try:
            pools = self.time_operation("Liquidity Pools Retrieval", 
                                      lambda: service.get_liquidity_pools(symbol, "4H", "all"))
            
            fvg_pools = pools.get('fvg_pools', [])
            pivot_pools = pools.get('pivot_pools', [])
            
            print(f"  📊 Retrieved Pools: {len(fvg_pools)} FVGs, {len(pivot_pools)} Pivots")
            
            return {
                'fvg_pools_count': len(fvg_pools),
                'pivot_pools_count': len(pivot_pools)
            }
        except Exception as e:
            print(f"  ⚠️  Pool retrieval error: {e}")
            return {'error': str(e)}
    
    def analyze_memory_usage(self):
        """Analyze memory usage patterns"""
        print("\n💾 Memory Usage Analysis:")
        
        if len(self.memory_snapshots) < 2:
            print("  ⚠️  Not enough memory snapshots for analysis")
            return
        
        initial_memory = self.memory_snapshots[0]['memory_mb']
        peak_memory = max(snapshot['memory_mb'] for snapshot in self.memory_snapshots)
        current_memory = self.memory_snapshots[-1]['memory_mb']
        
        memory_growth = current_memory - initial_memory
        
        print(f"  📊 Initial Memory: {initial_memory:.2f} MB")
        print(f"  📊 Peak Memory: {peak_memory:.2f} MB")
        print(f"  📊 Final Memory: {current_memory:.2f} MB")
        print(f"  📊 Memory Growth: {memory_growth:.2f} MB")
        
        # Memory growth analysis
        if memory_growth > 50:  # 50MB threshold
            print("  ⚠️  High memory growth detected")
        elif memory_growth > 10:
            print("  ⚠️  Moderate memory growth")
        else:
            print("  ✅ Low memory growth")
        
        return {
            'initial_memory': initial_memory,
            'peak_memory': peak_memory,
            'final_memory': current_memory,
            'memory_growth': memory_growth
        }
    
    def generate_performance_report(self):
        """Generate comprehensive performance report"""
        print("\n📊 Performance Report")
        print("=" * 40)
        
        # Analyze timings
        slow_operations = []
        for operation, timing in self.timings.items():
            if timing > 1.0:  # 1 second threshold
                slow_operations.append(f"{operation}: {timing:.4f}s")
            elif timing > 0.5:  # 0.5 second warning
                slow_operations.append(f"{operation}: {timing:.4f}s (moderate)")
        
        print("\n🚨 Performance Issues:")
        if slow_operations:
            for op in slow_operations:
                print(f"  🐌 {op}")
        else:
            print("  ✅ No significant performance issues detected")
        
        # Memory analysis
        memory_analysis = self.analyze_memory_usage()
        
        # Recommendations
        print("\n💡 Optimization Recommendations:")
        
        # Database recommendations
        if self.timings.get('FVG Count Query', 0) > 0.5:
            print("  🔧 Database: Consider adding indexes for FVG queries")
        
        if self.timings.get('Active FVG Query', 0) > 0.1:
            print("  🔧 Database: Optimize filtered queries with proper indexing")
        
        # Cache recommendations
        if self.timings.get('Cache Write', 0) > 0.01:
            print("  🔧 Cache: Check Redis performance and network latency")
        
        # Memory recommendations
        if memory_analysis and memory_analysis['memory_growth'] > 50:
            print("  🔧 Memory: Review for memory leaks or excessive data retention")
        
        # Service recommendations
        if self.timings.get('Liquidity Pools Retrieval', 0) > 0.5:
            print("  🔧 Service: Consider caching liquidity pool results")
        
        # Overall assessment
        print(f"\n📈 Overall Performance Assessment:")
        total_critical = sum(1 for t in self.timings.values() if t > 1.0)
        total_moderate = sum(1 for t in self.timings.values() if 0.5 <= t <= 1.0)
        
        if total_critical > 0:
            print(f"  🚨 Critical: {total_critical} operations need optimization")
        elif total_moderate > 0:
            print(f"  ⚠️  Moderate: {total_moderate} operations could be optimized")
        else:
            print("  ✅ Good: System performance is within acceptable limits")
    
    def run_profiling(self):
        """Run the complete profiling analysis"""
        print("🚀 Starting Performance Profiling")
        print("=" * 50)
        
        # Start memory tracking
        tracemalloc.start()
        self.measure_memory_usage("Initial")
        
        # Initialize components
        print("\n🔧 Initializing Components...")
        start_init = time.time()
        
        try:
            repo = AlpacaCryptoRepository()
            redis = get_redis_connection()
            db = SessionLocal()
            service = SignalDetectionService(repo, redis, db)
            
            init_time = time.time() - start_init
            print(f"⏱️  Initialization Time: {init_time:.4f}s")
            self.measure_memory_usage("After Initialization")
            
            # Run profiling components
            db_results = self.profile_database_operations(db)
            self.measure_memory_usage("After DB Operations")
            
            cache_results = self.profile_cache_operations(redis)
            self.measure_memory_usage("After Cache Operations")
            
            service_results = self.profile_service_operations(service)
            self.measure_memory_usage("After Service Operations")
            
            # Generate report
            self.generate_performance_report()
            
            # Cleanup
            db.close()
            
        except Exception as e:
            print(f"❌ Error during profiling: {e}")
            import traceback
            traceback.print_exc()
        
        # Final memory analysis
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"\n💾 Final Memory Analysis:")
        print(f"  Current Memory: {current / 1024 / 1024:.2f} MB")
        print(f"  Peak Memory: {peak / 1024 / 1024:.2f} MB")

def run_detailed_profiling():
    """Run detailed cProfile analysis"""
    print("\n🔍 Running Detailed Function-Level Profiling...")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run the main profiling
    simple_profiler = SimplePerformanceProfiler()
    simple_profiler.run_profiling()
    
    profiler.disable()
    
    # Analyze results
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    
    print("\n📊 Top 15 Functions by Cumulative Time:")
    stats.print_stats(15)
    
    # Save profile for detailed analysis
    stats.dump_stats('simple_performance_profile.prof')
    print("\n💾 Detailed profile saved to 'simple_performance_profile.prof'")

if __name__ == "__main__":
    # Run basic profiling
    profiler = SimplePerformanceProfiler()
    profiler.run_profiling()
    
    print("\n" + "="*50)
    print("🎯 Profiling Complete!")
    print("Check the analysis above for performance insights.")
