"""Boost duration and stopping a boost.

The README has listed "program, stop boost, etc." as unfinished since the
project began. Boost was hardcoded to two hours and could only be left by
selecting another preset, which also rewrote that preset's setpoint.
"""
import copy
from unittest.mock import patch

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
import pytest

from . import init_integration
from .test_entities import ZONES

PUSH = "custom_components.watts_vision.watts_api.WattsApi.pushTemperature"
THERMOSTAT = "climate.thermostat_woonkamer_verwarm_therm"
DOMAIN = "watts_vision"


@pytest.fixture
async def loaded(hass: HomeAssistant):
    return await init_integration(hass, with_devices=True, zones=copy.deepcopy(ZONES))


async def refresh(hass: HomeAssistant):
    """Pull the entity's view of the device back into line with the cache."""
    await async_update_entity(hass, THERMOSTAT)
    await hass.async_block_till_done()


async def call(hass: HomeAssistant, service: str, **data):
    with patch(PUSH, return_value=True) as push:
        await hass.services.async_call(
            DOMAIN, service, {ATTR_ENTITY_ID: THERMOSTAT, **data}, blocking=True
        )
    return push


async def test_a_boost_runs_for_the_requested_duration(hass: HomeAssistant, loaded):
    push = await call(hass, "start_boost", duration=45)

    assert push.call_args.args[3] == "4"
    assert push.call_args.args[4] == 45 * 60


async def test_a_boost_without_a_duration_uses_the_documented_default(
    hass: HomeAssistant, loaded
):
    """Two hours, which is what the integration sent before it was a choice."""
    push = await call(hass, "start_boost")

    assert push.call_args.args[4] == 120 * 60


async def test_stopping_a_boost_returns_to_the_previous_mode(
    hass: HomeAssistant, loaded
):
    client = hass.data[DOMAIN]["api"]
    device = client.getDevice("smarthome-1", "device-1")
    device["gv_mode"] = "3"  # eco before the boost
    await refresh(hass)

    await call(hass, "start_boost", duration=30)
    device["gv_mode"] = "4"  # the cloud confirms the boost
    await refresh(hass)

    push = await call(hass, "stop_boost")

    assert push.call_args.args[3] == "3"


async def test_stopping_a_boost_does_not_change_that_mode_setpoint(
    hass: HomeAssistant, loaded
):
    """Selecting a preset to escape a boost rewrote that preset's setpoint."""
    client = hass.data[DOMAIN]["api"]
    device = client.getDevice("smarthome-1", "device-1")
    device["gv_mode"] = "3"
    eco_before = device["consigne_eco"]
    await refresh(hass)

    await call(hass, "start_boost")
    device["gv_mode"] = "4"
    await refresh(hass)
    push = await call(hass, "stop_boost")

    # The value sent back is the one the device already holds, so nothing moves.
    assert push.call_args.args[2] == eco_before
    assert device["consigne_eco"] == eco_before


async def test_stopping_when_not_boosting_does_nothing(hass: HomeAssistant, loaded):
    push = await call(hass, "stop_boost")
    push.assert_not_called()


async def test_remaining_boost_time_is_visible(hass: HomeAssistant, loaded):
    client = hass.data[DOMAIN]["api"]
    device = client.getDevice("smarthome-1", "device-1")
    device["gv_mode"] = "4"
    device["time_boost"] = "1800"
    await refresh(hass)

    state = hass.states.get(THERMOSTAT)
    assert state.attributes["boost_seconds_remaining"] == 1800


async def test_remaining_boost_time_is_absent_when_not_boosting(
    hass: HomeAssistant, loaded
):
    state = hass.states.get(THERMOSTAT)
    assert state.attributes["boost_seconds_remaining"] is None


async def test_program_mode_sends_no_setpoint(hass: HomeAssistant, loaded):
    """The weekly schedule owns the setpoint in program mode.

    The mode previously fell through the request builder to an empty payload,
    so the setpoint its caller had computed was discarded in silence. Sending
    nothing is now what the branch says it does.
    """
    from custom_components.watts_vision.watts_api import WattsApi

    client = hass.data[DOMAIN]["api"]
    with patch.object(WattsApi, "_post", return_value={}) as post:
        await hass.async_add_executor_job(
            client.pushTemperature, "smarthome-1", "id-device-1", "689", "8"
        )

    query = post.call_args.args[2]
    assert not [key for key in query if key.startswith("query[consigne")]
    assert query["query[gv_mode]"] == "8"
