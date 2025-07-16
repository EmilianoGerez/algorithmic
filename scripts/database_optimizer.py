#!/usr/bin/env python3
"""
Database Performance Optimization Script
Analyzes and optimizes database queries and indexes
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
from datetime import datetime
from sqlalchemy import text, create_engine, inspect
from sqlalchemy.sql import func

from src.db.session import SessionLocal, engine
from src.db.models.fvg import FVG
from src.db.models.pivot import Pivot

class DatabaseOptimizer:
    def __init__(self):
        self.db = SessionLocal()
        self.engine = engine
        self.inspector = inspect(engine)
        
    def analyze_query_performance(self):
        """Analyze current query performance"""
        print("🔍 Analyzing Database Query Performance")
        print("=" * 50)
        
        # Test various query patterns
        queries = [
            ("FVG Count (Simple)", lambda: self.db.query(FVG).count()),
            ("FVG Count (Func)", lambda: self.db.query(func.count(FVG.id)).scalar()),
            ("FVG by Status", lambda: self.db.query(FVG).filter(FVG.status == "active").count()),
            ("FVG by Symbol", lambda: self.db.query(FVG).filter(FVG.symbol == "BTC/USD").count()),
            ("FVG by Timeframe", lambda: self.db.query(FVG).filter(FVG.timeframe == "4H").count()),
            ("FVG Recent", lambda: self.db.query(FVG).order_by(FVG.timestamp.desc()).limit(100).count()),
            ("Pivot Count", lambda: self.db.query(Pivot).count()),
            ("Pivot by Symbol", lambda: self.db.query(Pivot).filter(Pivot.symbol == "BTC/USD").count()),
        ]
        
        results = {}
        for name, query_func in queries:
            start_time = time.time()
            try:
                result = query_func()
                execution_time = time.time() - start_time
                results[name] = {
                    'time': execution_time,
                    'result': result,
                    'status': 'success'
                }
                print(f"⏱️  {name}: {execution_time:.4f}s (result: {result})")
            except Exception as e:
                execution_time = time.time() - start_time
                results[name] = {
                    'time': execution_time,
                    'error': str(e),
                    'status': 'error'
                }
                print(f"❌ {name}: {execution_time:.4f}s (error: {e})")
        
        return results
    
    def check_existing_indexes(self):
        """Check what indexes already exist"""
        print("\n🔍 Checking Existing Indexes")
        print("=" * 30)
        
        # Get indexes for FVG table
        fvg_indexes = self.inspector.get_indexes('fvg')
        print(f"📊 FVG Table Indexes: {len(fvg_indexes)} found")
        for idx in fvg_indexes:
            print(f"  🔑 {idx['name']}: {idx['column_names']}")
        
        # Get indexes for Pivot table
        pivot_indexes = self.inspector.get_indexes('pivot')
        print(f"📊 Pivot Table Indexes: {len(pivot_indexes)} found")
        for idx in pivot_indexes:
            print(f"  🔑 {idx['name']}: {idx['column_names']}")
        
        return {'fvg_indexes': fvg_indexes, 'pivot_indexes': pivot_indexes}
    
    def analyze_table_statistics(self):
        """Get table statistics"""
        print("\n📊 Table Statistics Analysis")
        print("=" * 30)
        
        # Table sizes
        try:
            # PostgreSQL specific query for table sizes
            size_query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename IN ('fvg', 'pivot')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
            """)
            
            result = self.db.execute(size_query)
            for row in result:
                print(f"📊 {row.tablename}: {row.size}")
                
        except Exception as e:
            print(f"⚠️  Could not get table sizes: {e}")
        
        # Row counts and column analysis
        fvg_count = self.db.query(FVG).count()
        pivot_count = self.db.query(Pivot).count()
        
        print(f"📊 FVG Records: {fvg_count}")
        print(f"📊 Pivot Records: {pivot_count}")
        
        # FVG status distribution
        try:
            status_dist = self.db.query(FVG.status, func.count(FVG.id))\
                                 .group_by(FVG.status)\
                                 .all()
            print(f"📊 FVG Status Distribution:")
            for status, count in status_dist:
                print(f"  {status}: {count}")
        except Exception as e:
            print(f"⚠️  Could not get status distribution: {e}")
        
        # Symbol distribution
        try:
            symbol_dist = self.db.query(FVG.symbol, func.count(FVG.id))\
                                 .group_by(FVG.symbol)\
                                 .all()
            print(f"📊 FVG Symbol Distribution:")
            for symbol, count in symbol_dist:
                print(f"  {symbol}: {count}")
        except Exception as e:
            print(f"⚠️  Could not get symbol distribution: {e}")
    
    def recommend_indexes(self):
        """Recommend indexes based on query patterns"""
        print("\n💡 Index Recommendations")
        print("=" * 30)
        
        recommendations = [
            {
                'table': 'fvg',
                'index_name': 'idx_fvg_status',
                'columns': ['status'],
                'reason': 'Frequent filtering by status in active FVG queries'
            },
            {
                'table': 'fvg',
                'index_name': 'idx_fvg_symbol_timeframe',
                'columns': ['symbol', 'timeframe'],
                'reason': 'Common filtering pattern for symbol and timeframe'
            },
            {
                'table': 'fvg',
                'index_name': 'idx_fvg_timestamp',
                'columns': ['timestamp'],
                'reason': 'Ordering by timestamp for recent records'
            },
            {
                'table': 'fvg',
                'index_name': 'idx_fvg_symbol_status',
                'columns': ['symbol', 'status'],
                'reason': 'Combined filtering for active FVGs by symbol'
            },
            {
                'table': 'pivot',
                'index_name': 'idx_pivot_symbol_timeframe',
                'columns': ['symbol', 'timeframe'],
                'reason': 'Common filtering pattern for pivot queries'
            },
            {
                'table': 'pivot',
                'index_name': 'idx_pivot_timestamp',
                'columns': ['timestamp'],
                'reason': 'Ordering by timestamp for recent pivots'
            }
        ]
        
        for rec in recommendations:
            print(f"🔧 {rec['table']}.{rec['index_name']}")
            print(f"   Columns: {rec['columns']}")
            print(f"   Reason: {rec['reason']}")
        
        return recommendations
    
    def create_performance_indexes(self, dry_run=True):
        """Create recommended indexes"""
        print(f"\n🚀 Creating Performance Indexes (dry_run={dry_run})")
        print("=" * 40)
        
        recommendations = self.recommend_indexes()
        
        # Check existing indexes first
        existing_indexes = self.check_existing_indexes()
        existing_fvg_indexes = [idx['name'] for idx in existing_indexes['fvg_indexes']]
        existing_pivot_indexes = [idx['name'] for idx in existing_indexes['pivot_indexes']]
        
        index_commands = []
        
        for rec in recommendations:
            index_name = rec['index_name']
            table_name = rec['table']
            columns = rec['columns']
            
            # Check if index already exists
            existing_list = existing_fvg_indexes if table_name == 'fvg' else existing_pivot_indexes
            
            if index_name in existing_list:
                print(f"⚠️  Index {index_name} already exists, skipping")
                continue
            
            # Create index command
            columns_str = ', '.join(columns)
            index_command = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str});"
            index_commands.append(index_command)
            
            print(f"🔧 Will create: {index_command}")
            
            if not dry_run:
                try:
                    start_time = time.time()
                    self.db.execute(text(index_command))
                    self.db.commit()
                    execution_time = time.time() - start_time
                    print(f"✅ Created {index_name} in {execution_time:.4f}s")
                except Exception as e:
                    print(f"❌ Error creating {index_name}: {e}")
                    self.db.rollback()
        
        if dry_run:
            print("\n💡 To create these indexes, run with dry_run=False")
            return index_commands
        
        return index_commands
    
    def benchmark_before_after(self):
        """Benchmark performance before and after optimization"""
        print("\n🏁 Performance Benchmark")
        print("=" * 30)
        
        # Run initial benchmark
        print("📊 BEFORE Optimization:")
        before_results = self.analyze_query_performance()
        
        # Create indexes
        print("\n🔧 Creating Indexes...")
        self.create_performance_indexes(dry_run=False)
        
        # Run benchmark again
        print("\n📊 AFTER Optimization:")
        after_results = self.analyze_query_performance()
        
        # Compare results
        print("\n📈 Performance Comparison:")
        print("=" * 30)
        
        for query_name in before_results:
            if query_name in after_results:
                before_time = before_results[query_name]['time']
                after_time = after_results[query_name]['time']
                
                if before_time > 0:
                    improvement = ((before_time - after_time) / before_time) * 100
                    if improvement > 0:
                        print(f"⚡ {query_name}: {improvement:.1f}% faster ({before_time:.4f}s → {after_time:.4f}s)")
                    else:
                        print(f"⚠️  {query_name}: {abs(improvement):.1f}% slower ({before_time:.4f}s → {after_time:.4f}s)")
                else:
                    print(f"📊 {query_name}: {before_time:.4f}s → {after_time:.4f}s")
    
    def run_full_analysis(self):
        """Run complete database optimization analysis"""
        print("🚀 Database Performance Optimization Analysis")
        print("=" * 60)
        
        # Current performance
        query_results = self.analyze_query_performance()
        
        # Existing indexes
        index_info = self.check_existing_indexes()
        
        # Table statistics
        self.analyze_table_statistics()
        
        # Recommendations
        recommendations = self.recommend_indexes()
        
        # Show index creation commands (dry run)
        index_commands = self.create_performance_indexes(dry_run=True)
        
        # Summary
        print("\n🎯 Summary")
        print("=" * 20)
        
        slow_queries = [name for name, result in query_results.items() 
                       if result.get('time', 0) > 0.5]
        
        if slow_queries:
            print(f"🐌 Slow queries detected: {len(slow_queries)}")
            for query in slow_queries:
                print(f"  - {query}: {query_results[query]['time']:.4f}s")
        else:
            print("✅ No slow queries detected")
        
        print(f"📊 Current indexes: FVG={len(index_info['fvg_indexes'])}, Pivot={len(index_info['pivot_indexes'])}")
        print(f"💡 Recommended indexes: {len(recommendations)}")
        print(f"🔧 Index commands ready: {len(index_commands)}")
        
        if slow_queries:
            print("\n💡 Next Steps:")
            print("  1. Run with create_indexes=True to create recommended indexes")
            print("  2. Monitor query performance after index creation")
            print("  3. Consider query optimization if indexes don't help")
        
        return {
            'query_results': query_results,
            'index_info': index_info,
            'recommendations': recommendations,
            'index_commands': index_commands
        }
    
    def __del__(self):
        """Cleanup database connection"""
        if hasattr(self, 'db'):
            self.db.close()

if __name__ == "__main__":
    optimizer = DatabaseOptimizer()
    
    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--create-indexes":
        print("🚀 Running with index creation enabled")
        optimizer.benchmark_before_after()
    else:
        print("🔍 Running analysis mode (no index creation)")
        optimizer.run_full_analysis()
        print("\n💡 To create indexes, run with --create-indexes flag")
