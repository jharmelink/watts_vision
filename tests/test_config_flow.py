"""Tests for the Watts Vision config flow."""
from unittest.mock import patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.watts_vision.const import DOMAIN
from custom_components.watts_vision.exceptions import (
    WattsVisionAuthError,
    WattsVisionConnectionError,
)

from . import MOCK_CONFIG, build_config_entry

# validate_input authenticates through getLoginToken so that a wrong password
# and an unreachable cloud arrive as different exceptions.
AUTH = "custom_components.watts_vision.watts_api.WattsApi.getLoginToken"


async def test_form_is_shown(hass: HomeAssistant):
    """The user step presents a form before anything is submitted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] in (None, {})


async def test_valid_credentials_create_an_entry(hass: HomeAssistant):
    """Credentials the cloud accepts produce a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch(AUTH, return_value="a-token"), patch(
        "custom_components.watts_vision.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_CONFIG[CONF_USERNAME]
    assert result["data"][CONF_USERNAME] == MOCK_CONFIG[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == MOCK_CONFIG[CONF_PASSWORD]


async def test_invalid_credentials_are_reported(hass: HomeAssistant):
    """Credentials the cloud rejects come back on the form, not as a crash."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch(AUTH, side_effect=WattsVisionAuthError("nope")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_unreachable_cloud_is_reported_separately(hass: HomeAssistant):
    """A wrong password and an unreachable cloud must not look the same."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch(AUTH, side_effect=WattsVisionConnectionError("no dns")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_username_is_rejected(hass: HomeAssistant):
    """The same account cannot be added twice."""
    build_config_entry().add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch(AUTH, return_value="a-token"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "username_exists"}


async def test_reauth_flow_updates_the_password(hass: HomeAssistant):
    """Setup raising ConfigEntryAuthFailed needs a reauth step to land on."""
    entry = build_config_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(AUTH, return_value="a-token"), patch(
        "custom_components.watts_vision.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "the-new-password"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_PASSWORD] == "the-new-password"
    # The account itself is unchanged; only the password was wrong.
    assert entry.data[CONF_USERNAME] == MOCK_CONFIG[CONF_USERNAME]


async def test_reauth_reports_a_still_wrong_password(hass: HomeAssistant):
    entry = build_config_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )

    with patch(AUTH, side_effect=WattsVisionAuthError("still no")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "wrong-again"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
