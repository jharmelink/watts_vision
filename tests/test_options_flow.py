"""Tests for the options flow.

The options flow is how a user changes stored credentials. It broke when Home
Assistant made `config_entry` a read-only property on `OptionsFlow`, and the
break was invisible to every existing test because none of them opened it.
"""
from unittest.mock import patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.watts_vision.exceptions import WattsVisionAuthError

from . import init_integration

NEW_CREDENTIALS = {
    CONF_USERNAME: "someone-else@example.com",
    CONF_PASSWORD: "also-not-real",
}


async def test_options_flow_can_be_opened(hass: HomeAssistant):
    """Opening the options flow presents the form rather than raising."""
    entry = await init_integration(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_updates_credentials(hass: HomeAssistant):
    """Submitting valid credentials updates the config entry."""
    entry = await init_integration(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch(
        "custom_components.watts_vision.watts_api.WattsApi.getLoginToken",
        return_value="a-token",
    ), patch(
        "custom_components.watts_vision.watts_api.WattsApi.loadData",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=NEW_CREDENTIALS
        )
        await hass.async_block_till_done()

    assert entry.data[CONF_USERNAME] == NEW_CREDENTIALS[CONF_USERNAME]
    assert entry.data[CONF_PASSWORD] == NEW_CREDENTIALS[CONF_PASSWORD]


async def test_options_flow_rejects_invalid_credentials(hass: HomeAssistant):
    """Credentials the cloud rejects are reported back on the form."""
    entry = await init_integration(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch(
        "custom_components.watts_vision.watts_api.WattsApi.getLoginToken",
        side_effect=WattsVisionAuthError("nope"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=NEW_CREDENTIALS
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_USERNAME] != NEW_CREDENTIALS[CONF_USERNAME]
