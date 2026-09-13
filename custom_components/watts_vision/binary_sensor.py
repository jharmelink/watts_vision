"""Watts Vision binary sensor platform."""
from datetime import timedelta
import logging
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import API_CLIENT, DOMAIN
from .device_state import error_code, is_faulty, iter_devices, reports_heating_state
from .helpers import sub_device_info
from .watts_api import WattsApi

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
):
    """Set up the binary_sensor platform."""
    wattsClient: WattsApi = hass.data[DOMAIN][API_CLIENT]

    sensors = []
    for smarthome_id, zone_label, device in iter_devices(wattsClient.getSmartHomes()):
        sensors.append(
            WattsVisionHeatingBinarySensor(
                wattsClient, smarthome_id, device["id"], zone_label
            )
        )
        sensors.append(
            WattsVisionProblemBinarySensor(
                wattsClient, smarthome_id, device["id"], zone_label
            )
        )

    async_add_entities(sensors, update_before_add=True)


class WattsVisionBinarySensor(BinarySensorEntity):
    """Shared behaviour for the per-device binary sensors."""

    def __init__(self, wattsClient: WattsApi, smartHome: str, id: str, zone: str):
        super().__init__()
        self.client = wattsClient
        self.smartHome = smartHome
        self.id = id
        self.zone = zone

    @property
    def device(self):
        """Return the cached device, which may be absent after a failed load."""
        return self.client.getDevice(self.smartHome, self.id)

    @property
    def device_info(self):
        return sub_device_info(
            self.hass, self.smartHome, self.id, "Thermostat " + self.zone
        )


class WattsVisionHeatingBinarySensor(WattsVisionBinarySensor):
    """Whether a device is currently calling for heat."""

    def __init__(self, wattsClient: WattsApi, smartHome: str, id: str, zone: str):
        super().__init__(wattsClient, smartHome, id, zone)
        self._attr_name = "Heating " + zone

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "thermostat_is_heating_" + self.id

    async def async_update(self):
        device = self.device
        # A device that is not reporting cannot be heating or not heating; it
        # is simply unknown, and saying "off" would be inventing an answer.
        # Nor can a device that never reports the field at all: a null here
        # used to compare unequal to "0" and come out as on.
        self._attr_available = (
            device is not None
            and not is_faulty(device)
            and reports_heating_state(device)
        )
        self._attr_is_on = reports_heating_state(device) and (
            device.get("heating_up") != "0"
        )


class WattsVisionProblemBinarySensor(WattsVisionBinarySensor):
    """Whether a device is reporting a fault.

    Deliberately a problem rather than a battery. The error code observed on
    faulty devices appears on one with a flat battery and on one that is simply
    broken, so it says the device has stopped working and nothing about why.
    Reporting it as a battery would send someone to buy batteries for a
    thermostat that needs replacing.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = None

    def __init__(self, wattsClient: WattsApi, smartHome: str, id: str, zone: str):
        super().__init__(wattsClient, smartHome, id, zone)
        self._attr_name = "Problem " + zone

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "thermostat_problem_" + self.id

    async def async_update(self):
        device = self.device
        # Stays available while faulty: reporting the fault is its whole job.
        self._attr_available = device is not None
        if device is None:
            return
        self._attr_is_on = is_faulty(device)
        self._attr_extra_state_attributes = {"raw_error_code": error_code(device)}
