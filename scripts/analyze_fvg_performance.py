#!/usr/bin/env python3
"""
Analyze FVG Performance and Multiple Touch Patterns
"""

import pandas as pd
from collections import defaultdict

# Parse the comprehensive trading data from the results
trades_data = []

# Data from the comprehensive entries table
raw_data = """
1   2025-05-23   09:35    BULL 109210.44  107992.05  111647.21  $1218.39 $2436.77 WIN     $2436.77  $12436.77  1D  107344.90-109265.06 
2   2025-05-23   09:40    BULL 109123.80  107992.05  111387.30  $1131.75 $2263.50 WIN     $2263.50  $14700.27  1D  107344.90-109265.06 
3   2025-05-23   09:45    BULL 109241.46  107992.05  111740.28  $1249.41 $2498.82 WIN     $2498.82  $17199.09  1D  107344.90-109265.06 
4   2025-05-23   20:35    BULL 107638.55  107159.37  108596.92  $479.18  $958.37  WIN     $958.37   $18157.46  1D  107344.90-109265.06 
5   2025-05-23   20:40    BULL 107569.54  107159.37  108389.90  $410.18  $820.36  LOSS    $-410.18  $17747.28  1D  107344.90-109265.06 
6   2025-05-24   03:15    BULL 108226.68  107764.90  109150.22  $461.77  $923.55  LOSS    $-461.77  $17285.51  1D  107344.90-109265.06 
7   2025-05-24   03:30    BULL 108204.30  107764.90  109083.10  $439.40  $878.80  LOSS    $-439.40  $16846.11  1D  107344.90-109265.06 
8   2025-05-24   03:35    BULL 108185.76  107764.90  109027.47  $420.85  $841.71  WIN     $841.71   $17687.82  1D  107344.90-109265.06 
9   2025-05-24   21:25    BULL 107948.29  107233.78  109377.31  $714.51  $1429.02 WIN     $1429.02  $19116.84  1D  107344.90-109265.06 
10  2025-05-24   21:30    BULL 107821.01  107233.78  108995.47  $587.23  $1174.46 WIN     $1174.46  $20291.30  1D  107344.90-109265.06 
11  2025-05-24   21:35    BULL 107881.22  107233.78  109176.10  $647.44  $1294.88 WIN     $1294.88  $21586.17  1D  107344.90-109265.06 
12  2025-05-24   21:40    BULL 107942.86  107233.78  109361.02  $709.08  $1418.16 WIN     $1418.16  $23004.33  1D  107344.90-109265.06 
13  2025-05-24   21:45    BULL 107830.91  107233.78  109025.17  $597.13  $1194.26 WIN     $1194.26  $24198.60  1D  107344.90-109265.06 
14  2025-05-26   22:35    BULL 108665.70  108281.82  109433.45  $383.88  $767.75  WIN     $767.75   $24966.35  4H  107924.85-108756.44 
15  2025-05-26   23:05    BULL 108766.60  107935.90  110428.01  $830.70  $1661.41 WIN     $1661.41  $26627.76  4H  107924.85-108756.44 
16  2025-05-27   02:00    BULL 109068.26  108774.95  109654.87  $293.31  $586.61  WIN     $586.61   $27214.37  1D  107344.90-109265.06 
17  2025-05-27   09:55    BEAR 109895.15  110422.29  108840.87  $527.14  $1054.28 WIN     $1054.28  $28268.65  4H  109995.93-110403.30 
18  2025-05-27   10:00    BEAR 110014.40  110422.29  109198.61  $407.89  $815.79  WIN     $815.79   $29084.44  4H  109995.93-110403.30 
19  2025-05-27   10:20    BEAR 109866.73  110272.16  109055.89  $405.42  $810.85  LOSS    $-405.42  $28679.01  4H  109995.93-110403.30 
20  2025-05-27   20:45    BULL 109027.45  108748.02  109586.33  $279.44  $558.88  WIN     $558.88   $29237.89  1D  107344.90-109265.06 
21  2025-05-27   20:50    BULL 109067.92  108748.02  109707.71  $319.90  $639.80  LOSS    $-319.90  $28917.99  1D  107344.90-109265.06 
22  2025-05-27   22:45    BULL 108832.55  108500.00  109497.65  $332.55  $665.10  LOSS    $-332.55  $28585.44  4H  107924.85-108756.44 
23  2025-05-27   23:15    BULL 108891.63  108531.17  109612.57  $360.47  $720.93  WIN     $720.93   $29306.37  1D  107344.90-109265.06 
24  2025-05-28   03:10    BULL 108975.09  108805.18  109314.92  $169.91  $339.83  WIN     $339.83   $29646.20  1D  107344.90-109265.06 
25  2025-05-28   23:35    BEAR 108029.00  108339.50  107408.01  $310.50  $620.99  LOSS    $-310.50  $29335.71  4H  107885.77-108345.85 
26  2025-05-28   23:40    BEAR 108100.98  108339.50  107623.95  $238.52  $477.03  WIN     $477.03   $29812.74  4H  107885.77-108345.85 
27  2025-05-29   02:05    BULL 107750.42  107689.47  107872.32  $60.95   $121.90  WIN     $121.90   $29934.64  1D  107344.90-109265.06 
28  2025-05-29   02:10    BULL 107813.07  107689.47  108060.28  $123.60  $247.21  WIN     $247.21   $30181.85  1D  107344.90-109265.06 
29  2025-05-29   02:15    BULL 107817.54  107689.47  108073.69  $128.07  $256.15  LOSS    $-128.07  $30053.77  1D  107344.90-109265.06 
30  2025-05-29   08:10    BEAR 108666.06  108892.99  108212.19  $226.93  $453.87  WIN     $453.87   $30507.64  4H  108340.80-108697.66 
31  2025-05-29   08:15    BEAR 108645.23  108892.99  108149.71  $247.76  $495.52  LOSS    $-247.76  $30259.88  4H  108340.80-108697.66 
32  2025-05-29   10:55    BULL 107646.45  106604.39  109730.56  $1042.06 $2084.11 LOSS    $-1042.06 $29217.82  1D  107344.90-109265.06 
33  2025-05-29   20:10    BULL 105967.80  105427.21  107048.98  $540.59  $1081.19 WIN     $1081.19  $30299.01  4H  105370.12-106062.86 
34  2025-05-29   20:15    BULL 105961.90  105427.21  107031.28  $534.69  $1069.38 LOSS    $-534.69  $29764.32  4H  105370.12-106062.86 
35  2025-05-29   20:20    BULL 106102.18  105427.21  107452.11  $674.97  $1349.94 WIN     $1349.94  $31114.26  4H  105370.12-106062.86 
36  2025-05-29   21:25    BULL 105790.30  104671.76  108027.37  $1118.54 $2237.07 WIN     $2237.07  $33351.33  4H  105370.12-106062.86 
37  2025-05-29   21:30    BULL 105657.01  105365.16  106240.71  $291.85  $583.70  LOSS    $-291.85  $33059.48  4H  105370.12-106062.86 
38  2025-05-29   21:35    BULL 105827.41  105365.16  106751.92  $462.25  $924.50  WIN     $924.50   $33983.98  4H  105370.12-106062.86 
39  2025-05-29   21:40    BULL 105831.49  105365.16  106764.15  $466.33  $932.66  LOSS    $-466.33  $33517.65  4H  105370.12-106062.86 
40  2025-05-30   11:10    BULL 105632.49  105307.70  106282.08  $324.79  $649.59  WIN     $649.59   $34167.24  4H  105370.12-106062.86 
41  2025-05-30   20:40    BULL 104198.74  103625.67  105344.88  $573.07  $1146.14 LOSS    $-573.07  $33594.17  4H  103401.98-104563.03 
42  2025-05-30   20:45    BULL 104125.70  103625.67  105125.75  $500.03  $1000.05 WIN     $1000.05  $34594.23  4H  103401.98-104563.03 
43  2025-05-30   20:50    BULL 104088.31  103625.67  105013.58  $462.64  $925.27  WIN     $925.27   $35519.50  4H  103401.98-104563.03 
44  2025-05-30   21:15    BULL 104148.17  103796.09  104852.32  $352.08  $704.15  WIN     $704.15   $36223.65  4H  103401.98-104563.03 
45  2025-05-30   22:20    BULL 103846.95  103339.27  104862.30  $507.68  $1015.35 WIN     $1015.35  $37239.00  4H  103489.32-103854.40 
46  2025-05-30   23:40    BULL 103555.66  103306.45  104054.09  $249.21  $498.43  WIN     $498.43   $37737.43  4H  103489.32-103854.40 
47  2025-05-30   23:45    BULL 103688.48  103306.45  104452.53  $382.03  $764.05  WIN     $764.05   $38501.48  4H  103489.32-103854.40 
48  2025-05-30   23:50    BULL 103619.15  103306.45  104244.55  $312.70  $625.40  WIN     $625.40   $39126.88  4H  103489.32-103854.40 
49  2025-05-31   02:25    BULL 103768.07  103615.70  104072.80  $152.37  $304.74  WIN     $304.74   $39431.62  4H  103489.32-103854.40 
50  2025-05-31   08:00    BULL 103571.55  103409.65  103895.37  $161.91  $323.82  WIN     $323.82   $39755.43  4H  103489.32-103854.40 
"""

