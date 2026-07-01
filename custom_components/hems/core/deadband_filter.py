"""Deadband filter."""

from __future__ import annotations


class DeadbandFilter:
    """Suppress small value changes around zero."""

    def __init__(self, deadband: float = 20.0) -> None:
        """Initialize the filter."""

        self._deadband = deadband

    def apply(self, value: float) -> float:
        """Apply deadband."""

        if abs(value) <= self._deadband:
            return 0.0

        return value
