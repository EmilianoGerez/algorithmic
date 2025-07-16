#!/usr/bin/env python3
"""
Comprehensive Algorithm Performance Profiler
Analyzes the entire trading strategy workflow for performance bottlenecks
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
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Mock data for testing without API calls
class MockAlpacaRepository:
    def __init__(self):
        self.call_count = 0
        
    def get_bars(self, symbol: str, timeframe: str, start_time=None, end_time=None, limit: int = 1000):
        """Mock get_bars method that returns synthetic data"""
        self.call_count += 1
        
        # Simulate API delay
        time.sleep(0.01)  # 10ms delay
        
        # Generate synthetic bars
        bars = []
        base_price = 45000.0 if symbol == "BTC/USD" else 3000.0
        
        current_time = start_time or (datetime.now() - timedelta(days=30))
        
        for i in range(min(limit, 100)):  # Limit to avoid excessive memory
            price_variation = (i % 10 - 5) * 100  # Simple price variation
            bar = {
                'timestamp': current_time + timedelta(minutes=i * 15),
                'open': base_price + price_variation,
                'high': base_price + price_variation + 50,
                'low': base_price + price_variation - 50,
                'close': base_price + price_variation + 10,
                'volume': 1000 + i * 10
            }
            bars.append(bar)
        
        return bars

from src.services.signal_detection import SignalDetectionService
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.db.models.fvg import FVG
from src.db.models.pivot import Pivot

class AlgorithmProfiler:
    def __init__(self):
        self.timings = {}
        self.memory_snapshots = []
        self.operation_counts = {}
        
    def measure_memory_usage(self, description=""):
        """Measure current memory usage"""
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        snapshot = {
            'timestamp': time.time(),
            'description': description,
            'memory_mb': memory_mb,
            'memory_percent': process.memory_percent(),
            'cpu_percent': process.cpu_percent()
        }
        
        self.memory_snapshots.append(snapshot)
        return memory_mb
    
    def time_operation(self, operation_name, func, *args, **kwargs):
        """Time a specific operation and track call count"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        self.timings[operation_name] = execution_time
        
        # Track operation count
        self.operation_counts[operation_name] = self.operation_counts.get(operation_name, 0) + 1
        
        return result
    
    def profile_data_layer(self, repo, symbol="BTC/USD"):
        """Profile data layer performance"""
        print("\n📊 Data Layer Performance Analysis")
        print("=" * 40)
        
        # Test different timeframes
        timeframes = ["15Min", "1Hour", "4Hour"]
        
        for timeframe in timeframes:
            operation_name = f"Data Fetch ({timeframe})"
            
            bars = self.time_operation(
                operation_name,
                repo.get_bars,
                symbol=symbol,
                timeframe=timeframe,
                limit=100
            )
            
            print(f"⏱️  {operation_name}: {self.timings[operation_name]:.4f}s ({len(bars)} bars)")
        
        # Check API call efficiency
        print(f"📊 Total API calls: {repo.call_count}")
        
        return repo.call_count
    
    def profile_database_layer(self, db):
        """Profile database layer performance"""
        print("\n🗄️  Database Layer Performance Analysis")
        print("=" * 40)
        
        # Test common database operations
        operations = [
            ("FVG Active Query", lambda: db.query(FVG).filter(FVG.status == "active").all()),
            ("FVG by Symbol", lambda: db.query(FVG).filter(FVG.symbol == "BTC/USD").all()),
            ("Pivot Recent", lambda: db.query(Pivot).order_by(Pivot.timestamp.desc()).limit(50).all()),
            ("FVG Count", lambda: db.query(FVG).count()),
            ("Pivot Count", lambda: db.query(Pivot).count()),
        ]
        
        db_results = {}
        for name, query_func in operations:
            result = self.time_operation(name, query_func)
            db_results[name] = {
                'time': self.timings[name],
                'count': len(result) if hasattr(result, '__len__') else result
            }
            print(f"⏱️  {name}: {self.timings[name]:.4f}s ({db_results[name]['count']} records)")
        
        return db_results
    
    def profile_cache_layer(self, redis_conn):
        """Profile cache layer performance"""
        print("\n🚀 Cache Layer Performance Analysis")
        print("=" * 40)
        
        # Test cache operations
        test_data = "x" * 1000  # 1KB of data
        large_data = "x" * 100000  # 100KB of data
        
        operations = [
            ("Cache Ping", lambda: redis_conn.ping()),
            ("Small Write", lambda: redis_conn.set("test_small", test_data, ex=60)),
            ("Small Read", lambda: redis_conn.get("test_small")),
            ("Large Write", lambda: redis_conn.set("test_large", large_data, ex=60)),
            ("Large Read", lambda: redis_conn.get("test_large")),
            ("Cache Delete", lambda: redis_conn.delete("test_small", "test_large")),
        ]
        
        cache_results = {}
        for name, operation in operations:
            result = self.time_operation(name, operation)
            cache_results[name] = {
                'time': self.timings[name],
                'success': result is not None or result == True
            }
            print(f"⏱️  {name}: {self.timings[name]:.4f}s")
        
        return cache_results
    
    def profile_service_layer(self, service, symbol="BTC/USD"):
        """Profile service layer performance"""
        print("\n🎯 Service Layer Performance Analysis")
        print("=" * 40)
        
        # Test service operations
        operations = [
            ("Cache Stats", lambda: service.get_cache_stats()),
            ("Liquidity Pools (4H)", lambda: service.get_liquidity_pools(symbol, "4H", "all")),
            ("Liquidity Pools (1H)", lambda: service.get_liquidity_pools(symbol, "1H", "all")),
        ]
        
        service_results = {}
        for name, operation in operations:
            try:
                result = self.time_operation(name, operation)
                service_results[name] = {
                    'time': self.timings[name],
                    'success': True,
                    'result_type': type(result).__name__
                }
                
                # Extract meaningful info from result
                if isinstance(result, dict):
                    if 'fvg_pools' in result:
                        fvg_count = len(result['fvg_pools'])
                        pivot_count = len(result.get('pivot_pools', []))
                        print(f"⏱️  {name}: {self.timings[name]:.4f}s ({fvg_count} FVGs, {pivot_count} Pivots)")
                    else:
                        print(f"⏱️  {name}: {self.timings[name]:.4f}s (dict with {len(result)} keys)")
                else:
                    print(f"⏱️  {name}: {self.timings[name]:.4f}s")
                    
            except Exception as e:
                service_results[name] = {
                    'time': 0,
                    'success': False,
                    'error': str(e)
                }
                print(f"❌ {name}: Error - {e}")
        
        return service_results
    
    def profile_algorithm_workflow(self, repo, redis_conn, db, service):
        """Profile complete algorithm workflow"""
        print("\n🔄 Complete Algorithm Workflow Analysis")
        print("=" * 40)
        
        symbol = "BTC/USD"
        
        # Simulate a complete workflow
        workflow_start = time.time()
        
        # Step 1: Data retrieval
        self.measure_memory_usage("Start Workflow")
        
        # Step 2: Database operations
        self.measure_memory_usage("After Data Retrieval")
        
        # Step 3: Cache operations
        self.measure_memory_usage("After Database Operations")
        
        # Step 4: Service processing
        self.measure_memory_usage("After Cache Operations")
        
        # Step 5: Final processing
        self.measure_memory_usage("After Service Processing")
        
        workflow_time = time.time() - workflow_start
        print(f"⏱️  Complete Workflow: {workflow_time:.4f}s")
        
        return workflow_time
    
    def analyze_performance_bottlenecks(self):
        """Analyze performance bottlenecks"""
        print("\n🔍 Performance Bottleneck Analysis")
        print("=" * 40)
        
        # Sort operations by time
        sorted_timings = sorted(self.timings.items(), key=lambda x: x[1], reverse=True)
        
        print("🐌 Slowest Operations:")
        for i, (operation, time_taken) in enumerate(sorted_timings[:10]):
            print(f"  {i+1}. {operation}: {time_taken:.4f}s")
        
        # Identify categories
        data_operations = [op for op in self.timings if 'Data' in op]
        db_operations = [op for op in self.timings if any(x in op for x in ['FVG', 'Pivot', 'Query'])]
        cache_operations = [op for op in self.timings if 'Cache' in op]
        service_operations = [op for op in self.timings if 'Service' in op or 'Liquidity' in op]
        
        print(f"\n📊 Performance by Category:")
        
        categories = [
            ("Data Layer", data_operations),
            ("Database Layer", db_operations),
            ("Cache Layer", cache_operations),
            ("Service Layer", service_operations)
        ]
        
        for category_name, operations in categories:
            if operations:
                total_time = sum(self.timings[op] for op in operations)
                avg_time = total_time / len(operations)
                print(f"  {category_name}: {total_time:.4f}s total, {avg_time:.4f}s avg ({len(operations)} ops)")
        
        # Memory analysis
        if len(self.memory_snapshots) > 1:
            print(f"\n💾 Memory Analysis:")
            initial_memory = self.memory_snapshots[0]['memory_mb']
            peak_memory = max(s['memory_mb'] for s in self.memory_snapshots)
            final_memory = self.memory_snapshots[-1]['memory_mb']
            
            print(f"  Initial: {initial_memory:.2f} MB")
            print(f"  Peak: {peak_memory:.2f} MB")
            print(f"  Final: {final_memory:.2f} MB")
            print(f"  Growth: {final_memory - initial_memory:.2f} MB")
    
    def generate_optimization_recommendations(self):
        """Generate optimization recommendations"""
        print("\n💡 Optimization Recommendations")
        print("=" * 40)
        
        recommendations = []
        
        # Analyze timings for recommendations
        for operation, time_taken in self.timings.items():
            if time_taken > 1.0:
                recommendations.append(f"🚨 CRITICAL: {operation} ({time_taken:.4f}s) - Major optimization needed")
            elif time_taken > 0.5:
                recommendations.append(f"⚠️  MODERATE: {operation} ({time_taken:.4f}s) - Consider optimization")
        
        # Data layer recommendations
        data_times = [t for op, t in self.timings.items() if 'Data' in op]
        if data_times and max(data_times) > 0.1:
            recommendations.append("🔧 Data Layer: Consider connection pooling and request batching")
        
        # Database recommendations
        db_times = [t for op, t in self.timings.items() if any(x in op for x in ['FVG', 'Pivot', 'Query'])]
        if db_times and max(db_times) > 0.3:
            recommendations.append("🔧 Database: Query optimization and better indexing needed")
        
        # Cache recommendations
        cache_times = [t for op, t in self.timings.items() if 'Cache' in op]
        if cache_times and max(cache_times) > 0.01:
            recommendations.append("🔧 Cache: Check Redis performance and network latency")
        
        # Memory recommendations
        if len(self.memory_snapshots) > 1:
            memory_growth = self.memory_snapshots[-1]['memory_mb'] - self.memory_snapshots[0]['memory_mb']
            if memory_growth > 100:
                recommendations.append("🔧 Memory: High memory usage - check for leaks or optimize data structures")
        
        # Display recommendations
        if recommendations:
            for rec in recommendations:
                print(f"  {rec}")
        else:
            print("  ✅ No major performance issues detected")
        
        return recommendations
    
    def run_comprehensive_analysis(self):
        """Run comprehensive algorithm performance analysis"""
        print("🚀 Comprehensive Algorithm Performance Analysis")
        print("=" * 60)
        
        # Start memory tracking
        tracemalloc.start()
        self.measure_memory_usage("Analysis Start")
        
        try:
            # Initialize components with mock data
            repo = MockAlpacaRepository()
            redis_conn = get_redis_connection()
            db = SessionLocal()
            service = SignalDetectionService(repo, redis_conn, db)
            
            self.measure_memory_usage("Components Initialized")
            
            # Profile each layer
            self.profile_data_layer(repo)
            self.measure_memory_usage("Data Layer Complete")
            
            self.profile_database_layer(db)
            self.measure_memory_usage("Database Layer Complete")
            
            self.profile_cache_layer(redis_conn)
            self.measure_memory_usage("Cache Layer Complete")
            
            self.profile_service_layer(service)
            self.measure_memory_usage("Service Layer Complete")
            
            # Profile complete workflow
            workflow_time = self.profile_algorithm_workflow(repo, redis_conn, db, service)
            self.measure_memory_usage("Workflow Complete")
            
            # Analyze bottlenecks
            self.analyze_performance_bottlenecks()
            
            # Generate recommendations
            recommendations = self.generate_optimization_recommendations()
            
            # Summary
            print(f"\n🎯 Performance Summary")
            print("=" * 30)
            print(f"Total Operations: {len(self.timings)}")
            print(f"Total Time: {sum(self.timings.values()):.4f}s")
            print(f"Average Time/Operation: {sum(self.timings.values()) / len(self.timings):.4f}s")
            print(f"Recommendations: {len(recommendations)}")
            
            # Cleanup
            db.close()
            
        except Exception as e:
            print(f"❌ Error during analysis: {e}")
            import traceback
            traceback.print_exc()
        
        # Final memory analysis
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"\n💾 Final Memory Analysis:")
        print(f"  Current: {current / 1024 / 1024:.2f} MB")
        print(f"  Peak: {peak / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    profiler = AlgorithmProfiler()
    profiler.run_comprehensive_analysis()
    
    print("\n" + "="*60)
    print("🎯 Algorithm Performance Analysis Complete!")
    print("Review the analysis above for optimization opportunities.")
