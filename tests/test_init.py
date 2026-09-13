"""Test component setup."""
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.watts_vision.const import API_CLIENT, DOMAIN

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
