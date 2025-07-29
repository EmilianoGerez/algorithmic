"""
Simulation clock for deterministic time management during backtesting.

Provides unified time source that can be advanced programmatically during backtesting
or proxy to real wall-clock time during live trading.
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Protocol


class Clock(Protocol):
    """Clock interface for time management."""
    
    def now(self) -> datetime:
        """Get current time as timezone-aware datetime."""
        ...
    
    def now_ms(self) -> int:
        """Get current time as milliseconds since epoch."""
        ...


class WallClock:
    """Real wall-clock time implementation."""
    
    def now(self) -> datetime:
        """Get current wall-clock time."""
        return datetime.now(UTC)
    
    def now_ms(self) -> int:
        """Get current time as milliseconds since epoch."""
        return int(self.now().timestamp() * 1000)


class SimClock:
    """Simulation clock for deterministic backtesting."""
    
    def __init__(self, start_time: datetime | None = None):
        """
        Initialize simulation clock.
        
        Args:
            start_time: Starting simulation time (defaults to current time)
        """
        self._current_time = start_time or datetime.now(UTC)
    
    def now(self) -> datetime:
        """Get current simulation time."""
        return self._current_time
    
    def now_ms(self) -> int:
        """Get current time as milliseconds since epoch."""
        return int(self._current_time.timestamp() * 1000)
    
    def advance(self, new_time: datetime) -> None:
        """
        Advance simulation time.
        
        Args:
            new_time: New simulation time (must be >= current time)
        """
        if new_time < self._current_time:
            raise ValueError(
                f"Cannot move time backwards: {new_time} < {self._current_time}"
            )
        self._current_time = new_time
    
    def advance_ms(self, ms_delta: int) -> None:
        """
        Advance simulation time by milliseconds.
        
        Args:
            ms_delta: Milliseconds to advance
        """
        from datetime import timedelta
        new_time = self._current_time + timedelta(milliseconds=ms_delta)
        self.advance(new_time)


# Global clock instance - defaults to wall clock
_global_clock: Clock = WallClock()


def get_clock() -> Clock:
    """Get the global clock instance."""
    return _global_clock


def set_clock(clock: Clock) -> None:
    """Set the global clock instance."""
    global _global_clock
    _global_clock = clock


def use_simulation_clock(start_time: datetime | None = None) -> SimClock:
    """
    Switch to simulation clock for backtesting.
    
    Args:
        start_time: Starting simulation time
        
    Returns:
        The simulation clock instance
    """
    sim_clock = SimClock(start_time)
    set_clock(sim_clock)
    return sim_clock


def use_wall_clock() -> WallClock:
    """
    Switch to wall clock for live trading.
    
    Returns:
        The wall clock instance
    """
    wall_clock = WallClock()
    set_clock(wall_clock)
    return wall_clock
