"""Zendure adapter for HEMS.

Wraps a single Zendure battery (as exposed by the Zendure Home
Assistant integration) so HEMS Core can control it through the
manufacturer-independent DeviceAdapter interface.

This adapter never talks to Zendure's cloud or local API directly.
It only calls regular Home Assistant services (``number.set_value``,
``select.select_option``) and reads regular HA entity states, so it
works with any Zendure HA integration that follows the same
entity-id conventions - it does not depend on Zendure-internal
protocol details.

Hardware note
-------------
These Zendure devices (SolarFlow 800 Pro, Hyper 2000, ...) have a
single bidirectional AC port that is either in "output" mode
(delivering power to the home, governed by the ``*_output_limit``
number) or "input" mode (drawing power from AC to charge, governed by
the ``*_input_limit`` number) - never both at once. Switching between
the two flips a physical relay. The device itself tracks this via a
``*_switch_count`` sensor, which strongly suggests excessive switching
should be avoided. This adapter therefore only changes direction at
most once per :data:`MIN_MODE_SWITCH_INTERVAL` seconds.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant

from ..models.device_state import DeviceCapabilities, DeviceState

_LOGGER = logging.getLogger(__name__)

_OUTPUT_LIMIT_SUFFIX = "_output_limit"
_INPUT_LIMIT_SUFFIX = "_input_limit"
_ELECTRIC_LEVEL_SUFFIX = "_electric_level"
_PACK_INPUT_POWER_SUFFIX = "_pack_input_power"
_OUTPUT_PACK_POWER_SUFFIX = "_output_pack_power"
_AC_MODE_SUFFIX = "_ac_mode"

# Keywords used to find the right AC-mode option out of the select
# entity's own `options` attribute, instead of hardcoding an exact
# string. This is deliberately case-insensitive and matches both
# German ("Ausgang"/"Eingang") and English ("output"/"input")
# wording, so it keeps working across integration versions/languages
# without needing to know the exact label text in advance.
_OUTPUT_MODE_HINTS = ("ausgang", "output")
_INPUT_MODE_HINTS = ("eingang", "input")

# Minimum time between AC-mode direction switches, to protect the
# device's relay from excessive cycling.
MIN_MODE_SWITCH_INTERVAL: float = 300.0

# SoC (%) thresholds beyond which a battery must not be offered
# charge/discharge headroom, even if its number entity's `max`
# attribute still allows it - the device's own BMS will reject or
# silently ignore commands once these are reached.
SOC_FULL_THRESHOLD: float = 99.0
SOC_EMPTY_THRESHOLD: float = 1.0


def resolve_ac_mode_option(
    options: list[str],
    wants_input_mode: bool,
) -> str | None:
    """Find the matching AC-mode option from a select entity's options.

    Pure logic, decoupled from ``hass`` so it can be unit tested
    without Home Assistant installed. Returns None if no option
    matches (e.g. unexpected wording), so the caller can fail safely
    instead of sending a value the device will reject.
    """

    hints = _INPUT_MODE_HINTS if wants_input_mode else _OUTPUT_MODE_HINTS

    for option in options:
        lowered = option.lower()

        if any(hint in lowered for hint in hints):
            return option

    return None


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


def extract_device_prefixes(number_entity_ids: list[str]) -> list[str]:
    """Derive Zendure device entity prefixes from a list of entity ids.

    Pure logic, decoupled from ``hass`` so it can be unit tested
    without Home Assistant installed. Looks for matching pairs of
    ``number.<prefix>_output_limit`` / ``number.<prefix>_input_limit``
    entities, which every Zendure battery exposes.
    """

    ids = set(number_entity_ids)
    prefixes: set[str] = set()

    for entity_id in ids:
        if not entity_id.startswith("number."):
            continue

        object_id = entity_id.split(".", 1)[1]

        if object_id.endswith(_OUTPUT_LIMIT_SUFFIX):
            prefixes.add(object_id[: -len(_OUTPUT_LIMIT_SUFFIX)])

    return [
        prefix
        for prefix in sorted(prefixes)
        if f"number.{prefix}{_INPUT_LIMIT_SUFFIX}" in ids
    ]


def discover_zendure_device_prefixes(hass: HomeAssistant) -> list[str]:
    """Find all Zendure device entity prefixes currently in Home Assistant."""

    return extract_device_prefixes(
        list(hass.states.async_entity_ids("number"))
    )


class ZendureAdapter:
    """Adapter for a single Zendure battery device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        entity_prefix: str,
    ) -> None:
        """Initialize the adapter.

        ``entity_prefix`` is the shared prefix of all entities for
        this device, e.g. "solarflow_800_pro" for entities like
        ``number.solarflow_800_pro_output_limit``.
        """

        self.hass = hass
        self.device_id = device_id
        self._prefix = entity_prefix

        self._output_limit_entity = (
            f"number.{entity_prefix}{_OUTPUT_LIMIT_SUFFIX}"
        )
        self._input_limit_entity = (
            f"number.{entity_prefix}{_INPUT_LIMIT_SUFFIX}"
        )
        self._electric_level_entity = (
            f"sensor.{entity_prefix}{_ELECTRIC_LEVEL_SUFFIX}"
        )
        self._pack_input_power_entity = (
            f"sensor.{entity_prefix}{_PACK_INPUT_POWER_SUFFIX}"
        )
        self._output_pack_power_entity = (
            f"sensor.{entity_prefix}{_OUTPUT_PACK_POWER_SUFFIX}"
        )
        self._ac_mode_entity = f"select.{entity_prefix}{_AC_MODE_SUFFIX}"

        self._last_mode_switch: float | None = None

    async def async_get_state(self) -> DeviceState:
        """Return the current state of the Zendure battery."""

        output_limit_state = self.hass.states.get(self._output_limit_entity)
        input_limit_state = self.hass.states.get(self._input_limit_entity)

        if output_limit_state is None or input_limit_state is None:
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

        max_discharge = _read_number_attr(output_limit_state, "max", 0.0)
        max_charge = _read_number_attr(input_limit_state, "max", 0.0)
        step = min(
            _read_number_attr(output_limit_state, "step", 1.0),
            _read_number_attr(input_limit_state, "step", 1.0),
        )

        charge_power = _read_float_state(
            self.hass, self._pack_input_power_entity
        )
        discharge_power = _read_float_state(
            self.hass, self._output_pack_power_entity
        )
        current_power = charge_power - discharge_power

        soc_state = self.hass.states.get(self._electric_level_entity)
        soc = (
            _read_float_state(self.hass, self._electric_level_entity)
            if soc_state is not None
            else None
        )

        # A battery that is (near) full or (near) empty must not be
        # offered as having charge/discharge headroom, even though its
        # number entity's own `max` attribute is still non-zero -
        # otherwise HEMS keeps commanding a charge/discharge limit the
        # device's BMS silently ignores once the SoC boundary is hit.
        can_charge = max_charge > 0 and (
            soc is None or soc < SOC_FULL_THRESHOLD
        )
        can_discharge = max_discharge > 0 and (
            soc is None or soc > SOC_EMPTY_THRESHOLD
        )

        return DeviceState(
            device_id=self.device_id,
            available=True,
            current_power=current_power,
            soc=soc,
            capabilities=DeviceCapabilities(
                can_charge=can_charge,
                can_discharge=can_discharge,
                min_power=max(step, 1.0),
                max_charge_power=max_charge,
                max_discharge_power=max_discharge,
            ),
        )

    async def async_set_power(self, power: float) -> None:
        """Move the device towards the given signed target power.

        Positive power -> charge (AC input mode + input_limit).
        Negative power -> discharge (AC output mode + output_limit).

        Direction changes are throttled by MIN_MODE_SWITCH_INTERVAL
        to protect the device's AC relay from excessive cycling.
        """

        wants_input_mode = power > 0

        mode_switched_or_confirmed = await self._async_ensure_ac_mode(
            wants_input_mode
        )

        if not mode_switched_or_confirmed:
            # We're in a cooldown after a recent direction switch and
            # the requested direction doesn't match the device's
            # current mode. Do not fight the hardware - just leave it
            # as is until the cooldown expires.
            _LOGGER.debug(
                "Zendure '%s': skipping power request, AC mode "
                "switch on cooldown",
                self.device_id,
            )
            return

        if wants_input_mode:
            await self._async_set_number(self._input_limit_entity, power)
        else:
            await self._async_set_number(
                self._output_limit_entity, -power
            )

    async def _async_ensure_ac_mode(self, wants_input_mode: bool) -> bool:
        """Ensure the AC mode matches the requested direction.

        Returns True if the device is now (or already was) in the
        requested direction, False if a switch would be needed but is
        currently on cooldown or if no matching option could be found
        (logged as a warning in that case).
        """

        mode_state = self.hass.states.get(self._ac_mode_entity)

        if mode_state is None:
            # No mode select for this device - assume it doesn't need
            # one (e.g. a device with independent charge/discharge
            # paths) and let the caller proceed.
            return True

        options = list(mode_state.attributes.get("options", []))
        target_option = resolve_ac_mode_option(options, wants_input_mode)

        if target_option is None:
            _LOGGER.warning(
                "Zendure '%s': could not find an AC mode option for "
                "'%s' direction among %s - skipping",
                self.device_id,
                "input" if wants_input_mode else "output",
                options,
            )
            return False

        if mode_state.state == target_option:
            return True

        now = time.monotonic()

        if (
            self._last_mode_switch is not None
            and now - self._last_mode_switch < MIN_MODE_SWITCH_INTERVAL
        ):
            return False

        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self._ac_mode_entity, "option": target_option},
            blocking=True,
        )

        self._last_mode_switch = now

        _LOGGER.info(
            "Zendure '%s': switched AC mode to '%s'",
            self.device_id,
            target_option,
        )

        return True

    async def _async_set_number(self, entity_id: str, value: float) -> None:
        """Call number.set_value on the given entity."""

        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": value},
            blocking=True,
        )
