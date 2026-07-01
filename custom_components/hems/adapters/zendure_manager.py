"""Zendure Manager adapter for HEMS.

Instead of HEMS individually commanding each Zendure battery (with
its own AC-mode switching, relay-cooldown, and SoC bookkeeping), this
adapter delegates fleet distribution to Zendure's own built-in
"Manager" device, exposed by the Zendure Home Assistant integration
whenever more than one Zendure device is configured (and even for a
single device).

The Zendure Manager already implements, across all configured
devices: SoC-weighted distribution, fuse-group limits, kickstart
thresholds for sluggish start-up behaviour, and atomic mode+limit
commands (avoiding the race condition our earlier per-device approach
had). HEMS only decides WHEN and HOW MUCH power to move (via
PowerGoal) - the Manager decides HOW to split that across the
individual battery units.

This still talks to Zendure exclusively through regular Home
Assistant services and entity states, so HEMS Core remains unaware
of Zendure-specific concepts.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from ..models.device_state import DeviceCapabilities, DeviceState

_LOGGER = logging.getLogger(__name__)

_MANUAL_POWER_SUFFIX = "_manual_power"
_OPERATION_SUFFIX = "_operation"

# Hints used to find the "manual" operation mode among the select
# entity's own `options`, rather than hardcoding an exact string -
# same self-adapting approach as the (now superseded) per-device
# AC-mode resolution, and for the same reason: raw option values are
# not guaranteed to match a guessed translation.
_MANUAL_MODE_HINTS = ("manual",)


def _read_number_attr(state: Any, attr: str, default: float) -> float:
    """Safely read a numeric attribute from a number entity's state."""

    if state is None:
        return default

    try:
        return float(state.attributes.get(attr, default))
    except (TypeError, ValueError):
        return default


def _read_float_state(hass: HomeAssistant, entity_id: str) -> float:
    """Safely read a sensor's numeric state, defaulting to 0.0."""

    state = hass.states.get(entity_id)

    if state is None or state.state in ("unknown", "unavailable"):
        return 0.0

    try:
        return float(state.state)
    except ValueError:
        return 0.0


def resolve_manual_mode_option(options: list[str]) -> str | None:
    """Find the "manual" operation mode from a select entity's options.

    Pure logic, decoupled from ``hass`` so it can be unit tested
    without Home Assistant installed.
    """

    for option in options:
        lowered = option.lower()

        if any(hint in lowered for hint in _MANUAL_MODE_HINTS):
            return option

    return None


def extract_manager_prefix(
    number_entity_ids: list[str],
    select_entity_ids: list[str],
) -> str | None:
    """Find the Zendure Manager's entity prefix, if present.

    Pure logic, decoupled from ``hass`` so it can be unit tested
    without Home Assistant installed. Looks for a matching pair of
    ``number.<prefix>_manual_power`` / ``select.<prefix>_operation``
    entities, which the Zendure Manager exposes exactly once per
    Zendure config entry (covering all of that entry's devices).
    """

    number_ids = set(number_entity_ids)
    select_ids = set(select_entity_ids)

    for entity_id in number_ids:
        if not entity_id.startswith("number."):
            continue

        object_id = entity_id.split(".", 1)[1]

        if not object_id.endswith(_MANUAL_POWER_SUFFIX):
            continue

        prefix = object_id[: -len(_MANUAL_POWER_SUFFIX)]

        if f"select.{prefix}{_OPERATION_SUFFIX}" in select_ids:
            return prefix

    return None


def discover_zendure_manager_prefix(hass: HomeAssistant) -> str | None:
    """Find the Zendure Manager's entity prefix currently in Home Assistant."""

    return extract_manager_prefix(
        list(hass.states.async_entity_ids("number")),
        list(hass.states.async_entity_ids("select")),
    )


