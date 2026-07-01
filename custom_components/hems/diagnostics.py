"""Diagnostics support for the HEMS integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

TO_REDACT = {
    CONF_HOST,
    "serial_number",
    "mac",
    "token",
    "password",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    runtime_data = entry.runtime_data
    coordinator = runtime_data.coordinator
    controller = runtime_data.controller

    return {
        "config_entry": async_redact_data(
            {
                **entry.data,
                **entry.options,
            },
            TO_REDACT,
        ),
        "last_update_success": coordinator.last_update_success,
        "data": {
            "power": coordinator.data.power if coordinator.data else None,
            "grid_import": (
                coordinator.data.import_power
                if coordinator.data
                else None
            ),
            "grid_export": (
                coordinator.data.export_power
                if coordinator.data
                else None
            ),
            "direction": (
                coordinator.data.direction.value
                if coordinator.data
                else None
            ),
            "trend": coordinator.data.trend if coordinator.data else None,
            "stable": coordinator.data.stable if coordinator.data else None,
            "samples": (
                coordinator.data.samples if coordinator.data else None
            ),
        },
        "controlled_devices": controller.device_manager.device_ids,
    }