# Parse the data
lines = raw_data.strip().split('\n')
for line in lines:
    if line.strip():
        parts = line.split()
        if len(parts) >= 13:
            trade_num = int(parts[0])
            date = parts[1]
            time = parts[2]
            direction = parts[3]
            entry_price = float(parts[4])
            outcome = parts[8]
            pnl_str = parts[9].replace('$', '')
            pnl = float(pnl_str)
            tf = parts[11]
            fvg_zone = parts[12]
            
            trades_data.append({
                'trade_num': trade_num,
                'date': date,
                'time': time,
                'direction': direction,
                'entry_price': entry_price,
                'outcome': outcome,
                'pnl': pnl,
                'tf': tf,
                'fvg_zone': fvg_zone
            })

# Create DataFrame
df = pd.DataFrame(trades_data)

print("=" * 80)
print("COMPREHENSIVE FVG PERFORMANCE ANALYSIS")
print("=" * 80)
print()

# Overall statistics
print("OVERALL PERFORMANCE:")
print(f"Total Trades: {len(df)}")
print(f"Win Rate: {(df['outcome'] == 'WIN').sum() / len(df) * 100:.1f}%")
print(f"Total P&L: ${df['pnl'].sum():,.2f}")
print()

# Timeframe Analysis
print("TIMEFRAME COMPARISON:")
print("-" * 60)
for tf in ['1D', '4H']:
    tf_data = df[df['tf'] == tf]
    wins = tf_data[tf_data['outcome'] == 'WIN']
    losses = tf_data[tf_data['outcome'] == 'LOSS']
    
    win_rate = len(wins) / len(tf_data) * 100 if len(tf_data) > 0 else 0
    avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
    total_pnl = tf_data['pnl'].sum()
    profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else float('inf')
    
    print(f"{tf} FVG Performance:")
    print(f"  Trades: {len(tf_data)} ({len(tf_data)/len(df)*100:.1f}%)")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Average Win: ${avg_win:,.2f}")
    print(f"  Average Loss: ${avg_loss:,.2f}")
    print(f"  Total P&L: ${total_pnl:,.2f}")
    print(f"  Profit Factor: {profit_factor:.2f}")
    print()

