"""
Enhanced killzone management system for algorithmic trading.

This module provides flexible time window filtering for algorithmic trading strategies,
allowing multiple active windows (Asia, London, NY sessions) with configurable
exclusion periods to avoid low-volume periods.
"""

from datetime import datetime, time, timezone


def convert_ny_time_to_utc(ny_hour: int, ny_minute: int = 0) -> tuple[int, int]:
    """
    Convert NY time to UTC, accounting for EST/EDT.

    Note: This is a simplified conversion. For production use, consider
    proper timezone handling with pytz or zoneinfo for DST transitions.

    Args:
        ny_hour: Hour in NY time (0-23)
        ny_minute: Minute in NY time (0-59)

    Returns:
        Tuple of (utc_hour, utc_minute)
    """
    # EST is UTC-5, EDT is UTC-4
    # For simplicity, using EST (UTC-5) - adjust as needed
    utc_hour = (ny_hour + 5) % 24
    return utc_hour, ny_minute


class TradingSession:
    """Represents a trading session with start and end times."""

    def __init__(
        self,
        name: str,
        start_hour: int,
        start_minute: int,
        end_hour: int,
        end_minute: int,
    ):
        self.name = name
        self.start_time = time(start_hour, start_minute)
        self.end_time = time(end_hour, end_minute)

    def is_active(self, current_time: time) -> bool:
        """Check if the given time falls within this session."""
        if self.start_time <= self.end_time:
            # Session doesn't cross midnight
            return self.start_time <= current_time <= self.end_time
        else:
            # Session crosses midnight
            return current_time >= self.start_time or current_time <= self.end_time


class KillzoneManager:
    """
    Advanced killzone manager supporting multiple sessions and exclusion periods.

    Supports:
    - Multiple trading sessions (Asia, London, NY)
    - Configurable exclusion periods (low volume times)
    - Flexible session selection
    """

    def __init__(self) -> None:
        # Convert NY times to UTC for the sessions
        # Asia: 20:00-02:00 NY = 01:00-07:00 UTC (EST)
        asia_start_utc = convert_ny_time_to_utc(20, 0)
        asia_end_utc = convert_ny_time_to_utc(2, 0)

        # London: 02:00-11:00 NY = 07:00-16:00 UTC (EST)
        london_start_utc = convert_ny_time_to_utc(2, 0)
        london_end_utc = convert_ny_time_to_utc(11, 0)

        # NY: 09:30-16:00 NY = 14:30-21:00 UTC (EST)
        ny_start_utc = convert_ny_time_to_utc(9, 30)
        ny_end_utc = convert_ny_time_to_utc(16, 0)

        # Define trading sessions
        self.sessions = {
            "asia": TradingSession(
                "Asia",
                asia_start_utc[0],
                asia_start_utc[1],
                asia_end_utc[0],
                asia_end_utc[1],
            ),
            "london": TradingSession(
                "London",
                london_start_utc[0],
                london_start_utc[1],
                london_end_utc[0],
                london_end_utc[1],
            ),
            "ny": TradingSession(
                "NY", ny_start_utc[0], ny_start_utc[1], ny_end_utc[0], ny_end_utc[1]
            ),
        }

        # Exclusion periods (low volume times in UTC)
        # Avoid: 00:00-02:00 UTC (NY 19:00-21:00 EST = after NY close)
        # Avoid: 05:00-07:00 UTC (NY 00:00-02:00 EST = NY midnight/early morning)
        self.exclusion_periods = [
            TradingSession("Low_Volume_1", 0, 0, 2, 0),  # 00:00-02:00 UTC
            TradingSession("Low_Volume_2", 5, 0, 7, 0),  # 05:00-07:00 UTC
        ]

    def is_killzone_active(
        self,
        current_time: datetime,
        active_sessions: list[str] | None = None,
        exclude_low_volume: bool = True,
    ) -> bool:
        """
        Check if current time is within any active killzone.

        Args:
            current_time: Current datetime (should be UTC)
            active_sessions: List of session names to check ['asia', 'london', 'ny']
                           If None, checks all sessions
            exclude_low_volume: Whether to exclude low-volume periods

        Returns:
            True if time is within an active killzone, False otherwise
        """
        if active_sessions is None:
            active_sessions = list(self.sessions.keys())

        current_time_only = current_time.time()

        # Check exclusion periods first
        if exclude_low_volume:
            for exclusion in self.exclusion_periods:
                if exclusion.is_active(current_time_only):
                    return False

        # Check if in any active session
        for session_name in active_sessions:
            if session_name in self.sessions:
                session = self.sessions[session_name]
                if session.is_active(current_time_only):
                    return True

        return False

    def get_active_session(self, current_time: datetime) -> str | None:
        """
        Get the name of the currently active session.

        Args:
            current_time: Current datetime (should be UTC)

        Returns:
            Name of active session or None if no session is active
        """
        current_time_only = current_time.time()

        for name, session in self.sessions.items():
            if session.is_active(current_time_only):
                return name

        return None

    def get_session_info(self) -> dict:
        """Get information about all configured sessions."""
        info = {}
        for name, session in self.sessions.items():
            info[name] = {
                "start": session.start_time.strftime("%H:%M"),
                "end": session.end_time.strftime("%H:%M"),
                "name": session.name,
            }
        return info


# Enhanced killzone guard function that can replace the existing one
def enhanced_killzone_ok(
    bar_time: datetime,
    sessions: list[str] | None = None,
    exclude_low_volume: bool = True,
    killzone_manager: KillzoneManager | None = None,
) -> bool:
    """
    Enhanced killzone check supporting multiple sessions and exclusions.

    Args:
        bar_time: Current bar timestamp (should be UTC)
        sessions: List of session names to allow ['asia', 'london', 'ny']
                 If None, allows all sessions
        exclude_low_volume: Whether to exclude low-volume periods
        killzone_manager: Optional custom killzone manager instance

    Returns:
        True if time is within allowed killzone, False otherwise
    """
    if killzone_manager is None:
        killzone_manager = KillzoneManager()

    return killzone_manager.is_killzone_active(
        bar_time, active_sessions=sessions, exclude_low_volume=exclude_low_volume
    )


# Configuration helper functions
def create_session_config(sessions: list[str], exclude_low_volume: bool = True) -> dict:
    """
    Create a configuration dictionary for killzone settings.

    Args:
        sessions: List of session names ['asia', 'london', 'ny']
        exclude_low_volume: Whether to exclude low-volume periods

    Returns:
        Configuration dictionary
    """
    return {"sessions": sessions, "exclude_low_volume": exclude_low_volume}


# Pre-defined common configurations
ASIA_ONLY = create_session_config(["asia"])
LONDON_ONLY = create_session_config(["london"])
NY_ONLY = create_session_config(["ny"])
LONDON_NY = create_session_config(["london", "ny"])
ALL_SESSIONS = create_session_config(["asia", "london", "ny"])
ALL_SESSIONS_NO_EXCLUSION = create_session_config(
    ["asia", "london", "ny"], exclude_low_volume=False
)
