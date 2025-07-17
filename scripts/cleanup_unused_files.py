#!/usr/bin/env python3
"""
Project Cleanup Script
Removes unused scripts and files, keeping only essential ones
"""

import os
import shutil
from pathlib import Path

def cleanup_project():
    """
    Clean up unused files and scripts
    """
    base_path = Path("/Users/emilianogerez/Projects/interviews/Frontend/MarketProject/algorithmic")
    
    print("🧹 CLEANING UP UNUSED FILES AND SCRIPTS")
    print("=" * 60)
    
    # Files to KEEP (essential/working files)
    keep_files = {
        # Core working scripts
        "scripts/original_rules_enhanced_fvg.py",  # Current working backtest
        "scripts/working_statistical_backtest.py",  # Comprehensive statistical backtest
        "scripts/working_clean_backtesting.py",     # Reference implementation
        
        # Utility scripts that might be needed
        "scripts/demo_refactored_system.py",        # Demo system
        "scripts/plot_strategy.py",                 # Plotting utilities
        "scripts/plot_strategy_main.py",            # Main plotting
        
        # Keep these for reference/debugging if needed
        "scripts/test_unified_fvg_system.py",       # FVG system testing
        "scripts/debug_fvg_detection.py",           # FVG debugging
        "scripts/populate_pools.py",                # Pool population utility
    }
    
    # Documentation files to KEEP
    keep_docs = {
        "REFACTORED_ARCHITECTURE.md",
        "REFACTORING_SUMMARY.md",
        "UNIFIED_FVG_SYSTEM.md",
        "FVG_UNIFICATION_SUMMARY.md",
        "structure_break_improvements.md",
    }
    
    # Remove unused documentation files
    doc_files_to_remove = [
        "CORRECTED_ORDER_FLOW_LOGIC.md",
        "ENHANCED_FVG_DETECTION_SUMMARY.md",
        "FRESH_BACKTEST_RESULTS.md",
        "POSITION_SNAPSHOTS_SUMMARY.md",
        "STRATEGY_EVALUATION_REPORT.md",
    ]
    
    print("\n📋 REMOVING UNUSED DOCUMENTATION FILES")
    print("-" * 50)
    removed_docs = 0
    for doc_file in doc_files_to_remove:
        file_path = base_path / doc_file
        if file_path.exists():
            file_path.unlink()
            print(f"   🗑️  Removed: {doc_file}")
            removed_docs += 1
    
    print(f"✅ Removed {removed_docs} unused documentation files")
    
    # Get all script files
    scripts_dir = base_path / "scripts"
    all_scripts = list(scripts_dir.glob("*.py"))
    
    print(f"\n📋 ANALYZING {len(all_scripts)} SCRIPT FILES")
    print("-" * 50)
    
    # Identify scripts to remove
    scripts_to_remove = []
    keep_scripts = []
    
    for script in all_scripts:
        relative_path = str(script.relative_to(base_path))
        if relative_path in keep_files:
            keep_scripts.append(script)
            print(f"   ✅ KEEP: {script.name}")
        else:
            scripts_to_remove.append(script)
            print(f"   🗑️  REMOVE: {script.name}")
    
    print(f"\n📊 CLEANUP SUMMARY")
    print("-" * 50)
    print(f"Total scripts: {len(all_scripts)}")
    print(f"Scripts to keep: {len(keep_scripts)}")
    print(f"Scripts to remove: {len(scripts_to_remove)}")
    
    # Ask for confirmation
    print(f"\n⚠️  WARNING: This will permanently delete {len(scripts_to_remove)} script files!")
    confirm = input("Do you want to proceed? (y/N): ").lower().strip()
    
    if confirm == 'y':
        print(f"\n🗑️  REMOVING {len(scripts_to_remove)} UNUSED SCRIPTS")
        print("-" * 50)
        
        removed_scripts = 0
        for script in scripts_to_remove:
            try:
                script.unlink()
                print(f"   ✅ Removed: {script.name}")
                removed_scripts += 1
            except Exception as e:
                print(f"   ❌ Error removing {script.name}: {e}")
        
        print(f"\n✅ Successfully removed {removed_scripts} unused scripts")
        
        # Clean up __pycache__ directories
        print(f"\n🧹 CLEANING UP __pycache__ DIRECTORIES")
        print("-" * 50)
        
        pycache_dirs = list(base_path.rglob("__pycache__"))
        removed_cache = 0
        for cache_dir in pycache_dirs:
            try:
                shutil.rmtree(cache_dir)
                print(f"   ✅ Removed: {cache_dir.relative_to(base_path)}")
                removed_cache += 1
            except Exception as e:
                print(f"   ❌ Error removing {cache_dir}: {e}")
        
        print(f"\n✅ CLEANUP COMPLETED!")
        print("=" * 60)
        print(f"📊 FINAL SUMMARY:")
        print(f"   • Removed {removed_docs} documentation files")
        print(f"   • Removed {removed_scripts} script files")
        print(f"   • Removed {removed_cache} __pycache__ directories")
        print(f"   • Kept {len(keep_scripts)} essential scripts")
        
        print(f"\n🎯 REMAINING ESSENTIAL SCRIPTS:")
        for script in keep_scripts:
            print(f"   • {script.name}")
        
    else:
        print("\n❌ Cleanup cancelled by user")

if __name__ == "__main__":
    cleanup_project()
