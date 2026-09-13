"""Testing for Watts Vision Component."""
from contextlib import ExitStack
from unittest.mock import patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.watts_vision.const import DOMAIN

MOCK_CONFIG = {
    CONF_USERNAME: "user@example.com",
    CONF_PASSWORD: "not-a-real-password",
}

# Values taken from a real installation. Temperatures are tenths of a degree
# Fahrenheit, which is what the Watts cloud speaks: 689 is 20.5 C, 446 is the
# 7.0 C frost protection setpoint, 410/986 are the 5-37 C setpoint limits.
MOCK_DEVICE = {
    "id": "device-1",
    "id_device": "id-device-1",
    "temperature_air": "689",
    "gv_mode": "0",
    "heating_up": "0",
    "heat_cool": "0",
    "error_code": 0,
    "min_set_point": "410",
    "max_set_point": "986",
    "consigne_confort": "689",
    "consigne_hg": "446",
    "consigne_eco": "572",
    "consigne_boost": "770",
    "consigne_manuel": "689",
}

MOCK_SMARTHOME = {
    "smarthome_id": "smarthome-1",
    "label": "Test Home",
    "mac_address": "00:11:22:33:44:55",
}

MOCK_ZONES = [{"zone_label": "Woonkamer", "devices": [MOCK_DEVICE]}]

MOCK_LAST_COMMUNICATION = {
    "diffObj": {"days": 0, "hours": 0, "minutes": 0, "seconds": 12}
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
    hass: HomeAssistant,
    entry: MockConfigEntry | None = None,
    with_devices: bool = False,
) -> MockConfigEntry:
    """Set up the integration with the Watts cloud mocked out.

    Only the network boundary is mocked. Home Assistant is real, which is the
    point: the defects this guards against live in how the integration talks to
    the platform, not in how it talks to Watts.

    With `with_devices`, the two request methods are stubbed rather than
    `loadData`, so the real `loadData` and `reloadDevices` run and entities are
    created. Anything that depends on a device existing -- device registry
    behaviour above all -- needs this.
    """
    entry = entry or build_config_entry()
    entry.add_to_hass(hass)

    api = "custom_components.watts_vision.watts_api.WattsApi"
    stubs = [patch(f"{api}.getLoginToken", return_value="a-token")]
    if with_devices:
        stubs += [
            patch(f"{api}.loadSmartHomes", return_value=[dict(MOCK_SMARTHOME)]),
            patch(f"{api}.loadDevices", return_value=MOCK_ZONES),
            patch(
                f"{api}.getLastCommunication",
                return_value=MOCK_LAST_COMMUNICATION,
            ),
        ]
    else:
        stubs.append(patch(f"{api}.loadData", return_value=True))

    with ExitStack() as stack:
        for stub in stubs:
            stack.enter_context(stub)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
