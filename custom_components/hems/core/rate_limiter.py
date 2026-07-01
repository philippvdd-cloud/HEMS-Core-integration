"""Rate limiter."""

from __future__ import annotations


class RateLimiter:
    """Limit the maximum rate of change between consecutive values."""

    def __init__(self, max_delta: float = 100.0) -> None:
        """Initialize limiter."""

        self._max_delta = max_delta
        self._last: float | None = None

    def apply(self, value: float) -> float:
        """Limit output.

        The very first value is passed through unchanged so the
        sensor reflects reality immediately after startup instead of
        ramping up from zero.
        """

        if self._last is None:
            self._last = value
            return value

        delta = value - self._last

        if delta > self._max_delta:
            value = self._last + self._max_delta

        elif delta < -self._max_delta:
            value = self._last - self._max_delta

        self._last = value

        return value

    def reset(self) -> None:
        """Reset limiter."""

        self._last = None
