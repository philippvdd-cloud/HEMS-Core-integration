"""DataUpdateCoordinator for the HEMS integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import create_api
from .api.exceptions import (
    HemsConnectionError,
    HemsInvalidResponseError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .energy_manager import EnergyManager
from .models import GridState

_LOGGER = logging.getLogger(__name__)


class HemsCoordinator(DataUpdateCoordinator[GridState]):
    """Coordinator responsible for updating HEMS data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""

        self.config_entry = config_entry

        self.api = create_api(
            session=async_get_clientsession(hass),
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
        )

        self.energy_manager = EnergyManager()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> GridState:
        """Fetch and process the latest data."""

        try:
            raw_data = await self.api.async_get_power()

            return self.energy_manager.update(raw_data)

        except HemsConnectionError as err:
            raise UpdateFailed(
                "Could not connect to EcoTracker."
            ) from err

        except HemsInvalidResponseError as err:
            raise UpdateFailed(
                "Invalid EcoTracker response."
            ) from err

        except Exception as err:
            _LOGGER.exception(
                "Unexpected error while updating HEMS"
            )
            raise UpdateFailed(str(err)) from err