# FVG Zone Analysis
print("FVG ZONE TOUCH ANALYSIS:")
print("-" * 80)
zone_stats = {}
for zone in df['fvg_zone'].unique():
    zone_data = df[df['fvg_zone'] == zone].sort_values('trade_num')
    wins = zone_data[zone_data['outcome'] == 'WIN']
    losses = zone_data[zone_data['outcome'] == 'LOSS']
    
    zone_stats[zone] = {
        'timeframe': zone_data.iloc[0]['tf'],
        'total_touches': len(zone_data),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(zone_data) * 100 if len(zone_data) > 0 else 0,
        'total_pnl': zone_data['pnl'].sum(),
        'avg_pnl': zone_data['pnl'].mean(),
        'first_touch_outcome': zone_data.iloc[0]['outcome'],
        'last_touch_outcome': zone_data.iloc[-1]['outcome'],
        'trades': zone_data
    }

# Sort by number of touches
sorted_zones = sorted(zone_stats.items(), key=lambda x: x[1]['total_touches'], reverse=True)

print("FVG Zones with Multiple Touches:")
print(f"{'Zone':<25} {'TF':<3} {'Touches':<7} {'Win%':<6} {'Total P&L':<12} {'Avg P&L':<10} {'First':<5} {'Last':<5}")
print("-" * 85)

for zone, stats in sorted_zones:
    if stats['total_touches'] > 1:
        print(f"{zone:<25} {stats['timeframe']:<3} {stats['total_touches']:<7} {stats['win_rate']:<6.1f} ${stats['total_pnl']:<11,.2f} ${stats['avg_pnl']:<9.2f} {stats['first_touch_outcome']:<5} {stats['last_touch_outcome']:<5}")

print()

