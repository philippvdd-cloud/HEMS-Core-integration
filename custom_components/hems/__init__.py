"""HEMS integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .controller import HemsController
from .coordinator import HemsCoordinator

PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
)


@dataclass(slots=True)
class HemsRuntimeData:
    """Objects shared across the HEMS integration for one config entry."""

    coordinator: HemsCoordinator
    controller: HemsController


async def async_setup(
    hass: HomeAssistant,
    config: dict,
) -> bool:
    """Set up the HEMS integration."""
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up HEMS from a config entry."""

    coordinator = HemsCoordinator(
        hass=hass,
        config_entry=entry,
    )

    await coordinator.async_config_entry_first_refresh()

    controller = HemsController(
        hass=hass,
        coordinator=coordinator,
    )

    await controller.async_setup()

    entry.runtime_data = HemsRuntimeData(
        coordinator=coordinator,
        controller=controller,
    )

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    entry.async_on_unload(
        entry.add_update_listener(_async_update_listener)
    )

    return True


async def _async_update_listener(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload the entry when its options change.

    This makes newly enabled/disabled devices (via the options flow)
    take effect immediately, without requiring a manual restart.
    """

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload HEMS."""

    runtime_data: HemsRuntimeData | None = entry.runtime_data

    if runtime_data is not None:
        runtime_data.controller.async_unload()

    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
