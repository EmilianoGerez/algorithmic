#!/usr/bin/env python3
"""
Performance Profiler for Multi-Timeframe Trading Strategy
Analyzes performance bottlenecks and optimization opportunities
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import cProfile
import pstats
import io
from datetime import datetime, timedelta
import psutil
import tracemalloc
from memory_profiler import profile as memory_profile
from functools import wraps
import json

from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.db.models.fvg import FVG
from src.db.models.pivot import Pivot

class PerformanceProfiler:
    def __init__(self):
        self.metrics = {}
        self.start_time = None
        self.memory_snapshots = []
        
    def timing_decorator(self, func_name):
        """Decorator to measure execution time"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                end_time = time.time()
                
                execution_time = end_time - start_time
                if func_name not in self.metrics:
                    self.metrics[func_name] = []
                self.metrics[func_name].append(execution_time)
                
                print(f"⏱️  {func_name}: {execution_time:.4f}s")
                return result
            return wrapper
        return decorator
    
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
    
    def profile_database_queries(self, db_session):
        """Profile database query performance"""
        print("\n🔍 Database Query Performance Analysis:")
        
        # Test FVG queries
        start_time = time.time()
        fvg_count = db_session.query(FVG).count()
        fvg_query_time = time.time() - start_time
        print(f"  📊 FVG Query: {fvg_count} records in {fvg_query_time:.4f}s")
        
        # Test Pivot queries
        start_time = time.time()
        pivot_count = db_session.query(Pivot).count()
        pivot_query_time = time.time() - start_time
        print(f"  📊 Pivot Query: {pivot_count} records in {pivot_query_time:.4f}s")
        
        # Test filtered queries
        start_time = time.time()
        active_fvgs = db_session.query(FVG).filter(FVG.status == "active").count()
        filtered_query_time = time.time() - start_time
        print(f"  📊 Filtered FVG Query: {active_fvgs} active records in {filtered_query_time:.4f}s")
        
        return {
            'fvg_query_time': fvg_query_time,
            'pivot_query_time': pivot_query_time,
            'filtered_query_time': filtered_query_time
        }
    
    def profile_cache_performance(self, redis_conn):
        """Profile cache performance"""
        print("\n🚀 Cache Performance Analysis:")
        
        # Test Redis connection
        start_time = time.time()
        redis_ping = redis_conn.ping()
        redis_ping_time = time.time() - start_time
        print(f"  📡 Redis Ping: {redis_ping_time:.4f}s")
        
        # Test cache write
        test_data = {"test": "performance_data", "timestamp": time.time()}
        start_time = time.time()
        redis_conn.set("performance_test", json.dumps(test_data))
        cache_write_time = time.time() - start_time
        print(f"  ✍️  Cache Write: {cache_write_time:.4f}s")
        
        # Test cache read
        start_time = time.time()
        cached_data = redis_conn.get("performance_test")
        cache_read_time = time.time() - start_time
        print(f"  📖 Cache Read: {cache_read_time:.4f}s")
        
        # Clean up
        redis_conn.delete("performance_test")
        
        return {
            'redis_ping_time': redis_ping_time,
            'cache_write_time': cache_write_time,
            'cache_read_time': cache_read_time
        }
    
    def profile_signal_detection(self, service, symbol, timeframe, start, end):
        """Profile signal detection performance"""
        print(f"\n🎯 Signal Detection Performance ({timeframe}):")
        
        # Profile multi-timeframe signal detection
        start_time = time.time()
        signals = service.detect_multi_timeframe_signals(
            symbol=symbol,
            strategy_type="intraday",
            start=start,
            end=end,
            update_pools=False  # Don't update pools to isolate detection performance
        )
        mtf_detection_time = time.time() - start_time
        print(f"  🔍 Multi-Timeframe Detection: {len(signals)} signals in {mtf_detection_time:.4f}s")
        
        # Profile liquidity pool retrieval
        start_time = time.time()
        htf_pools = service.get_liquidity_pools(symbol, "4H", "all")
        pool_retrieval_time = time.time() - start_time
        print(f"  🏊 Pool Retrieval: {len(htf_pools.get('fvg_pools', []))} FVGs, {len(htf_pools.get('pivot_pools', []))} pivots in {pool_retrieval_time:.4f}s")
        
        # Profile legacy signal detection
        start_time = time.time()
        legacy_result = service.detect_signals(
            symbol=symbol,
            signal_type="fvg_and_pivot",
            timeframe=timeframe,
            start=start,
            end=end
        )
        legacy_detection_time = time.time() - start_time
        print(f"  📊 Legacy Detection: {len(legacy_result['candles'])} candles in {legacy_detection_time:.4f}s")
        
        return {
            'mtf_detection_time': mtf_detection_time,
            'pool_retrieval_time': pool_retrieval_time,
            'legacy_detection_time': legacy_detection_time,
            'signals_count': len(signals)
        }
    
    def profile_data_processing(self, service, symbol, timeframe, start, end):
        """Profile data processing performance"""
        print(f"\n📈 Data Processing Performance:")
        
        # Profile candle data retrieval
        start_time = time.time()
        candles = service.repo.get_bars(symbol, timeframe, start, end)
        data_retrieval_time = time.time() - start_time
        print(f"  📊 Data Retrieval: {len(candles)} candles in {data_retrieval_time:.4f}s")
        
        # Estimate processing rate
        if data_retrieval_time > 0:
            processing_rate = len(candles) / data_retrieval_time
            print(f"  ⚡ Processing Rate: {processing_rate:.0f} candles/second")
        
        return {
            'data_retrieval_time': data_retrieval_time,
            'candles_count': len(candles),
            'processing_rate': len(candles) / data_retrieval_time if data_retrieval_time > 0 else 0
        }
    
    def run_comprehensive_profile(self):
        """Run comprehensive performance analysis"""
        print("🚀 Starting Comprehensive Performance Analysis")
        print("=" * 60)
        
        # Start memory tracking
        tracemalloc.start()
        self.measure_memory_usage("Initial")
        
        # Initialize components
        print("\n🔧 Initializing Components...")
        init_start = time.time()
        
        repo = AlpacaCryptoRepository()
        redis = get_redis_connection()
        db = SessionLocal()
        service = SignalDetectionService(repo, redis, db)
        
        init_time = time.time() - init_start
        self.measure_memory_usage("After Initialization")
        print(f"⏱️  Initialization Time: {init_time:.4f}s")
        
        # Test parameters
        symbol = "BTC/USD"
        ltf = "15T"
        htf = "4H"
        start = "2025-05-18T00:00:00Z"
        end = "2025-05-24T00:00:00Z"
        
        # Profile different components
        performance_results = {}
        
        # 1. Database Performance
        db_results = self.profile_database_queries(db)
        performance_results['database'] = db_results
        self.measure_memory_usage("After DB Queries")
        
        # 2. Cache Performance
        cache_results = self.profile_cache_performance(redis)
        performance_results['cache'] = cache_results
        self.measure_memory_usage("After Cache Tests")
        
        # 3. Data Processing Performance
        data_results = self.profile_data_processing(service, symbol, ltf, start, end)
        performance_results['data_processing'] = data_results
        self.measure_memory_usage("After Data Processing")
        
        # 4. Signal Detection Performance
        signal_results = self.profile_signal_detection(service, symbol, ltf, start, end)
        performance_results['signal_detection'] = signal_results
        self.measure_memory_usage("After Signal Detection")
        
        # Memory analysis
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"\n💾 Memory Analysis:")
        print(f"  Current Memory: {current / 1024 / 1024:.2f} MB")
        print(f"  Peak Memory: {peak / 1024 / 1024:.2f} MB")
        
        # Generate performance report
        self.generate_performance_report(performance_results)
        
        # Cleanup
        db.close()
        
        return performance_results
    
    def generate_performance_report(self, results):
        """Generate detailed performance report"""
        print("\n📊 Performance Analysis Report")
        print("=" * 40)
        
        # Identify bottlenecks
        bottlenecks = []
        
        # Database bottlenecks
        if results['database']['fvg_query_time'] > 0.1:
            bottlenecks.append("🐌 Slow FVG database queries")
        
        # Cache bottlenecks
        if results['cache']['cache_write_time'] > 0.01:
            bottlenecks.append("🐌 Slow cache writes")
        
        # Data processing bottlenecks
        if results['data_processing']['processing_rate'] < 1000:
            bottlenecks.append("🐌 Low data processing rate")
        
        # Signal detection bottlenecks
        if results['signal_detection']['mtf_detection_time'] > 1.0:
            bottlenecks.append("🐌 Slow multi-timeframe detection")
        
        # Memory usage analysis
        total_memory = sum(snapshot['memory_mb'] for snapshot in self.memory_snapshots)
        avg_memory = total_memory / len(self.memory_snapshots)
        
        if avg_memory > 500:  # 500MB threshold
            bottlenecks.append("🐌 High memory usage")
        
        print("\n🚨 Performance Bottlenecks:")
        if bottlenecks:
            for bottleneck in bottlenecks:
                print(f"  {bottleneck}")
        else:
            print("  ✅ No significant bottlenecks detected")
        
        # Optimization recommendations
        print("\n💡 Optimization Recommendations:")
        
        if results['database']['fvg_query_time'] > 0.1:
            print("  🔧 Database: Add indexes on frequently queried columns")
            print("  🔧 Database: Consider query optimization or pagination")
        
        if results['cache']['cache_write_time'] > 0.01:
            print("  🔧 Cache: Check Redis configuration and network latency")
            print("  🔧 Cache: Consider using connection pooling")
        
        if results['data_processing']['processing_rate'] < 1000:
            print("  🔧 Data Processing: Optimize data transformation algorithms")
            print("  🔧 Data Processing: Consider parallel processing")
        
        if results['signal_detection']['mtf_detection_time'] > 1.0:
            print("  🔧 Signal Detection: Optimize multi-timeframe analysis")
            print("  🔧 Signal Detection: Consider caching intermediate results")
        
        if avg_memory > 500:
            print("  🔧 Memory: Review data structures for memory efficiency")
            print("  🔧 Memory: Consider using generators for large datasets")
        
        # Performance summary
        print(f"\n📈 Performance Summary:")
        print(f"  Database Performance: {'✅ Good' if results['database']['fvg_query_time'] < 0.1 else '⚠️ Needs optimization'}")
        print(f"  Cache Performance: {'✅ Good' if results['cache']['cache_write_time'] < 0.01 else '⚠️ Needs optimization'}")
        print(f"  Data Processing: {'✅ Good' if results['data_processing']['processing_rate'] > 1000 else '⚠️ Needs optimization'}")
        print(f"  Signal Detection: {'✅ Good' if results['signal_detection']['mtf_detection_time'] < 1.0 else '⚠️ Needs optimization'}")
        print(f"  Memory Usage: {'✅ Good' if avg_memory < 500 else '⚠️ High usage'}")

def profile_with_cprofile():
    """Run profiling with cProfile for detailed function-level analysis"""
    print("\n🔍 Running Detailed Function-Level Profiling...")
    
    pr = cProfile.Profile()
    pr.enable()
    
    # Run the profiling
    profiler = PerformanceProfiler()
    profiler.run_comprehensive_profile()
    
    pr.disable()
    
    # Analyze results
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 functions
    
    print("\n📊 Top 20 Functions by Cumulative Time:")
    print(s.getvalue())
    
    # Save detailed profile
    ps.dump_stats('performance_profile.prof')
    print("\n💾 Detailed profile saved to 'performance_profile.prof'")
    print("   View with: python -m pstats performance_profile.prof")

if __name__ == "__main__":
    # Run basic profiling
    profiler = PerformanceProfiler()
    results = profiler.run_comprehensive_profile()
    
    # Run detailed profiling
    profile_with_cprofile()
    
    print("\n🎯 Profiling Complete!")
    print("Check the output above for performance insights and recommendations.")
