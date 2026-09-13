"""The write path: what actually reaches the thermostat.

This is where the "small temperature deviation" lived. Two setpoints on the
reference installation are off the device's grid because the conversion
truncated instead of rounding.
"""
import copy
from unittest.mock import patch

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
import pytest

from . import init_integration
from .test_entities import ZONES

PUSH = "custom_components.watts_vision.watts_api.WattsApi.pushTemperature"
THERMOSTAT = "climate.thermostat_woonkamer"


async def set_temperature(hass: HomeAssistant, celsius: float):
    with patch(PUSH, return_value=True) as push:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: THERMOSTAT, ATTR_TEMPERATURE: celsius},
            blocking=True,
        )
    return push


@pytest.fixture
async def loaded(hass: HomeAssistant):
    return await init_integration(hass, with_devices=True, zones=copy.deepcopy(ZONES))


@pytest.mark.parametrize(
    ("celsius", "expected"),
    [
        (15.1, "592"),  # int() sent 591, and the device kept it
        (21.1, "700"),  # int() sent 699
        (20.5, "689"),
        (20.6, "691"),
    ],
)
async def test_setpoints_are_rounded_not_truncated(
    hass: HomeAssistant, loaded, celsius, expected
):
    push = await set_temperature(hass, celsius)
    assert push.call_args.args[2] == expected


async def test_only_the_active_mode_setpoint_is_cached(hass: HomeAssistant, loaded):
    """Adjusting an eco target used to make the comfort setpoint appear to move."""
    client = hass.data["watts_vision"]["api"]
    device = client.getDevice("smarthome-1", "device-1")
    device["gv_mode"] = "3"
    comfort_before = device["consigne_confort"]

    await set_temperature(hass, 14.5)

    assert device["consigne_eco"] == "581"
    assert device["consigne_confort"] == comfort_before


async def test_the_active_mode_is_sent_with_the_setpoint(hass: HomeAssistant, loaded):
    client = hass.data["watts_vision"]["api"]
    client.getDevice("smarthome-1", "device-1")["gv_mode"] = "3"

    push = await set_temperature(hass, 14.5)

    assert push.call_args.args[3] == "3"


async def test_a_preset_change_sends_a_plausible_setpoint(hass: HomeAssistant, loaded):
    """The attribute holding a setpoint was once assigned the encoded string.

    A later multiplication then did string repetition, and a thirty digit
    number was sent to the thermostat as a temperature.
    """
    with patch(PUSH, return_value=True) as push:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: THERMOSTAT, ATTR_PRESET_MODE: "eco"},
            blocking=True,
        )

    value = push.call_args.args[2]
    assert value.isdigit()
    assert len(value) <= 4
    assert 0 < int(value) < 2000


async def test_frost_protection_sends_the_value_the_device_holds(
    hass: HomeAssistant, loaded
):
    with patch(PUSH, return_value=True) as push:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: THERMOSTAT, ATTR_PRESET_MODE: "Frost Protection"},
            blocking=True,
        )

    assert push.call_args.args[2] == "446"


async def test_a_faulty_device_is_not_written_to(hass: HomeAssistant, loaded):
    """Nothing useful can come of setting a temperature it cannot receive."""
    with patch(PUSH, return_value=True) as push:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.thermostat_studio", ATTR_TEMPERATURE: 20.0},
            blocking=True,
        )

    push.assert_not_called()
