"""Periodic device-control loop for HEMS.

Wires DecisionEngine -> Scheduler -> DeviceManager together and runs
them on their own interval (DEFAULT_CONTROL_INTERVAL), independent of
the fast grid-power polling in HemsCoordinator. Sensors stay
responsive at a 2s cadence without commanding real hardware (and
cycling relays) that often.

HEMS controls each Zendure device directly (not via Zendure's own
Manager) - by explicit choice, so HEMS owns the full decision:
equal distribution across all enabled devices, each device's SoC
respected individually (see adapters/zendure.py), and the export
allowance handled centrally in the DecisionEngine.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .adapters.zendure import ZendureAdapter, discover_zendure_device_prefixes
from .const import (
    CONF_ENABLED_ZENDURE_DEVICES,
    DEFAULT_CONTROL_INTERVAL,
    DEFAULT_EXPORT_ALLOWANCE,
)
from .coordinator import HemsCoordinator
from .decision_engine import DecisionEngine
from .device_manager import DeviceManager
from .scheduler import DevicePriority, Scheduler

_LOGGER = logging.getLogger(__name__)


class HemsController:
    """Owns the device-orchestration side of HEMS.

    Only devices the user explicitly enabled via the options flow are
    registered here - auto-discovery alone never grants control.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HemsCoordinator,
    ) -> None:
        """Initialize the controller (does not yet start the loop)."""

        self.hass = hass
        self.coordinator = coordinator

        self.device_manager = DeviceManager()
        self.decision_engine = DecisionEngine(
            export_allowance=DEFAULT_EXPORT_ALLOWANCE
        )
        self.scheduler = Scheduler()

        self._priorities: list[DevicePriority] = []
        self._unsub_timer: Callable[[], None] | None = None

    async def async_setup(self) -> None:
        """Register enabled devices and start the control loop."""

        enabled = set(
            self.coordinator.config_entry.options.get(
                CONF_ENABLED_ZENDURE_DEVICES, []
            )
        )

        if enabled:
            discovered = discover_zendure_device_prefixes(self.hass)

            for prefix in discovered:
                if prefix not in enabled:
                    continue

                adapter = ZendureAdapter(
                    hass=self.hass,
                    device_id=prefix,
                    entity_prefix=prefix,
                )
                self.device_manager.register(adapter)

                # `priority` is unused by the default EQUAL
                # distribution strategy (which is what spreads output
                # evenly across all three devices, as requested) -
                # kept at 0 so the field still means something if the
                # PRIORITY strategy is ever selected later.
                self._priorities.append(
                    DevicePriority(device_id=prefix, priority=0)
                )

        if not self._priorities:
            _LOGGER.debug(
                "HEMS: no devices enabled for control - "
                "monitoring only, control loop will idle"
            )
        else:
            _LOGGER.info(
                "HEMS: controlling %d device(s): %s",
                len(self._priorities),
                ", ".join(entry.device_id for entry in self._priorities),
            )

        self._unsub_timer = async_track_time_interval(
            self.hass,
            self._async_control_tick,
            DEFAULT_CONTROL_INTERVAL,
        )

    def async_unload(self) -> None:
        """Stop the control loop."""

        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _async_control_tick(self, _now: object) -> None:
        """Timer callback - schedule the async control step."""

        self.hass.async_create_task(
            self._async_control_step(),
            name="hems_control_step",
        )

    async def _async_control_step(self) -> None:
        """Run one DecisionEngine -> Scheduler -> DeviceManager cycle."""

        if not self._priorities:
            return

        grid_state = self.coordinator.data

        if grid_state is None:
            return

        goal = self.decision_engine.decide(grid_state)

        states = await self.device_manager.async_get_states()

        requests = self.scheduler.schedule(
            goal=goal,
            states=states,
            priorities=self._priorities,
        )

        if requests:
            _LOGGER.debug(
                "HEMS control step: applying %d power request(s) (%s)",
                len(requests),
                goal.reason,
            )

        await self.device_manager.async_apply(requests)
