"""Tests for the Zendure adapter's AC-mode option resolution.

Regression coverage for a real bug: hardcoding the exact option
strings ("AC-Ausgangsmodus"/"AC-Eingangsmodus") caused
ServiceValidationError: not_valid_option on a real installation,
because the actual wording didn't match. resolve_ac_mode_option()
instead reads the entity's own `options` attribute and matches
loosely on "ausgang"/"eingang" (or "output"/"input"), so exact
wording no longer needs to be guessed in advance.
"""

from __future__ import annotations

from custom_components.hems.adapters.zendure import (
    SOC_EMPTY_THRESHOLD,
    SOC_FULL_THRESHOLD,
    resolve_ac_mode_option,
)


def test_resolves_german_hyphenated_wording() -> None:
    """The wording originally (incorrectly) hardcoded still resolves."""

    options = ["AC-Ausgangsmodus", "AC-Eingangsmodus"]

    assert resolve_ac_mode_option(options, wants_input_mode=False) == (
        "AC-Ausgangsmodus"
    )
    assert resolve_ac_mode_option(options, wants_input_mode=True) == (
        "AC-Eingangsmodus"
    )


def test_resolves_german_spaced_wording() -> None:
    """A space instead of a hyphen still resolves correctly."""

    options = ["AC Ausgangsmodus", "AC Eingangsmodus"]

    assert resolve_ac_mode_option(options, wants_input_mode=False) == (
        "AC Ausgangsmodus"
    )
    assert resolve_ac_mode_option(options, wants_input_mode=True) == (
        "AC Eingangsmodus"
    )


def test_resolves_english_wording() -> None:
    """English-language installations resolve via "output"/"input"."""

    options = ["Output Mode", "Input Mode"]

    assert resolve_ac_mode_option(options, wants_input_mode=False) == (
        "Output Mode"
    )
    assert resolve_ac_mode_option(options, wants_input_mode=True) == (
        "Input Mode"
    )


def test_matching_is_case_insensitive() -> None:
    """Matching does not depend on capitalization."""

    options = ["AUSGANG", "eingang"]

    assert resolve_ac_mode_option(options, wants_input_mode=False) == (
        "AUSGANG"
    )
    assert resolve_ac_mode_option(options, wants_input_mode=True) == (
        "eingang"
    )


def test_unknown_wording_returns_none() -> None:
    """Unrecognized option wording fails safe (None) rather than
    guessing and sending an invalid value to the device."""

    options = ["Mode A", "Mode B"]

    assert resolve_ac_mode_option(options, wants_input_mode=False) is None
    assert resolve_ac_mode_option(options, wants_input_mode=True) is None


def test_empty_options_returns_none() -> None:
    """No options at all also fails safe."""

    assert resolve_ac_mode_option([], wants_input_mode=False) is None


# -- SoC-aware capability gating --------------------------------------
#
# Regression coverage for a real bug found on a live installation:
# HEMS kept commanding a charge limit to a battery that was already
# at 100% SoC. The number entity's own `max` attribute doesn't know
# about the BMS's SoC limits, so DeviceState.capabilities must be
# gated using the SoC reading too.


def _capabilities_for_soc(
    soc: float | None,
    max_charge: float = 800.0,
    max_discharge: float = 800.0,
) -> tuple[bool, bool]:
    """Mirror of the gating logic in ZendureAdapter.async_get_state().

    Reimplemented here (rather than driving the real hass-dependent
    adapter) so this can run without Home Assistant installed.
    """

    can_charge = max_charge > 0 and (
        soc is None or soc < SOC_FULL_THRESHOLD
    )
    can_discharge = max_discharge > 0 and (
        soc is None or soc > SOC_EMPTY_THRESHOLD
    )
    return can_charge, can_discharge


def test_full_battery_cannot_charge_but_can_discharge() -> None:
    """A battery at 100% SoC must not be offered charge headroom."""

    can_charge, can_discharge = _capabilities_for_soc(soc=100.0)

    assert can_charge is False
    assert can_discharge is True


def test_empty_battery_cannot_discharge_but_can_charge() -> None:
    """A battery at 0% SoC must not be offered discharge headroom."""

    can_charge, can_discharge = _capabilities_for_soc(soc=0.5)

    assert can_charge is True
    assert can_discharge is False


def test_mid_range_soc_allows_both_directions() -> None:
    """A battery with plenty of headroom allows both directions."""

    can_charge, can_discharge = _capabilities_for_soc(soc=55.0)

    assert can_charge is True
    assert can_discharge is True


def test_unknown_soc_fails_open() -> None:
    """If SoC can't be read, don't block - just use the number limits."""

    can_charge, can_discharge = _capabilities_for_soc(soc=None)

    assert can_charge is True
    assert can_discharge is True