class ZendureManagerAdapter:
    """Adapter for the Zendure Manager (controls the whole battery fleet).

    Represents ALL of a user's Zendure devices as a single HEMS
    device, since the Manager itself already handles distributing
    power across them.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        entity_prefix: str,
    ) -> None:
        """Initialize the adapter.

        ``entity_prefix`` is the Zendure Manager's entity prefix,
        e.g. "zendure_manager" for entities like
        ``number.zendure_manager_manual_power``.
        """

        self.hass = hass
        self.device_id = device_id
        self._prefix = entity_prefix

        self._manual_power_entity = (
            f"number.{entity_prefix}{_MANUAL_POWER_SUFFIX}"
        )
        self._operation_entity = f"select.{entity_prefix}{_OPERATION_SUFFIX}"

        # Aggregate sensors the Manager already computes across all
        # of its devices. `power` is a REAL measurement (summed from
        # the individual devices' own sensors) - crucially different
        # from reading back manual_power's own state, which would
        # just echo our last command back at us.
        self._power_entity = f"sensor.{entity_prefix}_power"
        self._global_soc_entity = f"sensor.{entity_prefix}_global_soc"

    async def async_get_state(self) -> DeviceState:
        """Return the current aggregate state of the Zendure fleet."""

        manual_power_state = self.hass.states.get(self._manual_power_entity)

        if manual_power_state is None:
            return DeviceState(
                device_id=self.device_id,
                available=False,
                current_power=0.0,
                soc=None,
                capabilities=DeviceCapabilities(
                    can_charge=False,
                    can_discharge=False,
                    min_power=0.0,
                    max_charge_power=0.0,
                    max_discharge_power=0.0,
                ),
            )

        # The Manager's manual_power range (e.g. -12000..12000) is a
        # software UI bound, not the fleet's real physical capacity -
        # the Manager internally clamps to whatever the actual
        # devices can do, so HEMS can safely request up to this bound
        # without needing to track individual device limits itself.
        max_discharge = _read_number_attr(manual_power_state, "max", 0.0)
        max_charge = abs(_read_number_attr(manual_power_state, "min", 0.0))
        step = _read_number_attr(manual_power_state, "step", 1.0)

        # Zendure's own sign convention is inverted from HEMS's:
        # positive = discharge, non-positive = charge. This applies
        # equally to `power` and `manual_power` (both accumulate the
        # same way in the Manager's source).
        #
        # IMPORTANT: current_power is read from the `power` sensor -
        # a real measurement aggregated from the individual devices'
        # own sensors - NOT from manual_power's own reported state.
        # Reading back our own last command here would make the
        # Scheduler's headroom math treat "what we asked for last
        # time" as "what's already flowing", causing it to keep
        # adding more on top every cycle (a runaway ratcheting bug
        # found on a real installation: -1458W, -3217W, -4976W...).
        current_power = -_read_float_state(self.hass, self._power_entity)

        soc = _read_float_state(self.hass, self._global_soc_entity)

        return DeviceState(
            device_id=self.device_id,
            available=True,
            current_power=current_power,
            soc=soc if soc > 0.0 else None,
            capabilities=DeviceCapabilities(
                can_charge=max_charge > 0,
                can_discharge=max_discharge > 0,
                min_power=max(step, 1.0),
                max_charge_power=max_charge,
                max_discharge_power=max_discharge,
            ),
        )

    async def async_set_power(self, power: float) -> None:
        """Move the fleet towards the given signed target power.

        Positive power -> charge (HEMS convention). Negative power ->
        discharge. Converted to Zendure's inverted sign convention
        before writing.
        """

        await self._async_ensure_manual_mode()

        zendure_value = -power

        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self._manual_power_entity, "value": zendure_value},
            blocking=True,
        )

    async def _async_ensure_manual_mode(self) -> None:
        """Make sure the Manager is in "manual" operation mode.

        Unlike the per-device AC-mode switch this replaces, this is
        not expected to change on every control cycle - it only
        switches the first time (or if something else changed it back
        externally), so no cooldown/throttling is needed here.
        """

        state = self.hass.states.get(self._operation_entity)

        if state is None:
            return

        options = list(state.attributes.get("options", []))
        target_option = resolve_manual_mode_option(options)

        if target_option is None:
            _LOGGER.warning(
                "Zendure manager '%s': could not find a 'manual' "
                "operation option among %s",
                self.device_id,
                options,
            )
            return

        if state.state == target_option:
            return

        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self._operation_entity, "option": target_option},
            blocking=True,
        )

        _LOGGER.info(
            "Zendure manager '%s': switched operation mode to '%s'",
            self.device_id,
            target_option,
        )
