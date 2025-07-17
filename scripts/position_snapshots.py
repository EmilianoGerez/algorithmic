#!/usr/bin/env python3
"""
Position Snapshots Generator
Creates visual charts showing actual entry positions from the strategy
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pytz
from typing import List, Dict, Optional, Tuple

from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from scripts.working_clean_backtesting import WorkingCleanBacktester

class PositionSnapshotGenerator:
    def __init__(self):
        self.repo = AlpacaCryptoRepository()
        self.redis = get_redis_connection()
        self.db = SessionLocal()
        self.service = SignalDetectionService(self.repo, self.redis, self.db)
        self.backtester = WorkingCleanBacktester()
        
    def generate_snapshots(self, num_snapshots: int = 5) -> None:
        """Generate visual snapshots of actual entry positions"""
        
        print(f"📸 POSITION SNAPSHOTS GENERATOR")
        print(f"================================================================================")
        print(f"🎯 Generating {num_snapshots} position snapshots with visual context")
        print(f"📊 Showing: Entry, Stop Loss, Take Profit, FVG levels, and EMA")
        print()
        
        # Run the backtester to get actual signals
        print("🔄 Running backtesting to generate signals...")
        signals = self.backtester.backtest_working(
            symbol="BTC/USD",
            ltf="5T",
            start="2025-05-01T00:00:00Z",
            end="2025-07-13T23:59:59Z"
        )
        
        if not signals or 'signals' not in signals:
            print("❌ No signals generated from backtesting")
            return
            
        signal_list = signals['signals']
        if not signal_list:
            print("❌ No signals found in backtesting results")
            return
            
        print(f"✅ Generated {len(signal_list)} signals from backtesting")
        
        # Select diverse signals for snapshots
        selected_signals = self._select_diverse_signals(signal_list, num_snapshots)
        
        # Generate charts for each selected signal
        for i, signal in enumerate(selected_signals, 1):
            print(f"📈 Processing snapshot {i}/{len(selected_signals)}...")
            self._create_position_chart(signal, i)
            
        print(f"\n✅ Generated {len(selected_signals)} position snapshots")
        print(f"📁 Charts saved as PNG files in current directory")
        
    def _select_diverse_signals(self, signals: List[Dict], num_samples: int) -> List[Dict]:
        """Select diverse signals for snapshots"""
        
        if len(signals) <= num_samples:
            return signals
            
        # Try to get a mix of bullish and bearish signals
        bullish_signals = [s for s in signals if s.get('direction') == 'BULLISH']
        bearish_signals = [s for s in signals if s.get('direction') == 'BEARISH']
        
        selected = []
        
        # Get half bullish, half bearish if possible
        target_bullish = num_samples // 2
        target_bearish = num_samples - target_bullish
        
        # Add bullish signals
        for signal in bullish_signals:
            if len([s for s in selected if s.get('direction') == 'BULLISH']) < target_bullish:
                selected.append(signal)
                
        # Add bearish signals
        for signal in bearish_signals:
            if len([s for s in selected if s.get('direction') == 'BEARISH']) < target_bearish:
                selected.append(signal)
                
        # Fill remaining slots with any signals
        for signal in signals:
            if len(selected) >= num_samples:
                break
            if signal not in selected:
                selected.append(signal)
                
        return selected[:num_samples]
        
    def _create_position_chart(self, signal: Dict, chart_num: int) -> None:
        """Create a detailed chart for a single position"""
        
        try:
            # Extract signal data
            timestamp_str = signal.get('timestamp')
            direction = signal.get('direction', 'UNKNOWN')
            entry_price = signal.get('entry_price', 0)
            stop_loss = signal.get('stop_loss', 0)
            take_profit = signal.get('take_profit', 0)
            fvg_data = signal.get('fvg', {})
            
            if not timestamp_str or not entry_price:
                print(f"   ⚠️  Skipping signal {chart_num} - missing data")
                return
                
            # Parse timestamp
            if isinstance(timestamp_str, str):
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = timestamp_str
                
            # Get candle data around the entry (wider window for context)
            start_time = timestamp - timedelta(hours=3)
            end_time = timestamp + timedelta(hours=2)
            
            # Get 5-minute candles for the chart
            candles = self._get_candles_for_chart(start_time, end_time)
            
            if not candles:
                print(f"   ⚠️  No candle data available for signal {chart_num}")
                return
                
            # Create the chart
            fig, ax = plt.subplots(figsize=(16, 10))
            
            # Plot candlesticks
            self._plot_candlesticks(ax, candles)
            
            # Plot EMA 20
            self._plot_ema(ax, candles)
            
            # Plot FVG zone
            if fvg_data:
                self._plot_fvg_zone(ax, fvg_data, start_time, end_time)
                
            # Plot entry, stop loss, and take profit
            self._plot_entry_levels(ax, timestamp, entry_price, stop_loss, take_profit, direction)
            
            # Customize chart
            self._customize_chart(ax, signal, chart_num)
            
            # Save chart
            filename = f"position_snapshot_{chart_num}_{direction.lower()}_{timestamp.strftime('%Y%m%d_%H%M')}.png"
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"   ✅ Saved: {filename}")
            
        except Exception as e:
            print(f"   ❌ Error creating chart {chart_num}: {str(e)}")
            
    def _get_candles_for_chart(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get candles for the chart from Alpaca API"""
        
        try:
            # Format times for API
            start_str = start_time.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
            end_str = end_time.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
            
            # Get data from signal detection service
            result = self.service.detect_signals(
                symbol="BTC/USD",
                signal_type="pivot",  # Just get candles
                timeframe="5T",
                start=start_str,
                end=end_str
            )
            
            return result.get('candles', [])
            
        except Exception as e:
            print(f"   ❌ Error fetching candles: {str(e)}")
            return []
            
    def _plot_candlesticks(self, ax, candles: List[Dict]) -> None:
        """Plot candlestick chart"""
        
        if not candles:
            return
            
        # Convert candle data
        data = []
        for candle in candles:
            timestamp = datetime.fromisoformat(candle['timestamp'].replace('Z', '+00:00'))
            data.append({
                'timestamp': timestamp,
                'open': candle['open'],
                'high': candle['high'],
                'low': candle['low'],
                'close': candle['close']
            })
            
        # Sort by timestamp
        data.sort(key=lambda x: x['timestamp'])
        
        # Create candlesticks
        for candle in data:
            ts = candle['timestamp']
            o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
            
            color = 'green' if c >= o else 'red'
            alpha = 0.7
            
            # High-low line
            ax.plot([ts, ts], [l, h], color='black', linewidth=1, alpha=0.8)
            
            # Body
            body_height = abs(c - o)
            body_bottom = min(o, c)
            
            # Calculate width for rectangle (5 minutes = 5/1440 of a day)
            width = timedelta(minutes=2)
            
            rect = Rectangle((ts - width/2, body_bottom), width, body_height,
                           facecolor=color, alpha=alpha, edgecolor='black', linewidth=0.5)
            ax.add_patch(rect)
            
    def _plot_ema(self, ax, candles: List[Dict]) -> None:
        """Plot EMA 20"""
        
        if len(candles) < 20:
            return
            
        # Convert and sort candles
        data = []
        for candle in candles:
            timestamp = datetime.fromisoformat(candle['timestamp'].replace('Z', '+00:00'))
            data.append({
                'timestamp': timestamp,
                'close': candle['close']
            })
            
        data.sort(key=lambda x: x['timestamp'])
        
        # Calculate EMA 20
        closes = [d['close'] for d in data]
        timestamps = [d['timestamp'] for d in data]
        
        ema_values = []
        multiplier = 2 / (20 + 1)
        ema = closes[0]  # Start with first close
        
        for close in closes:
            ema = (close * multiplier) + (ema * (1 - multiplier))
            ema_values.append(ema)
            
        ax.plot(timestamps, ema_values, color='blue', linewidth=2, label='EMA 20', alpha=0.8)
        
    def _plot_fvg_zone(self, ax, fvg_data: Dict, start_time: datetime, end_time: datetime) -> None:
        """Plot FVG zone"""
        
        fvg_low = fvg_data.get('low', 0)
        fvg_high = fvg_data.get('high', 0)
        fvg_timeframe = fvg_data.get('timeframe', '4H')
        
        if not fvg_low or not fvg_high:
            return
            
        # Create FVG rectangle
        width = end_time - start_time
        rect = Rectangle((start_time, fvg_low), width, fvg_high - fvg_low,
                        facecolor='yellow', alpha=0.2, edgecolor='orange', linewidth=2)
        ax.add_patch(rect)
        
        # Add FVG labels
        ax.text(start_time + timedelta(minutes=5), fvg_high + 50, 
               f'FVG ({fvg_timeframe})', fontsize=10, color='orange', weight='bold')
        ax.text(start_time + timedelta(minutes=5), fvg_low - 100, 
               f'${fvg_low:.2f} - ${fvg_high:.2f}', fontsize=9, color='orange')
        
    def _plot_entry_levels(self, ax, timestamp: datetime, entry_price: float, 
                          stop_loss: float, take_profit: float, direction: str) -> None:
        """Plot entry, stop loss, and take profit levels"""
        
        # Entry point
        ax.scatter([timestamp], [entry_price], color='purple', s=100, zorder=5, 
                  marker='o', label=f'{direction} Entry')
        
        # Entry price line
        ax.axhline(y=entry_price, color='purple', linestyle='-', linewidth=2, alpha=0.7)
        ax.text(timestamp + timedelta(minutes=5), entry_price + 50, 
               f'Entry: ${entry_price:.2f}', fontsize=10, color='purple', weight='bold')
        
        # Stop loss line
        ax.axhline(y=stop_loss, color='red', linestyle='--', linewidth=2, alpha=0.7)
        ax.text(timestamp + timedelta(minutes=5), stop_loss + 50, 
               f'Stop Loss: ${stop_loss:.2f}', fontsize=10, color='red', weight='bold')
        
        # Take profit line
        ax.axhline(y=take_profit, color='green', linestyle='--', linewidth=2, alpha=0.7)
        ax.text(timestamp + timedelta(minutes=5), take_profit + 50, 
               f'Take Profit: ${take_profit:.2f}', fontsize=10, color='green', weight='bold')
        
        # Risk/reward zones
        x_range = [timestamp - timedelta(minutes=30), timestamp + timedelta(hours=1)]
        if direction == 'BULLISH':
            # Risk zone (red)
            ax.fill_between(x_range, stop_loss, entry_price, alpha=0.1, color='red', label='Risk Zone')
            # Reward zone (green)
            ax.fill_between(x_range, entry_price, take_profit, alpha=0.1, color='green', label='Reward Zone')
        else:
            # Risk zone (red)
            ax.fill_between(x_range, entry_price, stop_loss, alpha=0.1, color='red', label='Risk Zone')
            # Reward zone (green)
            ax.fill_between(x_range, take_profit, entry_price, alpha=0.1, color='green', label='Reward Zone')
        
    def _customize_chart(self, ax, signal: Dict, chart_num: int) -> None:
        """Customize chart appearance and add information"""
        
        # Extract signal info
        timestamp_str = signal.get('timestamp')
        direction = signal.get('direction', 'UNKNOWN')
        entry_price = signal.get('entry_price', 0)
        stop_loss = signal.get('stop_loss', 0)
        take_profit = signal.get('take_profit', 0)
        fvg_data = signal.get('fvg', {})
        
        # Parse timestamp
        if isinstance(timestamp_str, str):
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            timestamp = timestamp_str
        
        # Calculate risk/reward
        if direction == 'BULLISH':
            risk = entry_price - stop_loss
            reward = take_profit - entry_price
        else:
            risk = stop_loss - entry_price
            reward = entry_price - take_profit
            
        rr_ratio = reward / risk if risk > 0 else 0
        
        # Set title with comprehensive info
        ny_time = timestamp.astimezone(pytz.timezone('America/New_York'))
        title = f"Position Snapshot #{chart_num} - {direction} Entry\n"
        title += f"BTC/USD 5min - {ny_time.strftime('%Y-%m-%d %H:%M')} NY Time\n"
        title += f"Entry: ${entry_price:.2f} | Risk: ${risk:.2f} | Reward: ${reward:.2f} | R:R = 1:{rr_ratio:.2f}"
        
        ax.set_title(title, fontsize=12, weight='bold', pad=20)
        
        # Format axes
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        # Add grid
        ax.grid(True, alpha=0.3)
        
        # Add legend
        ax.legend(loc='upper left', fontsize=10)
        
        # Labels
        ax.set_xlabel('Time (NY)', fontsize=10)
        ax.set_ylabel('Price ($)', fontsize=10)
        
        # Add strategy info box
        strategy_info = f"Strategy: 2-Candle EMA Confirmation\n"
        strategy_info += f"FVG: {fvg_data.get('timeframe', 'N/A')} | "
        strategy_info += f"Method: {'2_candles_above_ema20' if direction == 'BULLISH' else '2_candles_below_ema20'}\n"
        strategy_info += f"Trading Hours: NY 20:00-00:00, 02:00-04:00, 08:00-13:00"
        
        ax.text(0.02, 0.98, strategy_info, transform=ax.transAxes, fontsize=9, 
               verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

def main():
    """Main function to generate position snapshots"""
    
    generator = PositionSnapshotGenerator()
    generator.generate_snapshots(num_snapshots=5)

if __name__ == "__main__":
    main()
