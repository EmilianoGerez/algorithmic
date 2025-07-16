#!/usr/bin/env python3
"""
FVG Query Optimization Script
Investigates and fixes the slow FVG Active Query performance issue
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
from sqlalchemy import text, func

from src.db.session import SessionLocal
from src.db.models.fvg import FVG

def investigate_fvg_query_performance():
    """Investigate why FVG Active Query is slow"""
    print("🔍 Investigating FVG Active Query Performance")
    print("=" * 50)
    
    db = SessionLocal()
    
    try:
        # Check current indexes
        print("📊 Current FVG Table Indexes:")
        result = db.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'fvg';"))
        for row in result:
            print(f"  🔑 {row.indexname}")
            print(f"      {row.indexdef}")
        
        # Check table statistics
        print("\n📊 Table Statistics:")
        result = db.execute(text("SELECT COUNT(*) as total_rows FROM fvg;"))
        total_rows = result.scalar()
        print(f"  Total FVG records: {total_rows}")
        
        # Check status distribution
        print("\n📊 Status Distribution:")
        result = db.execute(text("SELECT status, COUNT(*) as count FROM fvg GROUP BY status ORDER BY count DESC;"))
        for row in result:
            print(f"  {row.status}: {row.count}")
        
        # Test different query approaches
        print("\n⏱️  Query Performance Tests:")
        
        # Method 1: Original query
        start_time = time.time()
        active_count_1 = db.query(FVG).filter(FVG.status == "active").count()
        time_1 = time.time() - start_time
        print(f"  1. SQLAlchemy ORM count(): {active_count_1} results in {time_1:.4f}s")
        
        # Method 2: Raw SQL count
        start_time = time.time()
        result = db.execute(text("SELECT COUNT(*) FROM fvg WHERE status = 'active';"))
        active_count_2 = result.scalar()
        time_2 = time.time() - start_time
        print(f"  2. Raw SQL count: {active_count_2} results in {time_2:.4f}s")
        
        # Method 3: SQLAlchemy func.count
        start_time = time.time()
        active_count_3 = db.query(func.count(FVG.id)).filter(FVG.status == "active").scalar()
        time_3 = time.time() - start_time
        print(f"  3. SQLAlchemy func.count: {active_count_3} results in {time_3:.4f}s")
        
        # Method 4: Get actual records (not just count)
        start_time = time.time()
        active_records = db.query(FVG).filter(FVG.status == "active").all()
        time_4 = time.time() - start_time
        print(f"  4. Get all records: {len(active_records)} results in {time_4:.4f}s")
        
        # Method 5: Limited query
        start_time = time.time()
        active_limited = db.query(FVG).filter(FVG.status == "active").limit(10).all()
        time_5 = time.time() - start_time
        print(f"  5. Limited to 10 records: {len(active_limited)} results in {time_5:.4f}s")
        
        # Check query plan
        print("\n🔍 Query Execution Plan:")
        result = db.execute(text("EXPLAIN ANALYZE SELECT COUNT(*) FROM fvg WHERE status = 'active';"))
        for row in result:
            print(f"  {row[0]}")
        
        # Check if index is being used
        print("\n🔍 Index Usage Analysis:")
        result = db.execute(text("""
            SELECT 
                schemaname, 
                tablename, 
                indexname, 
                idx_scan, 
                idx_tup_read, 
                idx_tup_fetch
            FROM pg_stat_user_indexes 
            WHERE tablename = 'fvg';
        """))
        
        for row in result:
            print(f"  Index: {row.indexname}")
            print(f"    Scans: {row.idx_scan}")
            print(f"    Tuples Read: {row.idx_tup_read}")
            print(f"    Tuples Fetched: {row.idx_tup_fetch}")
        
        # Performance comparison
        print(f"\n📈 Performance Comparison:")
        fastest_time = min(time_1, time_2, time_3, time_4, time_5)
        slowest_time = max(time_1, time_2, time_3, time_4, time_5)
        
        print(f"  Fastest method: {fastest_time:.4f}s")
        print(f"  Slowest method: {slowest_time:.4f}s")
        print(f"  Performance difference: {slowest_time / fastest_time:.1f}x")
        
        # Check for potential issues
        print(f"\n🔍 Potential Issues:")
        if time_1 > 1.0:
            print("  🚨 ORM query is very slow - consider using raw SQL")
        if time_2 < time_1 * 0.5:
            print("  💡 Raw SQL is significantly faster than ORM")
        if time_4 < time_1:
            print("  💡 Getting all records is faster than count() - possible ORM issue")
        
        return {
            'orm_count_time': time_1,
            'raw_sql_time': time_2,
            'func_count_time': time_3,
            'all_records_time': time_4,
            'limited_records_time': time_5,
            'active_count': active_count_1
        }
        
    except Exception as e:
        print(f"❌ Error during investigation: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()

def optimize_fvg_query():
    """Apply optimizations to fix the slow query"""
    print("\n🔧 Applying FVG Query Optimizations")
    print("=" * 40)
    
    db = SessionLocal()
    
    try:
        # Check if status index exists
        result = db.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = 'fvg' AND indexname = 'idx_fvg_status';"))
        status_index_exists = result.fetchone() is not None
        
        if not status_index_exists:
            print("🔧 Creating status index...")
            start_time = time.time()
            db.execute(text("CREATE INDEX CONCURRENTLY idx_fvg_status ON fvg (status);"))
            db.commit()
            creation_time = time.time() - start_time
            print(f"✅ Status index created in {creation_time:.4f}s")
        else:
            print("✅ Status index already exists")
        
        # Test if there are any table maintenance issues
        print("\n🔧 Table Maintenance Check:")
        
        # Check for table bloat
        result = db.execute(text("""
            SELECT 
                schemaname, 
                tablename, 
                n_tup_ins, 
                n_tup_upd, 
                n_tup_del, 
                n_dead_tup,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables 
            WHERE tablename = 'fvg';
        """))
        
        for row in result:
            print(f"  Inserts: {row.n_tup_ins}")
            print(f"  Updates: {row.n_tup_upd}")
            print(f"  Deletes: {row.n_tup_del}")
            print(f"  Dead tuples: {row.n_dead_tup}")
            print(f"  Last vacuum: {row.last_vacuum}")
            print(f"  Last analyze: {row.last_analyze}")
            
            # Check if table needs maintenance
            if row.n_dead_tup and row.n_dead_tup > 100:
                print("⚠️  Table has dead tuples - consider VACUUM")
            
            if not row.last_analyze:
                print("⚠️  Table statistics may be outdated - consider ANALYZE")
        
        # Run ANALYZE to update table statistics
        print("\n🔧 Updating table statistics...")
        start_time = time.time()
        db.execute(text("ANALYZE fvg;"))
        db.commit()
        analyze_time = time.time() - start_time
        print(f"✅ Table statistics updated in {analyze_time:.4f}s")
        
        # Test query performance after optimization
        print("\n⏱️  Testing Query Performance After Optimization:")
        
        start_time = time.time()
        active_count = db.query(FVG).filter(FVG.status == "active").count()
        optimized_time = time.time() - start_time
        print(f"  Optimized query: {active_count} results in {optimized_time:.4f}s")
        
        return optimized_time
        
    except Exception as e:
        print(f"❌ Error during optimization: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()

def create_optimized_query_methods():
    """Create optimized methods for common FVG queries"""
    print("\n💡 Optimized Query Methods")
    print("=" * 30)
    
    optimization_code = '''
# Add these optimized methods to your service classes:

class OptimizedFVGQueries:
    def __init__(self, db_session):
        self.db = db_session
    
    def get_active_fvgs_fast(self, symbol=None, limit=None):
        """Fast method to get active FVGs using raw SQL"""
        query = "SELECT * FROM fvg WHERE status = 'active'"
        params = {}
        
        if symbol:
            query += " AND symbol = :symbol"
            params['symbol'] = symbol
        
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += " LIMIT :limit"
            params['limit'] = limit
        
        result = self.db.execute(text(query), params)
        return result.fetchall()
    
    def count_active_fvgs_fast(self, symbol=None):
        """Fast method to count active FVGs"""
        query = "SELECT COUNT(*) FROM fvg WHERE status = 'active'"
        params = {}
        
        if symbol:
            query += " AND symbol = :symbol"
            params['symbol'] = symbol
        
        result = self.db.execute(text(query), params)
        return result.scalar()
    
    def get_fvg_status_distribution(self):
        """Get FVG status distribution efficiently"""
        query = """
        SELECT status, COUNT(*) as count 
        FROM fvg 
        GROUP BY status 
        ORDER BY count DESC
        """
        result = self.db.execute(text(query))
        return {row.status: row.count for row in result}
'''
    
    print(optimization_code)

if __name__ == "__main__":
    print("🚀 FVG Query Performance Investigation & Optimization")
    print("=" * 60)
    
    # Investigate current performance
    investigation_results = investigate_fvg_query_performance()
    
    if investigation_results:
        # Apply optimizations
        optimized_time = optimize_fvg_query()
        
        if optimized_time and investigation_results['orm_count_time'] > 0:
            improvement = investigation_results['orm_count_time'] / optimized_time
            print(f"\n📈 Performance Improvement: {improvement:.1f}x faster")
            print(f"  Before: {investigation_results['orm_count_time']:.4f}s")
            print(f"  After: {optimized_time:.4f}s")
        
        # Show optimized query methods
        create_optimized_query_methods()
        
        print("\n🎯 Optimization Complete!")
        print("Consider implementing the optimized query methods in your service layer.")
