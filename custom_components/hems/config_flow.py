"""Config flow for the HEMS integration."""

from __future__ import annotations

from typing import Any

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import create_api
from .api.exceptions import (
    HemsConnectionError,
    HemsInvalidResponseError,
)
from .adapters.zendure import discover_zendure_device_prefixes
from .const import CONF_ENABLED_ZENDURE_DEVICES, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class HemsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HEMS."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "HemsOptionsFlow":
        """Return the options flow."""

        return HemsOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial configuration."""

        errors: dict[str, str] = {}

        if user_input is not None:

            host: str = user_input[CONF_HOST]
            port: int = user_input[CONF_PORT]

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            api = create_api(
                session=async_get_clientsession(self.hass),
                host=host,
                port=port,
            )

            try:
                await api.async_get_power()

            except HemsConnectionError:
                errors["base"] = "cannot_connect"

            except HemsInvalidResponseError:
                errors["base"] = "invalid_response"

            except Exception:
                _LOGGER.exception("Unexpected error during configuration")
                errors["base"] = "unknown"

            else:
                return self.async_create_entry(
                    title=f"EcoTracker ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class HemsOptionsFlow(config_entries.OptionsFlow):
    """Handle HEMS options.

    Lets the user explicitly opt in ("enable") each auto-discovered
    Zendure battery before HEMS is allowed to control it directly.
    Devices are never controlled automatically just because they
    were detected - the user has to confirm each one here first.

    HEMS controls each device directly rather than delegating to
    Zendure's own Manager - see controller.py for why.

    Note: this deliberately does NOT define __init__ / set
    self.config_entry manually. Recent Home Assistant versions
    provide `self.config_entry` on the base OptionsFlow class as a
    read-only property; assigning to it here would raise an error.
    """

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Let the user enable/disable each discovered Zendure device."""

        device_prefixes = discover_zendure_device_prefixes(self.hass)

        currently_enabled = set(
            self.config_entry.options.get(CONF_ENABLED_ZENDURE_DEVICES, [])
        )

        if user_input is not None:
            enabled = [
                prefix
                for prefix in device_prefixes
                if user_input.get(prefix, False)
            ]
            return self.async_create_entry(
                title="",
                data={CONF_ENABLED_ZENDURE_DEVICES: enabled},
            )

        if not device_prefixes:
            # Nothing discovered yet (e.g. the Zendure integration
            # isn't installed/loaded). Show an empty form so the
            # options dialog still opens cleanly.
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
            )

        schema = vol.Schema(
            {
                vol.Optional(
                    prefix,
                    default=prefix in currently_enabled,
                ): bool
                for prefix in device_prefixes
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
