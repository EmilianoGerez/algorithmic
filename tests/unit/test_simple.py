"""
Simple test to debug pytest collection issues.
"""

import pytest


def test_simple():
    """Simple test."""
    assert True


class TestSimple:
    """Simple test class."""

    def test_method(self):
        """Simple test method."""
        assert True


if __name__ == "__main__":
    pytest.main([__file__])
