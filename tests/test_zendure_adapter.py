"""Tests for the Zendure adapter's entity-based device discovery.

These only exercise the pure, hass-independent logic
(``extract_device_prefixes``) - not the parts of ZendureAdapter that
call Home Assistant services, which need a running hass instance and
are exercised in integration tests instead.
"""

from __future__ import annotations

from custom_components.hems.adapters.zendure import extract_device_prefixes


def test_discovers_devices_from_real_world_entity_list() -> None:
    """Regression test using a real Home Assistant entity dump.

    This is the exact set of Zendure-related entity ids reported from
    a live installation with a SolarFlow 800 Pro and two Hyper 2000
    units.
    """

    entities = [
        "sensor.batterieleistung_gesamt_solarflow",
        "number.solarflow_800_pro_output_limit",
        "number.solarflow_800_pro_input_limit",
        "number.solarflow_800_pro_min_soc",
        "number.solarflow_800_pro_soc_set",
        "sensor.solarflow_800_pro_electric_level",
        "select.solarflow_800_pro_ac_mode",
        "number.hyper_2000_garage_output_limit",
        "number.hyper_2000_garage_input_limit",
        "number.hyper_2000_garage_min_soc",
        "sensor.hyper_2000_garage_electric_level",
        "number.hyper_2000_gro_output_limit",
        "number.hyper_2000_gro_input_limit",
        "number.hyper_2000_gro_min_soc",
        "sensor.hyper_2000_gro_electric_level",
        # Noise that must NOT be picked up as a device:
        "update.battery_smartflow_ai_update",
        "update.power_flow_card_plus_update",
        "device_tracker.hyper1",
        "switch.hyper1_internetzugang",
    ]

    result = extract_device_prefixes(entities)

    assert result == [
        "hyper_2000_garage",
        "hyper_2000_gro",
        "solarflow_800_pro",
    ]


def test_ignores_output_limit_without_matching_input_limit() -> None:
    """A device is only confirmed if both limits are present."""

    entities = [
        "number.orphan_device_output_limit",
        # no matching input_limit for "orphan_device"
        "number.real_device_output_limit",
        "number.real_device_input_limit",
    ]

    result = extract_device_prefixes(entities)

    assert result == ["real_device"]


def test_empty_input_returns_empty_list() -> None:
    """No number entities means no discovered devices."""

    assert extract_device_prefixes([]) == []


def test_ignores_non_number_domain_entities() -> None:
    """Entities outside the number domain are never matched."""

    entities = [
        "sensor.some_device_output_limit",
        "switch.some_device_input_limit",
    ]

    assert extract_device_prefixes(entities) == []
