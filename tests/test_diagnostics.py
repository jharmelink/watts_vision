"""Diagnostics, and above all what must never appear in them.

Diagnostics get pasted into public issue trackers. A wrong temperature is
recoverable; a leaked credential is not, so the redaction tests here matter more
than anything else in this file.
"""
import copy
import json

from homeassistant.core import HomeAssistant
import pytest

from custom_components.watts_vision.diagnostics import (
    async_get_config_entry_diagnostics,
)

from . import MOCK_CONFIG, MOCK_SMARTHOME, init_integration
from .test_entities import ZONES


@pytest.fixture
async def diagnostics(hass: HomeAssistant):
    entry = await init_integration(hass, with_devices=True, zones=copy.deepcopy(ZONES))
    return await async_get_config_entry_diagnostics(hass, entry)


def flatten(payload) -> str:
    return json.dumps(payload, default=str)


async def test_no_credential_reaches_the_output(diagnostics):
    text = flatten(diagnostics)
    assert MOCK_CONFIG["password"] not in text
    assert MOCK_CONFIG["username"] not in text
    assert "a-token" not in text


async def test_identifiers_are_pseudonymised_not_leaked(diagnostics):
    text = flatten(diagnostics)
    assert MOCK_SMARTHOME["mac_address"] not in text
    assert MOCK_SMARTHOME["smarthome_id"] not in text
    # Pseudonymised rather than removed, so devices stay distinguishable.
    assert "id-" in text


async def test_an_unexpected_field_cannot_leak_a_secret(hass: HomeAssistant):
    """Redaction must protect fields nobody has thought of yet.

    The API is undocumented and can add fields without notice, so a key-name
    deny-list alone is not enough: values known to be secret are redacted
    wherever they appear, under any key.
    """
    zones = copy.deepcopy(ZONES)
    zones[0]["devices"][0]["some_field_invented_next_year"] = MOCK_CONFIG["password"]
    zones[0]["devices"][0]["owner_contact_details"] = MOCK_CONFIG["username"]

    entry = await init_integration(hass, with_devices=True, zones=zones)
    text = flatten(await async_get_config_entry_diagnostics(hass, entry))

    assert MOCK_CONFIG["password"] not in text
    assert MOCK_CONFIG["username"] not in text


async def test_raw_values_are_included_verbatim(diagnostics):
    """Fields the integration ignores are the point of the export."""
    device = diagnostics["devices"][0]
    assert device["raw"]["temperature_air"] == "689"
    assert device["raw"]["consigne_confort"] == "689"


async def test_the_interpretation_sits_alongside_the_raw_values(diagnostics):
    device = diagnostics["devices"][0]
    assert device["integration"]["decoded"]["air_temperature_celsius"] == pytest.approx(
        20.5
    )
    assert device["integration"]["decoded"]["target_temperature_celsius"] == (
        pytest.approx(20.5)
    )


async def test_a_skipped_entity_is_explained(diagnostics):
    """The receiver's missing thermostat should not be a mystery."""
    receiver = next(
        device
        for device in diagnostics["devices"]
        if device["raw"]["temperature_air"] == "536"
    )
    assert receiver["integration"]["entities"]["climate"] is False
    assert "no usable setpoint" in receiver["integration"]["skipped"].lower()


async def test_unrecognised_values_are_surfaced(diagnostics):
    """The sentinel behind the 100 C readings is exposed nowhere else."""
    faulty = next(
        device
        for device in diagnostics["devices"]
        if device["raw"]["temperature_air"] == "2124"
    )
    assert faulty["integration"]["unrecognised"]["air_temperature_implausible"] == (
        "2124"
    )
    assert faulty["integration"]["decoded"]["error_code"] == 12288
    assert faulty["integration"]["decoded"]["faulty"] is True
