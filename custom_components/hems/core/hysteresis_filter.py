"""Hysteresis filter."""

from __future__ import annotations


class HysteresisFilter:
    """Prevent frequent switching."""

    def __init__(self, hysteresis: float = 30.0) -> None:
        """Initialize the filter."""

        self._hysteresis = hysteresis
        self._last_output = 0.0

    def apply(self, value: float) -> float:
        """Apply hysteresis."""

        if abs(value - self._last_output) < self._hysteresis:
            return self._last_output

        self._last_output = value
        return value

    def reset(self) -> None:
        """Reset filter state."""

        self._last_output = 0.0
