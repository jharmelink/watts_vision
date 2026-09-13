"""Device registry behaviour.

Sub-devices used to declare their parent with `via_device`, an identifier tuple,
which Home Assistant removes in 2027.8.0. They now use `via_device_id`, a
registry id, which means the central unit has to be registered before any
platform is set up. These tests pin the resulting shape.
"""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.watts_vision.const import DOMAIN

from . import MOCK_DEVICE, MOCK_SMARTHOME, init_integration


async def test_central_unit_is_registered(hass: HomeAssistant):
    """The central unit exists as a device in its own right."""
    entry = await init_integration(hass, with_devices=True)

    registry = dr.async_get(hass)
    central = registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SMARTHOME["smarthome_id"]), entry.entry_id
    )

    assert central is not None
    assert central.manufacturer == "Watts"
    assert (dr.CONNECTION_NETWORK_MAC, MOCK_SMARTHOME["mac_address"]) in (
        central.connections
    )


async def test_sub_devices_hang_off_the_central_unit(hass: HomeAssistant):
    """A thermostat is linked to its central unit by registry id."""
    entry = await init_integration(hass, with_devices=True)

    registry = dr.async_get(hass)
    central = registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SMARTHOME["smarthome_id"]), entry.entry_id
    )
    thermostat = registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_DEVICE["id"]), entry.entry_id
    )

    assert thermostat is not None
    assert thermostat.via_device_id == central.id


async def test_reload_does_not_duplicate_devices(hass: HomeAssistant):
    """Setting up again reuses the existing devices rather than adding more.

    Identifiers are unchanged by the `via_device_id` migration, so an
    installation that already has devices registered must keep them, along with
    the history attached to their entities.
    """
    entry = await init_integration(hass, with_devices=True)

    registry = dr.async_get(hass)
    before = {
        device.id
        for device in dr.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert len(before) == 2  # the central unit and one thermostat

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await init_integration(hass, entry=entry, with_devices=True)

    after = {
        device.id
        for device in dr.async_entries_for_config_entry(registry, entry.entry_id)
    }

    assert after == before
