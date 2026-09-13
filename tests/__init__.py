"""Testing for Watts Vision Component."""
from unittest.mock import patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.watts_vision.const import DOMAIN

MOCK_CONFIG = {
    CONF_USERNAME: "user@example.com",
    CONF_PASSWORD: "not-a-real-password",
}


def build_config_entry(data: dict | None = None) -> MockConfigEntry:
    """Return a config entry for this integration."""
    config = data or MOCK_CONFIG
    return MockConfigEntry(
        domain=DOMAIN,
        title=config[CONF_USERNAME],
        data=config,
    )


async def init_integration(
    hass: HomeAssistant, entry: MockConfigEntry | None = None
) -> MockConfigEntry:
    """Set up the integration with the Watts cloud mocked out.

    Only the network boundary is mocked. Home Assistant is real, which is the
    point: the defects this guards against live in how the integration talks to
    the platform, not in how it talks to Watts.
    """
    entry = entry or build_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.watts_vision.watts_api.WattsApi.getLoginToken",
        return_value="a-token",
    ), patch(
        "custom_components.watts_vision.watts_api.WattsApi.loadData",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