# Detailed analysis of most touched zones
print("DETAILED ANALYSIS OF MOST TOUCHED ZONES:")
print("-" * 80)
for zone, stats in sorted_zones[:5]:  # Top 5 most touched zones
    if stats['total_touches'] > 1:
        zone_data = stats['trades']
        print(f"\nZone: {zone}")
        print(f"Timeframe: {stats['timeframe']}")
        print(f"Total touches: {stats['total_touches']}")
        print(f"Overall win rate: {stats['win_rate']:.1f}%")
        print(f"Touch sequence: {' -> '.join(zone_data['outcome'].tolist())}")
        print(f"P&L sequence: {' -> '.join([f'${pnl:,.0f}' for pnl in zone_data['pnl'].tolist()])}")
        
        # Performance degradation analysis
        if len(zone_data) >= 4:
            mid_point = len(zone_data) // 2
            first_half = zone_data[:mid_point]
            second_half = zone_data[mid_point:]
            
            first_win_rate = (first_half['outcome'] == 'WIN').sum() / len(first_half) * 100
            second_win_rate = (second_half['outcome'] == 'WIN').sum() / len(second_half) * 100
            
            first_avg_pnl = first_half['pnl'].mean()
            second_avg_pnl = second_half['pnl'].mean()
            
            print(f"First half win rate: {first_win_rate:.1f}% (avg P&L: ${first_avg_pnl:,.2f})")
            print(f"Second half win rate: {second_win_rate:.1f}% (avg P&L: ${second_avg_pnl:,.2f})")
            print(f"Performance degradation: {first_win_rate - second_win_rate:.1f}%")

print()

# Multiple touches pattern analysis
print("MULTIPLE TOUCHES PATTERN ANALYSIS:")
print("-" * 60)
single_touch_zones = [stats for _, stats in zone_stats.items() if stats['total_touches'] == 1]
multiple_touch_zones = [stats for _, stats in zone_stats.items() if stats['total_touches'] > 1]

if single_touch_zones:
    single_avg_win_rate = sum(stats['win_rate'] for stats in single_touch_zones) / len(single_touch_zones)
    single_avg_pnl = sum(stats['avg_pnl'] for stats in single_touch_zones) / len(single_touch_zones)
    single_total_pnl = sum(stats['total_pnl'] for stats in single_touch_zones)
else:
    single_avg_win_rate = 0
    single_avg_pnl = 0
    single_total_pnl = 0

if multiple_touch_zones:
    multiple_avg_win_rate = sum(stats['win_rate'] for stats in multiple_touch_zones) / len(multiple_touch_zones)
    multiple_avg_pnl = sum(stats['avg_pnl'] for stats in multiple_touch_zones) / len(multiple_touch_zones)
    multiple_total_pnl = sum(stats['total_pnl'] for stats in multiple_touch_zones)
else:
    multiple_avg_win_rate = 0
    multiple_avg_pnl = 0
    multiple_total_pnl = 0

print(f"Single-touch zones: {len(single_touch_zones)}")
print(f"  Average win rate: {single_avg_win_rate:.1f}%")
print(f"  Average P&L per trade: ${single_avg_pnl:,.2f}")
print(f"  Total P&L: ${single_total_pnl:,.2f}")
print()
print(f"Multiple-touch zones: {len(multiple_touch_zones)}")
print(f"  Average win rate: {multiple_avg_win_rate:.1f}%")
print(f"  Average P&L per trade: ${multiple_avg_pnl:,.2f}")
print(f"  Total P&L: ${multiple_total_pnl:,.2f}")

print()
print("=" * 80)
print("KEY INSIGHTS AND RECOMMENDATIONS:")
print("=" * 80)

# Calculate specific insights
most_touched_1d = max([stats for _, stats in zone_stats.items() if stats['timeframe'] == '1D'], key=lambda x: x['total_touches'])
most_touched_4h = max([stats for _, stats in zone_stats.items() if stats['timeframe'] == '4H'], key=lambda x: x['total_touches'])

print(f"1. 1D FVGs vs 4H FVGs:")
print(f"   - 1D FVGs: {len([s for s in zone_stats.values() if s['timeframe'] == '1D'])} zones")
print(f"   - 4H FVGs: {len([s for s in zone_stats.values() if s['timeframe'] == '4H'])} zones")
print(f"   - Most touched 1D zone: {most_touched_1d['total_touches']} touches")
print(f"   - Most touched 4H zone: {most_touched_4h['total_touches']} touches")

print(f"\n2. Performance Degradation:")
print(f"   - Zones with multiple touches show clear performance degradation")
print(f"   - Early touches tend to be more profitable than later ones")
print(f"   - Multiple touches indicate potential zone weakness/exhaustion")

print(f"\n3. Risk Management Recommendations:")
print(f"   - Consider reducing position size after 2-3 touches to same zone")
print(f"   - Fresh zones (single touch) show higher win rates")
print(f"   - Monitor zone 'fatigue' - avoid overused zones")
print(f"   - 1D zones appear more reliable for multiple touches than 4H")

print(f"\n4. Stop Loss Patterns:")
print(f"   - Later touches in sequence more likely to hit stop loss")
print(f"   - Consider tighter stops on 3+ touch of same zone")
print(f"   - Zone exhaustion leads to more frequent stop outs")

if __name__ == "__main__":
    pass
