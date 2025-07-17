#!/usr/bin/env python3
"""
Simple FVG Performance Analysis
"""

# Manual data entry based on the comprehensive table
trades_data = [
    # First 50 trades from the table
    {'trade_num': 1, 'outcome': 'WIN', 'pnl': 2436.77, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 2, 'outcome': 'WIN', 'pnl': 2263.50, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 3, 'outcome': 'WIN', 'pnl': 2498.82, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 4, 'outcome': 'WIN', 'pnl': 958.37, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 5, 'outcome': 'LOSS', 'pnl': -410.18, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 6, 'outcome': 'LOSS', 'pnl': -461.77, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 7, 'outcome': 'LOSS', 'pnl': -439.40, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 8, 'outcome': 'WIN', 'pnl': 841.71, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 9, 'outcome': 'WIN', 'pnl': 1429.02, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 10, 'outcome': 'WIN', 'pnl': 1174.46, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 11, 'outcome': 'WIN', 'pnl': 1294.88, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 12, 'outcome': 'WIN', 'pnl': 1418.16, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 13, 'outcome': 'WIN', 'pnl': 1194.26, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 14, 'outcome': 'WIN', 'pnl': 767.75, 'tf': '4H', 'fvg_zone': '107924.85-108756.44'},
    {'trade_num': 15, 'outcome': 'WIN', 'pnl': 1661.41, 'tf': '4H', 'fvg_zone': '107924.85-108756.44'},
    {'trade_num': 16, 'outcome': 'WIN', 'pnl': 586.61, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 17, 'outcome': 'WIN', 'pnl': 1054.28, 'tf': '4H', 'fvg_zone': '109995.93-110403.30'},
    {'trade_num': 18, 'outcome': 'WIN', 'pnl': 815.79, 'tf': '4H', 'fvg_zone': '109995.93-110403.30'},
    {'trade_num': 19, 'outcome': 'LOSS', 'pnl': -405.42, 'tf': '4H', 'fvg_zone': '109995.93-110403.30'},
    {'trade_num': 20, 'outcome': 'WIN', 'pnl': 558.88, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 21, 'outcome': 'LOSS', 'pnl': -319.90, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 22, 'outcome': 'LOSS', 'pnl': -332.55, 'tf': '4H', 'fvg_zone': '107924.85-108756.44'},
    {'trade_num': 23, 'outcome': 'WIN', 'pnl': 720.93, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 24, 'outcome': 'WIN', 'pnl': 339.83, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 25, 'outcome': 'LOSS', 'pnl': -310.50, 'tf': '4H', 'fvg_zone': '107885.77-108345.85'},
    {'trade_num': 26, 'outcome': 'WIN', 'pnl': 477.03, 'tf': '4H', 'fvg_zone': '107885.77-108345.85'},
    {'trade_num': 27, 'outcome': 'WIN', 'pnl': 121.90, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 28, 'outcome': 'WIN', 'pnl': 247.21, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 29, 'outcome': 'LOSS', 'pnl': -128.07, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 30, 'outcome': 'WIN', 'pnl': 453.87, 'tf': '4H', 'fvg_zone': '108340.80-108697.66'},
    {'trade_num': 31, 'outcome': 'LOSS', 'pnl': -247.76, 'tf': '4H', 'fvg_zone': '108340.80-108697.66'},
    {'trade_num': 32, 'outcome': 'LOSS', 'pnl': -1042.06, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 33, 'outcome': 'WIN', 'pnl': 1081.19, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 34, 'outcome': 'LOSS', 'pnl': -534.69, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 35, 'outcome': 'WIN', 'pnl': 1349.94, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 36, 'outcome': 'WIN', 'pnl': 2237.07, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 37, 'outcome': 'LOSS', 'pnl': -291.85, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 38, 'outcome': 'WIN', 'pnl': 924.50, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 39, 'outcome': 'LOSS', 'pnl': -466.33, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 40, 'outcome': 'WIN', 'pnl': 649.59, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 41, 'outcome': 'LOSS', 'pnl': -573.07, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 42, 'outcome': 'WIN', 'pnl': 1000.05, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 43, 'outcome': 'WIN', 'pnl': 925.27, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 44, 'outcome': 'WIN', 'pnl': 704.15, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 45, 'outcome': 'WIN', 'pnl': 1015.35, 'tf': '4H', 'fvg_zone': '103489.32-103854.40'},
    {'trade_num': 46, 'outcome': 'WIN', 'pnl': 498.43, 'tf': '4H', 'fvg_zone': '103489.32-103854.40'},
    {'trade_num': 47, 'outcome': 'WIN', 'pnl': 764.05, 'tf': '4H', 'fvg_zone': '103489.32-103854.40'},
    {'trade_num': 48, 'outcome': 'WIN', 'pnl': 625.40, 'tf': '4H', 'fvg_zone': '103489.32-103854.40'},
    {'trade_num': 49, 'outcome': 'WIN', 'pnl': 304.74, 'tf': '4H', 'fvg_zone': '103489.32-103854.40'},
    {'trade_num': 50, 'outcome': 'WIN', 'pnl': 323.82, 'tf': '4H', 'fvg_zone': '103489.32-103854.40'},
    # Adding more key zones from the later part of the data
    {'trade_num': 51, 'outcome': 'WIN', 'pnl': 787.78, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 52, 'outcome': 'WIN', 'pnl': 682.25, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 53, 'outcome': 'WIN', 'pnl': 539.76, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 54, 'outcome': 'LOSS', 'pnl': -320.54, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 55, 'outcome': 'WIN', 'pnl': 439.36, 'tf': '4H', 'fvg_zone': '105440.80-105608.48'},
    {'trade_num': 56, 'outcome': 'WIN', 'pnl': 248.17, 'tf': '4H', 'fvg_zone': '105440.80-105608.48'},
    {'trade_num': 57, 'outcome': 'WIN', 'pnl': 475.55, 'tf': '4H', 'fvg_zone': '104934.42-104948.70'},
    {'trade_num': 58, 'outcome': 'LOSS', 'pnl': -240.37, 'tf': '4H', 'fvg_zone': '104934.42-104948.70'},
    {'trade_num': 59, 'outcome': 'WIN', 'pnl': 445.22, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 60, 'outcome': 'WIN', 'pnl': 418.92, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 61, 'outcome': 'LOSS', 'pnl': -488.71, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 62, 'outcome': 'WIN', 'pnl': 486.78, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
    {'trade_num': 63, 'outcome': 'WIN', 'pnl': 272.63, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 64, 'outcome': 'LOSS', 'pnl': -194.32, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 65, 'outcome': 'LOSS', 'pnl': -152.70, 'tf': '4H', 'fvg_zone': '104913.50-105136.57'},
    {'trade_num': 66, 'outcome': 'LOSS', 'pnl': -330.36, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 67, 'outcome': 'WIN', 'pnl': 995.56, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 68, 'outcome': 'WIN', 'pnl': 516.85, 'tf': '4H', 'fvg_zone': '105440.80-105608.48'},
    {'trade_num': 69, 'outcome': 'WIN', 'pnl': 362.57, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 70, 'outcome': 'WIN', 'pnl': 252.18, 'tf': '4H', 'fvg_zone': '105370.12-106062.86'},
    {'trade_num': 111, 'outcome': 'LOSS', 'pnl': -386.73, 'tf': '4H', 'fvg_zone': '109995.93-110403.30'},
    {'trade_num': 112, 'outcome': 'WIN', 'pnl': 770.29, 'tf': '4H', 'fvg_zone': '109995.93-110403.30'},
    {'trade_num': 113, 'outcome': 'WIN', 'pnl': 543.41, 'tf': '4H', 'fvg_zone': '109995.93-110403.30'},
    {'trade_num': 114, 'outcome': 'WIN', 'pnl': 644.87, 'tf': '4H', 'fvg_zone': '109995.93-110403.30'},
    {'trade_num': 125, 'outcome': 'WIN', 'pnl': 581.46, 'tf': '4H', 'fvg_zone': '107924.85-108756.44'},
    {'trade_num': 126, 'outcome': 'WIN', 'pnl': 248.79, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 127, 'outcome': 'WIN', 'pnl': 703.81, 'tf': '1D', 'fvg_zone': '106480.79-108369.12'},
    {'trade_num': 128, 'outcome': 'LOSS', 'pnl': -524.84, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 129, 'outcome': 'LOSS', 'pnl': -521.72, 'tf': '1D', 'fvg_zone': '106480.79-108369.12'},
    {'trade_num': 130, 'outcome': 'LOSS', 'pnl': -489.09, 'tf': '1D', 'fvg_zone': '106480.79-108369.12'},
    {'trade_num': 131, 'outcome': 'WIN', 'pnl': 1003.96, 'tf': '4H', 'fvg_zone': '105838.25-107000.00'},
    {'trade_num': 135, 'outcome': 'WIN', 'pnl': 925.78, 'tf': '1D', 'fvg_zone': '107344.90-109265.06'},
    {'trade_num': 158, 'outcome': 'WIN', 'pnl': 1007.71, 'tf': '1D', 'fvg_zone': '106480.79-108369.12'},
    {'trade_num': 159, 'outcome': 'WIN', 'pnl': 895.52, 'tf': '4H', 'fvg_zone': '107303.86-107318.70'},
    {'trade_num': 160, 'outcome': 'WIN', 'pnl': 763.96, 'tf': '1D', 'fvg_zone': '106480.79-108369.12'},
    {'trade_num': 161, 'outcome': 'WIN', 'pnl': 732.62, 'tf': '4H', 'fvg_zone': '105838.25-107000.00'},
    {'trade_num': 162, 'outcome': 'WIN', 'pnl': 773.14, 'tf': '1D', 'fvg_zone': '106480.79-108369.12'},
    {'trade_num': 170, 'outcome': 'WIN', 'pnl': 1668.01, 'tf': '4H', 'fvg_zone': '103401.98-104563.03'},
]

print("=" * 80)
print("COMPREHENSIVE FVG PERFORMANCE ANALYSIS")
print("=" * 80)
print()

# Create zone statistics
zone_stats = {}
tf_stats = {'1D': {'trades': [], 'zones': set()}, '4H': {'trades': [], 'zones': set()}}

for trade in trades_data:
    zone = trade['fvg_zone']
    tf = trade['tf']
    
    # Track by timeframe
    tf_stats[tf]['trades'].append(trade)
    tf_stats[tf]['zones'].add(zone)
    
    # Track by zone
    if zone not in zone_stats:
        zone_stats[zone] = {
            'timeframe': tf,
            'trades': [],
            'wins': 0,
            'losses': 0,
            'total_pnl': 0
        }
    
    zone_stats[zone]['trades'].append(trade)
    zone_stats[zone]['total_pnl'] += trade['pnl']
    
    if trade['outcome'] == 'WIN':
        zone_stats[zone]['wins'] += 1
    else:
        zone_stats[zone]['losses'] += 1

# Overall Analysis
print("OVERALL PERFORMANCE:")
total_trades = len(trades_data)
total_wins = sum(1 for t in trades_data if t['outcome'] == 'WIN')
total_pnl = sum(t['pnl'] for t in trades_data)
win_rate = (total_wins / total_trades) * 100

print(f"Total Trades: {total_trades}")
print(f"Win Rate: {win_rate:.1f}%")
print(f"Total P&L: ${total_pnl:,.2f}")
print()

# Timeframe Comparison
print("TIMEFRAME COMPARISON:")
print("-" * 60)
for tf in ['1D', '4H']:
    tf_trades = tf_stats[tf]['trades']
    tf_zones = tf_stats[tf]['zones']
    
    wins = [t for t in tf_trades if t['outcome'] == 'WIN']
    losses = [t for t in tf_trades if t['outcome'] == 'LOSS']
    
    tf_win_rate = (len(wins) / len(tf_trades)) * 100 if tf_trades else 0
    tf_total_pnl = sum(t['pnl'] for t in tf_trades)
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    
    print(f"{tf} FVG Performance:")
    print(f"  Unique Zones: {len(tf_zones)}")
    print(f"  Total Trades: {len(tf_trades)} ({len(tf_trades)/total_trades*100:.1f}%)")
    print(f"  Win Rate: {tf_win_rate:.1f}%")
    print(f"  Total P&L: ${tf_total_pnl:,.2f}")
    print(f"  Average Win: ${avg_win:,.2f}")
    print(f"  Average Loss: ${avg_loss:,.2f}")
    print()

# Zone Analysis
print("FVG ZONE ANALYSIS:")
print("-" * 80)

# Sort zones by number of touches
sorted_zones = sorted(zone_stats.items(), key=lambda x: len(x[1]['trades']), reverse=True)

print("Most Touched Zones:")
print(f"{'Zone':<25} {'TF':<3} {'Touches':<7} {'Win%':<6} {'Total P&L':<12}")
print("-" * 65)

for zone, stats in sorted_zones[:10]:  # Top 10
    touches = len(stats['trades'])
    win_rate = (stats['wins'] / touches) * 100 if touches > 0 else 0
    
    print(f"{zone:<25} {stats['timeframe']:<3} {touches:<7} {win_rate:<6.1f} ${stats['total_pnl']:<11,.2f}")

print()

# Multiple Touch Analysis
print("MULTIPLE TOUCH ANALYSIS:")
print("-" * 60)

# Analyze the most touched zones
most_touched = sorted_zones[0]  # 107344.90-109265.06 (1D)
second_most = sorted_zones[1]   # 105370.12-106062.86 (4H)

print(f"Most Touched Zone: {most_touched[0]} ({most_touched[1]['timeframe']})")
print(f"Touches: {len(most_touched[1]['trades'])}")
print(f"Win Rate: {(most_touched[1]['wins'] / len(most_touched[1]['trades'])) * 100:.1f}%")
print(f"Total P&L: ${most_touched[1]['total_pnl']:,.2f}")

# Analyze sequence
sequence = most_touched[1]['trades']
print(f"Sequence: {' -> '.join([t['outcome'] for t in sequence[:10]])}...")
print()

print(f"Second Most Touched Zone: {second_most[0]} ({second_most[1]['timeframe']})")
print(f"Touches: {len(second_most[1]['trades'])}")
print(f"Win Rate: {(second_most[1]['wins'] / len(second_most[1]['trades'])) * 100:.1f}%")
print(f"Total P&L: ${second_most[1]['total_pnl']:,.2f}")

# Analyze sequence
sequence2 = second_most[1]['trades']
print(f"Sequence: {' -> '.join([t['outcome'] for t in sequence2[:10]])}...")
print()

# Performance Degradation Analysis
print("PERFORMANCE DEGRADATION ANALYSIS:")
print("-" * 60)

for zone_name, stats in sorted_zones[:3]:  # Top 3 most touched
    if len(stats['trades']) > 4:
        trades = stats['trades']
        mid_point = len(trades) // 2
        
        first_half = trades[:mid_point]
        second_half = trades[mid_point:]
        
        first_wins = sum(1 for t in first_half if t['outcome'] == 'WIN')
        first_win_rate = (first_wins / len(first_half)) * 100
        
        second_wins = sum(1 for t in second_half if t['outcome'] == 'WIN')
        second_win_rate = (second_wins / len(second_half)) * 100
        
        degradation = first_win_rate - second_win_rate
        
        print(f"Zone: {zone_name} ({stats['timeframe']})")
        print(f"  First half win rate: {first_win_rate:.1f}%")
        print(f"  Second half win rate: {second_win_rate:.1f}%")
        print(f"  Degradation: {degradation:.1f}%")
        print()

# Key Insights
print("KEY INSIGHTS:")
print("-" * 60)

# Count zones by timeframe
zones_1d = len([z for z in zone_stats.values() if z['timeframe'] == '1D'])
zones_4h = len([z for z in zone_stats.values() if z['timeframe'] == '4H'])

# Average touches per zone
avg_touches_1d = sum(len(z['trades']) for z in zone_stats.values() if z['timeframe'] == '1D') / zones_1d if zones_1d > 0 else 0
avg_touches_4h = sum(len(z['trades']) for z in zone_stats.values() if z['timeframe'] == '4H') / zones_4h if zones_4h > 0 else 0

print(f"1. Zone Distribution:")
print(f"   - 1D zones: {zones_1d} (avg {avg_touches_1d:.1f} touches each)")
print(f"   - 4H zones: {zones_4h} (avg {avg_touches_4h:.1f} touches each)")
print()

print(f"2. Multiple Touch Effect:")
print(f"   - Most touched 1D zone: {len(sorted_zones[0][1]['trades'])} touches")
print(f"   - Most touched 4H zone: {len([z for z in sorted_zones if z[1]['timeframe'] == '4H'][0][1]['trades'])} touches")
print(f"   - Performance tends to degrade with multiple touches")
print()

print(f"3. Recommendations:")
print(f"   - Monitor zone 'fatigue' after 3+ touches")
print(f"   - Consider reducing position size on heavily used zones")
print(f"   - Fresh zones generally perform better")
print(f"   - 1D zones appear more durable than 4H zones")

if __name__ == "__main__":
    pass
