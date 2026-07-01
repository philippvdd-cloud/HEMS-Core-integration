"""Turns a GridState into a signed power goal for the Scheduler."""

from __future__ import annotations

from .models.grid_state import GridDirection, GridState
from .models.power_goal import PowerGoal

# Default minimum grid power (in watts) before HEMS reacts. Prevents
# HEMS from constantly re-adjusting devices for noise that already
# survived the EnergyManager's own filters. Can be overridden per
# instance via the `deadband` constructor argument.
DEFAULT_REACTION_THRESHOLD: float = 50.0

# Default amount of PV surplus (in watts) HEMS is allowed to let flow
# into the grid before it starts charging batteries with the excess.
# 0.0 means "zero feed-in" (charge any surplus at all). Can be
# overridden per instance via the `export_allowance` constructor
# argument.
DEFAULT_EXPORT_ALLOWANCE: float = 0.0


class DecisionEngine:
    """HEMS's grid-following decision logic.

    Goal, in order of priority:

    1. Grid import (house consumption > PV) -> discharge batteries to
       cover exactly the deficit, so PV keeps covering the rest.
    2. No PV at all -> the above already covers this: 100% of
       consumption shows up as import, so batteries cover all of it.
    3. PV surplus (PV > house consumption) -> let up to
       `export_allowance` watts flow into the grid; charge batteries
       with anything beyond that, so excess feed-in is avoided
       without needing to hit exactly zero.
    4. Grid balanced (within the export allowance, or genuinely idle)
       -> explicitly release any device that is still actively
       charging/discharging back to 0, so a previous command doesn't
       linger forever once it's no longer needed.

    More advanced strategies (electricity price awareness, PV
    forecasts, scheduling deferrable loads, ...) are planned for
    later versions and will build on top of this same PowerGoal
    contract.
    """

    def __init__(
        self,
        deadband: float = DEFAULT_REACTION_THRESHOLD,
        export_allowance: float = DEFAULT_EXPORT_ALLOWANCE,
    ) -> None:
        """Initialize the decision engine.

        ``deadband`` is the minimum power change (in watts) before
        HEMS reacts at all - avoids reacting to noise right at a
        threshold crossing.

        ``export_allowance`` is how much PV surplus (in watts) HEMS
        is allowed to let flow into the grid before charging the
        excess into batteries. 0.0 means zero feed-in.
        """

        self._deadband = deadband
        self._export_allowance = export_allowance

    def decide(self, grid_state: GridState) -> PowerGoal:
        """Return the current power goal.

        Always returns a goal - a balanced grid (or export within the
        allowance) produces an explicit "release to zero" goal rather
        than no goal at all, so devices don't keep an old command
        active indefinitely.
        """

        if grid_state.direction == GridDirection.IDLE:
            return PowerGoal(power=0.0, reason="grid_balanced")

        if grid_state.direction == GridDirection.EXPORT:
            chargeable = grid_state.export_power - self._export_allowance

            if chargeable < self._deadband:
                return PowerGoal(power=0.0, reason="within_export_allowance")

            return PowerGoal(power=chargeable, reason="avoid_excess_feed_in")

        # GridDirection.IMPORT
        if grid_state.import_power < self._deadband:
            return PowerGoal(power=0.0, reason="grid_balanced")

        return PowerGoal(
            power=-grid_state.import_power,
            reason="avoid_grid_import",
        )
