"""Watts Vision sensor platform."""
from datetime import timedelta
import logging
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

from .central_unit import WattsVisionLastCommunicationSensor
from .const import API_CLIENT, DOMAIN, ERROR_OPTIONS, PRESET_MODE_MAP, UNKNOWN_FAULT
from .device_state import (
    error_code,
    error_label,
    has_usable_setpoints,
    is_faulty,
    iter_devices,
    target_celsius,
)
from .helpers import sub_device_info
from .temperature import plausible_celsius
from .watts_api import WattsApi

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
):
    """Set up the sensor platform."""

    wattsClient: WattsApi = hass.data[DOMAIN][API_CLIENT]

    smartHomes = wattsClient.getSmartHomes()

    sensors = []

    for smarthome_id, zone_label, device in iter_devices(smartHomes):
        sensors.append(
            WattsVisionThermostatSensor(
                wattsClient, smarthome_id, device["id"], zone_label
            )
        )
        sensors.append(
            WattsVisionTemperatureSensor(
                wattsClient, smarthome_id, device["id"], zone_label
            )
        )
        sensors.append(
            WattsVisionErrorSensor(wattsClient, smarthome_id, device["id"], zone_label)
        )
        # A device with no setpoints -- a receiver, say -- has no target
        # temperature to report. Creating the entity anyway is what made it
        # crash on first update and vanish without explanation.
        if has_usable_setpoints(device):
            sensors.append(
                WattsVisionSetTemperatureSensor(
                    wattsClient, smarthome_id, device["id"], zone_label
                )
            )
        else:
            _LOGGER.info(
                "Device %s in zone %s reports no setpoints, so it gets no target "
                "temperature entity",
                device["id"],
                zone_label,
            )

    for smart_home in smartHomes or []:
        sensors.append(
            WattsVisionLastCommunicationSensor(
                wattsClient,
                smart_home["smarthome_id"],
                smart_home["label"],
                smart_home.get("mac_address"),
            )
        )

    async_add_entities(sensors, update_before_add=True)


class WattsVisionSensor(SensorEntity):
    """Shared behaviour for the per-device sensors."""

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


class WattsVisionThermostatSensor(WattsVisionSensor):
    """The operating mode a device is in."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, wattsClient: WattsApi, smartHome: str, id: str, zone: str):
        super().__init__(wattsClient, smartHome, id, zone)
        self._attr_name = "Heating mode " + zone
        self._attr_options = list(PRESET_MODE_MAP.values())

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "thermostat_mode_" + self.id

    async def async_update(self):
        device = self.device
        mode = PRESET_MODE_MAP.get(str(device.get("gv_mode"))) if device else None
        # An unrecognised mode leaves the entity unknown rather than raising,
        # which previously destroyed it.
        self._attr_available = device is not None
        self._attr_native_value = mode


class WattsVisionTemperatureSensor(WattsVisionSensor):
    """The air temperature a device measures."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, wattsClient: WattsApi, smartHome: str, id: str, zone: str):
        super().__init__(wattsClient, smartHome, id, zone)
        self._attr_name = "Air temperature " + zone

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "temperature_air_" + self.id

    @property
    def device_info(self):
        return sub_device_info(
            self.hass,
            self.smartHome,
            self.id,
            "Thermostat " + self.zone,
            suggested_area=self.zone,
        )

    async def async_update(self):
        device = self.device
        celsius = plausible_celsius(device.get("temperature_air")) if device else None
        # A device that has stopped reporting sends a sentinel, not nothing.
        # Publishing it wrote about 100 C into long-term statistics as a room
        # temperature; going unavailable keeps it out.
        self._attr_available = celsius is not None
        self._attr_native_value = celsius


class WattsVisionSetTemperatureSensor(WattsVisionSensor):
    """The target temperature of a device's active mode."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, wattsClient: WattsApi, smartHome: str, id: str, zone: str):
        super().__init__(wattsClient, smartHome, id, zone)
        self._attr_name = "Target temperature " + zone

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "target_temperature_" + self.id

    async def async_update(self):
        device = self.device
        self._attr_available = device is not None and not is_faulty(device)
        # A mode with no target -- off, or one we do not recognise -- reports
        # unknown. It used to publish the literal string "nan".
        self._attr_native_value = target_celsius(device)


class WattsVisionErrorSensor(WattsVisionSensor):
    """Whatever fault a device is reporting."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, wattsClient: WattsApi, smartHome: str, id: str, zone: str):
        super().__init__(wattsClient, smartHome, id, zone)
        self._attr_name = "Error " + zone
        self._attr_options = ERROR_OPTIONS
        self._reported_codes: set = set()

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "error_" + self.id

    async def async_update(self):
        device = self.device
        self._attr_available = device is not None
        if device is None:
            return

        label = error_label(device)
        self._attr_native_value = label
        # The raw value is the only thing a user of an undocumented API can
        # usefully report, so it is always exposed, recognised or not.
        self._attr_extra_state_attributes = {"raw_error_code": error_code(device)}

        code = error_code(device)
        if label == UNKNOWN_FAULT and code not in self._reported_codes:
            # Once per code per device: an unrecognised code is a normal
            # operating condition here, but it is still the signal that the
            # API has moved, and it should not flood the log to say so.
            self._reported_codes.add(code)
            _LOGGER.warning(
                "Device %s reports an unrecognised fault code %s. Please report "
                "this, with what the device itself is showing",
                self.id,
                code,
            )
