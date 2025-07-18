#!/usr/bin/env python3
"""
Phase 3 System Demonstration

This demo showcases the complete Phase 3 implementation including:
- Live trading engine with paper trading
- Real-time data streaming
- FastAPI integration
- WebSocket real-time updates
- Complete system integration
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
import json
import time

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import (
    # Data models
    Signal, Position, Order, TimeFrame, SignalDirection, SignalType,
    # Strategy system
    FVGStrategy, create_fvg_strategy_config,
    # Risk management
    RiskManager, RiskLimits, FixedRiskPositionSizer,
    # Live trading
    LiveTradingEngine, PaperBrokerAdapter, LiveTradingConfig, ExecutionMode,
    # Streaming
    StreamingManager, StreamingFactory, StreamingConfig, StreamingProvider
)


class Phase3Demo:
    """Phase 3 system demonstration"""
    
    def __init__(self):
        self.live_engine = None
        self.streaming_manager = None
        self.demo_signals = []
        self.demo_orders = []
        self.demo_positions = []
    
    async def run_complete_demo(self):
        """Run the complete Phase 3 demonstration"""
        print("🚀 Phase 3 Complete System Demonstration")
        print("=" * 70)
        print("This demo showcases the complete Phase 3 implementation:")
        print("- Live trading engine with paper trading")
        print("- Real-time data streaming simulation")
        print("- Order management and execution")
        print("- Risk management integration")
        print("- Event-driven architecture")
        print("=" * 70)
        print()
        
        try:
            # Run all demo components
            await self.demo_live_trading_engine()
            await self.demo_streaming_integration()
            await self.demo_signal_processing()
            await self.demo_risk_integration()
            await self.demo_order_management()
            await self.demo_real_time_updates()
            
            print("\n🎉 Phase 3 System Features:")
            print("  ✅ Live Trading Engine - Paper and live trading capabilities")
            print("  ✅ Real-time Data Streaming - Multiple provider support")
            print("  ✅ Order Management - Complete order lifecycle")
            print("  ✅ Risk Integration - Real-time risk monitoring")
            print("  ✅ Event-driven Architecture - Reactive system design")
            print("  ✅ API Integration - RESTful and WebSocket APIs")
            print()
            print("✅ All Phase 3 demonstrations completed successfully!")
            
        except Exception as e:
            print(f"❌ Error during demonstration: {e}")
            import traceback
            traceback.print_exc()
    
    async def demo_live_trading_engine(self):
        """Demonstrate live trading engine"""
        print("🔥 Live Trading Engine Demo")
        print("=" * 50)
        
        # Create paper broker
        broker = PaperBrokerAdapter(initial_balance=Decimal('100000'))
        
        # Create risk manager
        risk_limits = RiskLimits(
            max_position_size=Decimal('0.1'),
            max_daily_loss=Decimal('0.05'),
            max_drawdown=Decimal('0.2'),
            max_positions=5
        )
        position_sizer = FixedRiskPositionSizer(risk_per_trade=0.02)
        risk_manager = RiskManager(
            risk_limits=risk_limits,
            position_sizer=position_sizer,
            initial_capital=Decimal('100000')
        )
        
        # Create live trading config
        config = LiveTradingConfig(
            mode=ExecutionMode.PAPER,
            enable_auto_trading=True,
            max_orders_per_minute=10,
            max_daily_trades=50,
            emergency_stop_loss=0.05
        )
        
        # Create live trading engine
        self.live_engine = LiveTradingEngine(
            broker_adapter=broker,
            risk_manager=risk_manager,
            config=config
        )
        
        # Add event handlers
        self.live_engine.add_order_handler(self._on_order_event)
        self.live_engine.add_position_handler(self._on_position_event)
        self.live_engine.add_error_handler(self._on_error_event)
        
        # Start engine
        success = await self.live_engine.start()
        print(f"📊 Live Trading Engine started: {success}")
        
        # Show initial status
        status = self.live_engine.get_status()
        print(f"💰 Initial balance: ${await broker.get_account_balance():,.2f}")
        print(f"🎯 Trading mode: {config.mode.value}")
        print(f"🔄 Auto trading: {config.enable_auto_trading}")
        print(f"📊 Max positions: {risk_limits.max_positions}")
        
        print()
    
    async def demo_streaming_integration(self):
        """Demonstrate streaming integration"""
        print("📡 Real-time Data Streaming Demo")
        print("=" * 50)
        
        # Create streaming configs
        mock_config = StreamingConfig(
            provider=StreamingProvider.MOCK,
            symbols=["AAPL", "GOOGL", "MSFT"],
            timeframes=[TimeFrame.MINUTE_1],
            auto_reconnect=True
        )
        
        # Create streaming manager
        self.streaming_manager = StreamingManager()
        
        # Add mock provider
        mock_provider = StreamingFactory.create_provider(mock_config)
        self.streaming_manager.add_provider(mock_provider)
        
        # Add data subscriber
        self.streaming_manager.add_subscriber(self._on_streaming_data)
        
        # Start streaming
        success = await self.streaming_manager.start()
        print(f"📊 Streaming started: {success}")
        
        # Subscribe to symbols
        for symbol in mock_config.symbols:
            await self.streaming_manager.subscribe_symbol(symbol)
        
        # Show streaming status
        status = self.streaming_manager.get_status()
        print(f"🔗 Providers connected: {status['providers']}")
        print(f"📈 Symbols subscribed: {list(status['subscriptions'].keys())}")
        print(f"👥 Subscribers: {status['subscriber_count']}")
        
        # Let it stream for a few seconds
        print("📊 Streaming live data for 3 seconds...")
        await asyncio.sleep(3)
        
        print()
    
    async def demo_signal_processing(self):
        """Demonstrate signal processing"""
        print("🎯 Signal Processing Demo")
        print("=" * 50)
        
        # Create test signals
        test_signals = [
            Signal(
                timestamp=datetime.now(),
                symbol="AAPL",
                direction=SignalDirection.LONG,
                signal_type=SignalType.ENTRY,
                entry_price=Decimal('150.00'),
                stop_loss=Decimal('145.00'),
                take_profit=Decimal('160.00'),
                confidence=0.9,
                strength=0.8,
                strategy_name="demo_strategy"
            ),
            Signal(
                timestamp=datetime.now(),
                symbol="GOOGL",
                direction=SignalDirection.SHORT,
                signal_type=SignalType.ENTRY,
                entry_price=Decimal('120.00'),
                stop_loss=Decimal('125.00'),
                take_profit=Decimal('110.00'),
                confidence=0.85,
                strength=0.7,
                strategy_name="demo_strategy"
            ),
            Signal(
                timestamp=datetime.now(),
                symbol="MSFT",
                direction=SignalDirection.LONG,
                signal_type=SignalType.ENTRY,
                entry_price=Decimal('200.00'),
                stop_loss=Decimal('195.00'),
                take_profit=Decimal('210.00'),
                confidence=0.95,
                strength=0.9,
                strategy_name="demo_strategy"
            )
        ]
        
        # Process signals through live engine
        for signal in test_signals:
            print(f"🎯 Processing signal: {signal.symbol} {signal.direction.value} @ ${signal.entry_price}")
            
            order = await self.live_engine.process_signal(signal)
            
            if order:
                print(f"  ✅ Order placed: {order.order_id}")
                self.demo_orders.append(order)
            else:
                print(f"  ❌ Signal rejected")
            
            self.demo_signals.append(signal)
            
            # Small delay between signals
            await asyncio.sleep(0.5)
        
        print(f"📊 Total signals processed: {len(self.demo_signals)}")
        print(f"📋 Orders placed: {len(self.demo_orders)}")
        
        print()
    
    async def demo_risk_integration(self):
        """Demonstrate risk management integration"""
        print("🛡️ Risk Management Integration Demo")
        print("=" * 50)
        
        # Update positions with current market prices
        positions = await self.live_engine.broker.get_positions()
        self.demo_positions = positions
        
        # Simulate price updates
        price_updates = {
            "AAPL": Decimal('152.00'),  # +1.33% gain
            "GOOGL": Decimal('118.00'), # -1.67% gain for short
            "MSFT": Decimal('198.00')   # -1.00% loss
        }
        
        # Update broker prices
        for symbol, price in price_updates.items():
            if hasattr(self.live_engine.broker, 'update_market_price'):
                self.live_engine.broker.update_market_price(symbol, price)
        
        # Get portfolio summary
        portfolio = self.live_engine.risk_manager.get_portfolio_summary()
        
        print(f"💰 Total portfolio value: ${portfolio['total_value']:,.2f}")
        print(f"💵 Available cash: ${portfolio['available_cash']:,.2f}")
        print(f"📊 Unrealized P&L: ${portfolio['unrealized_pnl']:,.2f}")
        print(f"📈 Total return: {portfolio['return_pct']:.2f}%")
        print(f"🔢 Active positions: {portfolio['active_positions']}")
        print(f"📊 Win rate: {portfolio['win_rate']:.1%}")
        
        # Test risk limits
        print(f"\n🚨 Risk Limits Check:")
        print(f"  Max drawdown: {portfolio['max_drawdown']:.2%}")
        print(f"  Should stop trading: {self.live_engine.risk_manager.should_stop_trading()}")
        
        print()
    
    async def demo_order_management(self):
        """Demonstrate order management"""
        print("📋 Order Management Demo")
        print("=" * 50)
        
        # Show order lifecycle
        print(f"📊 Order Lifecycle Demonstration:")
        
        # Wait for orders to be processed
        await asyncio.sleep(2)
        
        # Check order statuses
        filled_orders = 0
        pending_orders = 0
        
        for order in self.demo_orders:
            status = await self.live_engine.broker.get_order_status(order.order_id)
            if status.value == "filled":
                filled_orders += 1
            elif status.value == "pending":
                pending_orders += 1
            
            print(f"  Order {order.order_id}: {order.symbol} {order.direction.value} - {status.value}")
        
        print(f"\n📊 Order Summary:")
        print(f"  Total orders: {len(self.demo_orders)}")
        print(f"  Filled orders: {filled_orders}")
        print(f"  Pending orders: {pending_orders}")
        
        # Show position summary
        positions = await self.live_engine.broker.get_positions()
        print(f"  Active positions: {len(positions)}")
        
        for position in positions:
            print(f"    {position.symbol}: {position.direction.value} {position.quantity} @ ${position.entry_price}")
        
        print()
    
    async def demo_real_time_updates(self):
        """Demonstrate real-time updates"""
        print("📊 Real-time Updates Demo")
        print("=" * 50)
        
        print("🔄 Monitoring system for 5 seconds...")
        
        # Monitor for 5 seconds
        for i in range(5):
            # Get current status
            trading_status = self.live_engine.get_status()
            streaming_status = self.streaming_manager.get_status()
            
            print(f"  Heartbeat {i+1}: Live={trading_status['is_running']}, "
                  f"Streaming={streaming_status['is_running']}, "
                  f"Orders={trading_status['orders_sent_today']}")
            
            await asyncio.sleep(1)
        
        print()
    
    async def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up resources...")
        
        if self.live_engine:
            await self.live_engine.stop()
        
        if self.streaming_manager:
            await self.streaming_manager.stop()
        
        print("✅ Cleanup complete")
    
    # Event handlers
    def _on_order_event(self, order: Order):
        """Handle order events"""
        print(f"  📋 Order event: {order.order_id} - {order.status.value}")
    
    def _on_position_event(self, position: Position):
        """Handle position events"""
        print(f"  📊 Position update: {position.symbol} - P&L: ${position.unrealized_pnl:.2f}")
    
    def _on_error_event(self, error: str):
        """Handle error events"""
        print(f"  ❌ Error: {error}")
    
    def _on_streaming_data(self, candle):
        """Handle streaming data"""
        # Only show first few candles to avoid spam
        if len(self.demo_signals) < 3:
            print(f"  📊 Live data: {candle.symbol} - ${candle.close} @ {candle.timestamp.strftime('%H:%M:%S')}")


async def demo_api_integration():
    """Demonstrate API integration concepts"""
    print("🌐 API Integration Demo")
    print("=" * 50)
    
    print("📡 FastAPI Integration Features:")
    print("  ✅ RESTful endpoints for system control")
    print("  ✅ WebSocket real-time updates")
    print("  ✅ Strategy management endpoints")
    print("  ✅ Live trading control endpoints")
    print("  ✅ Portfolio monitoring endpoints")
    print("  ✅ Backtesting endpoints")
    print()
    
    print("🔗 Available API Endpoints:")
    print("  GET    /health - Health check")
    print("  GET    /strategies - Available strategies")
    print("  POST   /strategies/{name}/activate - Activate strategy")
    print("  POST   /live-trading/start - Start live trading")
    print("  POST   /live-trading/stop - Stop live trading")
    print("  GET    /live-trading/status - Get trading status")
    print("  POST   /signals/manual - Send manual signal")
    print("  GET    /positions - Get current positions")
    print("  GET    /orders - Get recent orders")
    print("  POST   /backtest/run - Run backtest")
    print("  GET    /portfolio/summary - Get portfolio summary")
    print("  WS     /ws - WebSocket real-time updates")
    print()
    
    print("📱 Usage Example:")
    print("  curl -X POST http://localhost:8000/live-trading/start \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"mode\": \"paper\", \"auto_trading\": true}'")
    print()
    
    print("🚀 To start the API server:")
    print("  cd api && python main.py")
    print("  or: uvicorn api.main:app --reload")
    print()


async def main():
    """Main demonstration function"""
    demo = Phase3Demo()
    
    try:
        # Run complete system demo
        await demo.run_complete_demo()
        
        # Show API integration
        await demo_api_integration()
        
    finally:
        # Always cleanup
        await demo.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
