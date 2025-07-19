"""
FastAPI Application.

RESTful API for controlling and monitoring the algorithmic trading system.
Provides endpoints for strategy management, live trading control, and system monitoring.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core import (
    BacktestRunner,
    BaseStrategy,
    DataAdapterFactory,
    ExecutionMode,
    FixedRiskPositionSizer,
    FVGStrategy,
    LiveTradingConfig,
    LiveTradingEngine,
    Order,
    PaperBrokerAdapter,
    Position,
    RiskLimits,
    RiskManager,
    Signal,
    SignalDirection,
    SignalType,
    TimeFrame,
    create_fvg_strategy_config,
    strategy_registry,
)


# Pydantic models for API requests/responses
class SignalResponse(BaseModel):
    """Signal API response model."""

    timestamp: datetime
    symbol: str
    direction: str
    signal_type: str
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float
    strength: float
    strategy_name: str

    @classmethod
    def from_signal(cls, signal: Signal) -> "SignalResponse":
        """Create SignalResponse from Signal."""
        return cls(
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            direction=signal.direction.value,
            signal_type=signal.signal_type.value,
            entry_price=float(signal.entry_price),
            stop_loss=float(signal.stop_loss) if signal.stop_loss else None,
            take_profit=(float(signal.take_profit) if signal.take_profit else None),
            confidence=signal.confidence,
            strength=signal.strength,
            strategy_name=signal.strategy_name,
        )


class PositionResponse(BaseModel):
    """Position API response model."""

    symbol: str
    direction: str
    entry_price: float
    quantity: float
    entry_time: datetime
    current_price: Optional[float] = None
    unrealized_pnl: float
    strategy_name: str

    @classmethod
    def from_position(cls, position: Position) -> "PositionResponse":
        """Create PositionResponse from Position."""
        return cls(
            symbol=position.symbol,
            direction=position.direction.value,
            entry_price=float(position.entry_price),
            quantity=float(position.quantity),
            entry_time=position.entry_time,
            current_price=(
                float(position.current_price) if position.current_price else None
            ),
            unrealized_pnl=float(position.unrealized_pnl),
            strategy_name=position.strategy_name,
        )


class OrderResponse(BaseModel):
    """Order API response model."""

    order_id: str
    symbol: str
    direction: str
    quantity: float
    price: Optional[float] = None
    order_type: str
    status: str
    created_at: datetime
    filled_at: Optional[datetime] = None
    filled_price: Optional[float] = None
    strategy_name: str

    @classmethod
    def from_order(cls, order: Order) -> "OrderResponse":
        """Create OrderResponse from Order."""
        return cls(
            order_id=order.order_id,
            symbol=order.symbol,
            direction=order.direction.value,
            quantity=float(order.quantity),
            price=float(order.price) if order.price else None,
            order_type=order.order_type,
            status=order.status.value,
            created_at=order.created_at,
            filled_at=order.filled_at,
            filled_price=(float(order.filled_price) if order.filled_price else None),
            strategy_name=order.strategy_name,
        )


class StrategyConfigRequest(BaseModel):
    """Strategy configuration request model."""

    name: str
    symbol: str
    timeframes: list[str]
    risk_per_trade: float = 0.02
    confidence_threshold: float = 0.85
    parameters: dict[str, Any] = Field(default_factory=dict)


class BacktestRequest(BaseModel):
    """Backtest request model."""

    strategy_name: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000
    strategy_config: Optional[StrategyConfigRequest] = None


class LiveTradingRequest(BaseModel):
    """Live trading request model."""

    mode: str = "paper"  # paper, live, sandbox
    auto_trading: bool = True
    max_orders_per_minute: int = 10
    max_daily_trades: int = 50
    emergency_stop_loss: float = 0.05


# Global system state
class SystemState:
    """Global system state."""

    def __init__(self) -> None:
        """Initialize system state."""
        self.live_engine: Optional[LiveTradingEngine] = None
        self.risk_manager: Optional[RiskManager] = None
        self.active_strategies: dict[str, BaseStrategy] = {}
        self.websocket_connections: list[WebSocket] = []
        self.is_live_trading = False
        self.system_start_time = datetime.now()


# Global state instance
system_state = SystemState()


# WebSocket connection manager
class ConnectionManager:
    """WebSocket connection manager."""

    def __init__(self) -> None:
        """Initialize connection manager."""
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Connect a WebSocket."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Disconnect a WebSocket."""
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send a personal message to a WebSocket."""
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all WebSockets."""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as exc:
                print(f"Error broadcasting to WebSocket: {exc}")


# Global connection manager
connection_manager = ConnectionManager()


