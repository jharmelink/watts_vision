"""Shared device registry helpers."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CENTRAL_UNIT_IDS, DOMAIN


def register_central_units(
    hass: HomeAssistant, entry: ConfigEntry, smart_homes
) -> None:
    """Register each central unit and remember its device registry id.

    Sub-devices link to their central unit with `via_device_id`, which is a
    device registry id rather than an identifier tuple, so the central unit has
    to exist before any platform is set up. Registering here rather than letting
    a sensor create it implicitly is what makes the ordering reliable.
    """
    registry = dr.async_get(hass)
    ids: dict[str, str] = {}

    for smart_home in smart_homes or []:
        smarthome_id = smart_home.get("smarthome_id")
        if smarthome_id is None:
            continue

        connections = set()
        if mac_address := smart_home.get("mac_address"):
            connections.add((dr.CONNECTION_NETWORK_MAC, mac_address))

        device = registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, smarthome_id)},
            manufacturer="Watts",
            name="Central Unit " + str(smart_home.get("label", smarthome_id)),
            model="BT-CT02-RF",
            connections=connections,
        )
        ids[smarthome_id] = device.id

    hass.data[DOMAIN][CENTRAL_UNIT_IDS] = ids


def central_unit_device_id(hass: HomeAssistant, smarthome_id: str) -> str | None:
    """Return the registry id of a smart home's central unit, if registered."""
    return hass.data.get(DOMAIN, {}).get(CENTRAL_UNIT_IDS, {}).get(smarthome_id)


def sub_device_info(
    hass: HomeAssistant, smarthome_id: str, identifier: str, name: str, **extra
) -> dict:
    """Build device info for a device hanging off a central unit.

    `via_device_id` is omitted rather than set to None when the central unit is
    not registered, because the key is typed as a string and an absent parent is
    better expressed by saying nothing.
    """
    info = {
        "identifiers": {(DOMAIN, identifier)},
        "manufacturer": "Watts",
        "name": name,
        "model": "BT-D03-RF",
        **extra,
    }
    if via_id := central_unit_device_id(hass, smarthome_id):
        info["via_device_id"] = via_id
    return info
