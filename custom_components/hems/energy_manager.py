"""Energy management logic for HEMS."""

from __future__ import annotations

from collections import deque

from .core.deadband_filter import DeadbandFilter
from .core.hysteresis_filter import HysteresisFilter
from .core.median_filter import MedianFilter
from .core.moving_average import MovingAverageFilter
from .core.power_history import PowerHistory
from .core.rate_limiter import RateLimiter
from .models import GridDirection, GridState, PowerData

# Number of processed samples kept to derive the short-term trend.
# At the default 2s poll interval this covers roughly 30 seconds.
TREND_WINDOW: int = 15

# Minimum trend magnitude (in watts) below which the grid is
# considered "stable".
STABILITY_THRESHOLD: float = 50.0


class EnergyManager:
    """Main HEMS signal processing pipeline.

    Turns a raw :class:`PowerData` measurement into a filtered,
    contextualized :class:`GridState`.
    """

    def __init__(self) -> None:
        """Initialize the energy manager."""

        self._history = PowerHistory(max_samples=300)
        self._trend_window: deque[float] = deque(maxlen=TREND_WINDOW)

        self._median = MedianFilter(window_size=5)
        self._average = MovingAverageFilter(window_size=5)

        self._deadband = DeadbandFilter(deadband=20.0)
        self._hysteresis = HysteresisFilter(hysteresis=30.0)
        self._rate_limiter = RateLimiter(max_delta=100.0)

    def update(
        self,
        data: PowerData,
    ) -> GridState:
        """Process a new EcoTracker measurement and return the grid state."""

        #
        # Store original measurement
        #

        self._history.add(data.power)

        value = data.power

        #
        # Median
        #

        self._median.add(value)
        value = self._median.value

        #
        # Moving average
        #

        self._average.add(value)
        value = self._average.value

        #
        # Deadband
        #

        value = self._deadband.apply(value)

        #
        # Hysteresis
        #

        value = self._hysteresis.apply(value)

        #
        # Rate limiter
        #

        value = self._rate_limiter.apply(value)

        self._trend_window.append(value)

        return self._build_grid_state(value)

    def _build_grid_state(self, value: float) -> GridState:
        """Build a GridState from the latest filtered value."""

        if value > 0:
            direction = GridDirection.IMPORT
        elif value < 0:
            direction = GridDirection.EXPORT
        else:
            direction = GridDirection.IDLE

        trend = self._calculate_trend()

        return GridState(
            power=value,
            import_power=value if value > 0 else 0.0,
            export_power=-value if value < 0 else 0.0,
            direction=direction,
            stable=abs(trend) < STABILITY_THRESHOLD,
            trend=trend,
            samples=self._history.samples,
        )

    def _calculate_trend(self) -> float:
        """Return the short-term power trend in watts.

        Positive values mean power is rising (more import / less
        export), negative values mean it is falling.
        """

        if len(self._trend_window) < 2:
            return 0.0

        return self._trend_window[-1] - self._trend_window[0]

    def reset(self) -> None:
        """Reset all filters."""

        self._history.clear()
        self._trend_window.clear()

        self._median.clear()
        self._average.clear()

        self._hysteresis.reset()
        self._rate_limiter.reset()

    @property
    def latest_power(self) -> float:
        """Return latest raw power."""

        return self._history.latest

    @property
    def average_power(self) -> float:
        """Return average raw power."""

        return self._history.average

    @property
    def minimum_power(self) -> float:
        """Return minimum raw power."""

        return self._history.minimum

    @property
    def maximum_power(self) -> float:
        """Return maximum raw power."""

        return self._history.maximum

    @property
    def sample_count(self) -> int:
        """Return number of samples."""

        return self._history.samples