# Lifespan manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Lifespan manager for FastAPI app."""
    # Startup
    print("🚀 Starting Algorithmic Trading API...")

    # Initialize risk manager
    risk_limits = RiskLimits()
    position_sizer = FixedRiskPositionSizer(risk_per_trade=0.02)
    system_state.risk_manager = RiskManager(
        risk_limits=risk_limits,
        position_sizer=position_sizer,
        initial_capital=Decimal("100000"),
    )

    print("✅ API initialized successfully")

    yield

    # Shutdown
    print("🛑 Shutting down Algorithmic Trading API...")
    if system_state.live_engine and system_state.is_live_trading:
        await system_state.live_engine.stop()
    print("✅ API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Algorithmic Trading System API",
    description=(
        "RESTful API for controlling and monitoring the algorithmic trading system"
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "uptime": datetime.now() - system_state.system_start_time,
        "live_trading": system_state.is_live_trading,
    }


# Strategy management endpoints
@app.get("/strategies", response_model=list[str])
async def get_available_strategies() -> list[str]:
    """Get list of available strategies."""
    return strategy_registry.list_strategies()


@app.post("/strategies/{strategy_name}/activate")
async def activate_strategy(
    strategy_name: str, config: StrategyConfigRequest
) -> dict[str, Any]:
    """Activate a strategy."""
    try:
        # Get strategy class
        strategy_names = strategy_registry.list_strategies()
        if strategy_name not in strategy_names:
            raise HTTPException(status_code=404, detail="Strategy not found")

        # Create strategy configuration
        from core.data.models import StrategyConfig

        timeframes = [TimeFrame(tf) for tf in config.timeframes]
        strategy_config = StrategyConfig(
            name=config.name,
            symbol=config.symbol,
            timeframes=timeframes,
            risk_per_trade=config.risk_per_trade,
            confidence_threshold=config.confidence_threshold,
            parameters=config.parameters,
        )

        # Create and initialize strategy using registry
        strategy = strategy_registry.create_strategy(strategy_name, strategy_config)
        strategy.initialize()

        # Store active strategy
        system_state.active_strategies[config.name] = strategy

        return {
            "message": f"Strategy {strategy_name} activated successfully",
            "strategy_id": config.name,
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/strategies/{strategy_id}")
async def deactivate_strategy(strategy_id: str) -> dict[str, str]:
    """Deactivate a strategy."""
    if strategy_id not in system_state.active_strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")

    del system_state.active_strategies[strategy_id]
    return {"message": f"Strategy {strategy_id} deactivated successfully"}


@app.get("/strategies/active", response_model=list[str])
async def get_active_strategies() -> list[str]:
    """Get list of active strategies."""
    return list(system_state.active_strategies.keys())


# Live trading endpoints
@app.post("/live-trading/start")
async def start_live_trading(config: LiveTradingRequest) -> dict[str, str]:
    """Start live trading."""
    try:
        if system_state.is_live_trading:
            raise HTTPException(status_code=400, detail="Live trading already running")

        # Create broker adapter
        broker = PaperBrokerAdapter(initial_balance=Decimal("100000"))

        # Create live trading config
        live_config = LiveTradingConfig(
            mode=ExecutionMode(config.mode),
            enable_auto_trading=config.auto_trading,
            max_orders_per_minute=config.max_orders_per_minute,
            max_daily_trades=config.max_daily_trades,
            emergency_stop_loss=config.emergency_stop_loss,
        )

        # Ensure risk manager is initialized
        if system_state.risk_manager is None:
            raise HTTPException(status_code=500, detail="Risk manager not initialized")

        # Create live trading engine
        system_state.live_engine = LiveTradingEngine(
            broker_adapter=broker,
            risk_manager=system_state.risk_manager,
            config=live_config,
        )

        # Add event handlers
        system_state.live_engine.add_order_handler(_on_order_event)
        system_state.live_engine.add_position_handler(_on_position_event)
        system_state.live_engine.add_error_handler(_on_error_event)

        # Start engine
        success = await system_state.live_engine.start()
        if success:
            system_state.is_live_trading = True
            await _broadcast_event("live_trading_started", {"mode": config.mode})
            return {"message": "Live trading started successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to start live trading")

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/live-trading/stop")
async def stop_live_trading() -> dict[str, str]:
    """Stop live trading."""
    try:
        if not system_state.is_live_trading or not system_state.live_engine:
            raise HTTPException(status_code=400, detail="Live trading not running")

        await system_state.live_engine.stop()
        system_state.is_live_trading = False
        await _broadcast_event("live_trading_stopped", {})

        return {"message": "Live trading stopped successfully"}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/live-trading/status")
async def get_live_trading_status() -> dict[str, Any]:
    """Get live trading status."""
    if not system_state.live_engine:
        return {"running": False}

    return system_state.live_engine.get_status()


@app.post("/live-trading/emergency-stop")
async def emergency_stop(reason: str = "Manual emergency stop") -> dict[str, Any]:
    """Emergency stop live trading."""
    try:
        if not system_state.is_live_trading or not system_state.live_engine:
            raise HTTPException(status_code=400, detail="Live trading not running")

        await system_state.live_engine.emergency_stop(reason)
        await _broadcast_event("emergency_stop", {"reason": reason})

        return {"message": "Emergency stop executed"}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# Signal endpoints
@app.post("/signals/manual")
async def send_manual_signal(signal_data: dict[str, Any]) -> dict[str, Any]:
    """Send a manual trading signal."""
    try:
        if not system_state.is_live_trading or not system_state.live_engine:
            raise HTTPException(status_code=400, detail="Live trading not running")

        # Create signal
        signal = Signal(
            timestamp=datetime.now(),
            symbol=signal_data["symbol"],
            direction=SignalDirection(signal_data["direction"]),
            signal_type=SignalType(signal_data["signal_type"]),
            entry_price=Decimal(str(signal_data["entry_price"])),
            stop_loss=(
                Decimal(str(signal_data["stop_loss"]))
                if signal_data.get("stop_loss")
                else None
            ),
            take_profit=(
                Decimal(str(signal_data["take_profit"]))
                if signal_data.get("take_profit")
                else None
            ),
            confidence=signal_data.get("confidence", 0.8),
            strength=signal_data.get("strength", 0.8),
            strategy_name="manual",
        )

        # Process signal
        order = await system_state.live_engine.process_signal(signal)

        if order:
            return {
                "message": "Signal processed successfully",
                "order_id": order.order_id,
            }
        else:
            return {"message": "Signal rejected by risk management"}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# Position endpoints
@app.get("/positions", response_model=list[PositionResponse])
async def get_positions() -> list[PositionResponse]:
    """Get current positions."""
    try:
        if not system_state.live_engine:
            return []

        positions = await system_state.live_engine.broker.get_positions()
        return [PositionResponse.from_position(pos) for pos in positions]

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# Order endpoints
@app.get("/orders", response_model=list[OrderResponse])
async def get_orders() -> list[OrderResponse]:
    """Get recent orders."""
    try:
        if not system_state.live_engine:
            return []

        orders = (
            list(system_state.live_engine.pending_orders.values())
            + system_state.live_engine.state.filled_orders[
                -50:
            ]  # Last 50 filled orders
        )
        return [OrderResponse.from_order(order) for order in orders]

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# Backtesting endpoints
@app.post("/backtest/run")
async def run_backtest(request: BacktestRequest) -> dict[str, Any]:
    """Run a backtest."""
    try:
        # Create data adapter
        adapter = DataAdapterFactory.create_adapter("backtrader")

        # Create backtest runner
        runner = BacktestRunner(adapter)

        # Create strategy
        if request.strategy_name == "FVGStrategy":
            config = create_fvg_strategy_config(
                symbol=request.symbol,
                timeframes=[TimeFrame(request.timeframe)],
            )
            strategy = FVGStrategy(config)
        else:
            raise HTTPException(status_code=400, detail="Strategy not supported")

        # Run backtest
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            runner.run_single_backtest,
            strategy,
            request.symbol,
            TimeFrame(request.timeframe),
            request.start_date,
            request.end_date,
            Decimal(str(request.initial_capital)),
        )

        return {
            "strategy_name": result.strategy_name,
            "symbol": result.symbol,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "initial_capital": float(result.initial_capital),
            "final_capital": float(result.final_capital),
            "total_return": result.calculate_return_percentage(),
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "win_rate": result.calculate_win_rate(),
            "max_drawdown": float(result.max_drawdown),
            "signals_count": len(result.signals),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# Portfolio endpoints
@app.get("/portfolio/summary")
async def get_portfolio_summary() -> dict[str, Any]:
    """Get portfolio summary."""
    try:
        if not system_state.risk_manager:
            return {"error": "Risk manager not initialized"}

        return system_state.risk_manager.get_portfolio_summary()

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Websocket endpoint for real-time updates."""
    await connection_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now - can be extended for bidirectional communication
            await connection_manager.send_personal_message(f"Echo: {data}", websocket)
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)


# Event handlers
def _on_order_event(order: Order) -> None:
    """Handle order events."""
    asyncio.create_task(
        _broadcast_event(
            "order_update",
            {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "status": order.status.value,
                "filled_price": (
                    float(order.filled_price) if order.filled_price else None
                ),
            },
        )
    )


def _on_position_event(position: Position) -> None:
    """Handle position events."""
    asyncio.create_task(
        _broadcast_event(
            "position_update",
            {
                "symbol": position.symbol,
                "direction": position.direction.value,
                "quantity": float(position.quantity),
                "unrealized_pnl": float(position.unrealized_pnl),
            },
        )
    )


def _on_error_event(error: str) -> None:
    """Handle error events."""
    asyncio.create_task(_broadcast_event("error", {"message": error}))


async def _broadcast_event(event_type: str, data: dict[str, Any]) -> None:
    """Broadcast event to all WebSocket connections."""
    message = json.dumps(
        {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }
    )
    await connection_manager.broadcast(message)


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "timestamp": datetime.now().isoformat()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "timestamp": datetime.now().isoformat()},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
