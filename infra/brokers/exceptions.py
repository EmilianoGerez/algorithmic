"""
Broker-specific exceptions and error handling.

This module defines custom exceptions used throughout the broker system
for proper error handling and debugging.
"""

__all__ = ["BrokerError"]


class BrokerError(Exception):
    """Base exception for broker-related errors.

    Raised when broker operations fail due to validation errors,
    connectivity issues, or other broker-specific problems.
    """

    def __init__(self, message: str, order_id: str | None = None) -> None:
        """Initialize broker error.

        Args:
            message: Error description.
            order_id: Associated order ID if applicable.
        """
        super().__init__(message)
        self.message = message
        self.order_id = order_id

    def __str__(self) -> str:
        """String representation of the error."""
        if self.order_id:
            return f"BrokerError (order {self.order_id}): {self.message}"
        return f"BrokerError: {self.message}"
