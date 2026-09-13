"""Test component setup."""
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.watts_vision.const import API_CLIENT, DOMAIN, SCAN_INTERVAL
from custom_components.watts_vision.exceptions import (
    WattsVisionAuthError,
    WattsVisionConnectionError,
)

from . import build_config_entry, init_integration


async def test_setup_entry(hass: HomeAssistant):
    """The integration sets up against a real Home Assistant instance."""
    entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert API_CLIENT in hass.data[DOMAIN]


async def test_unload_entry(hass: HomeAssistant):
    """Unloading releases the API client."""
    entry = await init_integration(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert API_CLIENT not in hass.data[DOMAIN]


async def test_setup_entry_fails_when_login_fails(hass: HomeAssistant):
    """A failure to authenticate is reported as a failure to set up."""
    entry = build_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.watts_vision.watts_api.WattsApi.getLoginToken",
        side_effect=Exception("no"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is not ConfigEntryState.LOADED


async def test_auth_failure_asks_the_user_to_reauthenticate(hass: HomeAssistant):
    """A wrong password must not be retried forever in the background."""
    entry = build_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.watts_vision.watts_api.WattsApi.getLoginToken",
        side_effect=WattsVisionAuthError("rejected"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow for flow in flows if flow["context"]["source"] == "reauth"]


async def test_unreachable_cloud_is_retried(hass: HomeAssistant):
    """An outage is transient, so Home Assistant should try again by itself."""
    entry = build_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.watts_vision.watts_api.WattsApi.getLoginToken",
        side_effect=WattsVisionConnectionError("no dns"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    # Distinct from the auth case: nothing to ask the user, so no reauth flow.
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert not [flow for flow in flows if flow["context"]["source"] == "reauth"]


async def test_a_failed_refresh_does_not_raise_into_home_assistant(
    hass: HomeAssistant, caplog
):
    """The 2026-09-11 outage put a requests traceback through the timer."""
    await init_integration(hass, with_devices=True)

    with patch(
        "custom_components.watts_vision.watts_api.WattsApi.loadDevices",
        side_effect=WattsVisionConnectionError("no dns"),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL * 2)
        await hass.async_block_till_done()

    assert "Refreshing Watts Vision devices failed" in caplog.text
    assert "Traceback" not in caplog.text
