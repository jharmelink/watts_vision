"""
Config flow for Watts Vision integration.
"""
import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import voluptuous as vol

from .const import DOMAIN
from .exceptions import WattsVisionAuthError, WattsVisionConnectionError
from .watts_api import WattsApi

CONFIG_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], current: dict[str, Any] = None
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Authenticates through `getLoginToken` rather than `test_authentication`, so
    that a wrong password and an unreachable cloud arrive as different
    exceptions and can be reported to the user as different things.
    """

    # Check if the username already exists as an entry
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    for entry in existing_entries:
        if entry.data.get(CONF_USERNAME) == data[CONF_USERNAME] and (
            current is None or entry.data.get(CONF_USERNAME) != current.get("username")
        ):
            raise UsernameExists

    api = WattsApi(hass, data[CONF_USERNAME], data[CONF_PASSWORD])
    await hass.async_add_executor_job(api.getLoginToken, True)

    # Return info that you want to store in the config entry.
    return data


def _error_for(exception: Exception) -> str:
    """Map an exception onto the error key shown on the form."""
    if isinstance(exception, WattsVisionAuthError):
        return "invalid_auth"
    if isinstance(exception, WattsVisionConnectionError):
        return "cannot_connect"
    if isinstance(exception, UsernameExists):
        return "username_exists"
    return "unknown"


class WattsVisionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Watts Vision."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] = None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

        errors = {}

        try:
            _LOGGER.debug("Validate input")
            await validate_input(self.hass, user_input)
        except Exception as exception:  # pylint: disable=broad-except
            errors["base"] = _error_for(exception)
            if errors["base"] == "unknown":
                _LOGGER.exception("Unexpected exception")
        else:
            return self.async_create_entry(
                title=str(user_input["username"]), data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Start reauthentication after the cloud rejected stored credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] = None):
        """Ask for a new password for the account already configured."""
        entry = self._get_reauth_entry()
        errors = {}

        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                await validate_input(self.hass, data, entry.data)
            except Exception as exception:  # pylint: disable=broad-except
                errors["base"] = _error_for(exception)
                if errors["base"] == "unknown":
                    _LOGGER.exception("Unexpected exception")
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class UsernameExists(HomeAssistantError):
    """Error to indicate the username already exists."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for the Watts Vision integration."""

    # `config_entry` is supplied by the base class as a read-only property.
    # Assigning it here raised AttributeError and made the options flow
    # unopenable.

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                _LOGGER.debug("Validate input")
                validated_data = await validate_input(
                    self.hass, user_input, self.config_entry.data
                )

                # Update entry
                _LOGGER.debug("Updating entry")
                updated = self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=str(user_input["username"]),
                    data=validated_data,
                )
                if updated:
                    # Reload entry
                    _LOGGER.debug("Reloading entry")
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )

            except Exception as exception:  # pylint: disable=broad-except
                errors["base"] = _error_for(exception)
                if errors["base"] == "unknown":
                    _LOGGER.exception("Unexpected exception")
            else:
                # If updated, return to overview
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=str(self.config_entry.data[CONF_USERNAME]),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
