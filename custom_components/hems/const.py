"""Constants for the HEMS integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "hems"
NAME: Final = "HEMS"

MANUFACTURER: Final = "HEMS Project"

VERSION: Final = "0.0.1"

DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=2)

# How often the DecisionEngine -> Scheduler -> DeviceManager control
# loop runs. Deliberately slower than DEFAULT_SCAN_INTERVAL: sensors
# can update quickly without commanding devices on every tick, which
# would generate unnecessary traffic and (for devices like Zendure
# batteries with a switchable AC relay) unnecessary wear.
DEFAULT_CONTROL_INTERVAL: Final = timedelta(seconds=30)

# How much PV surplus (in watts) HEMS is allowed to let flow into the
# grid before it starts charging batteries with the excess.
DEFAULT_EXPORT_ALLOWANCE: Final = 800.0

DEFAULT_PORT: Final = 80

API_TIMEOUT: Final = 5

# Options-flow key storing the list of Zendure entity-prefixes the
# user has explicitly enabled for HEMS control (opt-in per device).
# This is the active approach: HEMS controls each device directly
# rather than delegating to Zendure's own Manager.
CONF_ENABLED_ZENDURE_DEVICES: Final = "enabled_zendure_devices"

# Options-flow key: whether HEMS is allowed to control the Zendure
# fleet via the Zendure Manager's "manual" mode. Currently unused -
# kept alongside adapters/zendure_manager.py in case delegating to
# Zendure's Manager becomes preferable again later.
CONF_ZENDURE_MANAGER_ENABLED: Final = "zendure_manager_enabled"
