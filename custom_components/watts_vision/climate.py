"""Watts Vision climate platform."""
import functools
import logging
from typing import Callable

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

from .const import (
    API_CLIENT,
    DOMAIN,
    PRESET_MODE_MAP,
    PRESET_MODE_REVERSE_MAP,
    PRESET_OFF,
)
from .device_state import (
    SETPOINT_FIELDS,
    has_usable_setpoints,
    is_faulty,
    iter_devices,
    setpoint_limits,
    target_celsius,
)
from .helpers import sub_device_info
from .temperature import celsius_to_deci_f, deci_f_to_celsius, plausible_celsius
from .watts_api import WattsApi

_LOGGER = logging.getLogger(__name__)

# The device stores tenths of a degree Fahrenheit, roughly 0.056 C, so no
# Celsius step is exact. 0.1 C is offered as a usability choice -- it keeps
# every value a user is likely to want reachable from the card -- and is not a
# claim about the device's resolution. Confirmed on hardware: writing an
# off-grid value to an active setpoint reads back unchanged, so the device does
# not quantise to half degrees.
TARGET_TEMPERATURE_STEP = 0.1

# 7.0 C, the frost protection setpoint the device holds in that mode.
DEFROST_DECI_F = "446"

# Which setpoint a mode writes when it is entered.
SETPOINT_TO_WRITE = {
    "0": "consigne_confort",
    "3": "consigne_eco",
    "4": "consigne_boost",
}


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
):
    """Set up the climate platform."""

    wattsClient: WattsApi = hass.data[DOMAIN][API_CLIENT]

    smartHomes = wattsClient.getSmartHomes()

    devices = []

    for smarthome_id, label, device in iter_devices(smartHomes):
        # Only a device you can set a temperature on gets a thermostat. A
        # receiver reports null setpoints, and building a climate entity for it
        # is what made it crash and disappear.
        if not has_usable_setpoints(device):
            _LOGGER.info(
                "Device %s in %s reports no setpoints, so it gets no climate "
                "entity",
                device["id"],
                label,
            )
            continue
        devices.append(
            WattsThermostat(
                wattsClient,
                smarthome_id,
                device["id"],
                device["id_device"],
                label,
            )
        )

    async_add_entities(devices, update_before_add=True)


class WattsThermostat(ClimateEntity):
    """A Watts Vision thermostat."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = TARGET_TEMPERATURE_STEP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    def __init__(
        self, wattsClient: WattsApi, smartHome: str, id: str, deviceID: str, zone: str
    ):
        super().__init__()
        self.client = wattsClient
        self.smartHome = smartHome
        self.id = id
        self.zone = zone
        self.deviceID = deviceID
        self._attr_name = "Thermostat " + zone
        self._attr_preset_modes = list(PRESET_MODE_MAP.values())
        self._attr_extra_state_attributes = {"previous_gv_mode": "0"}

    @property
    def unique_id(self):
        """Return the unique ID for this device."""
        return "watts_thermostat_" + self.id

    @property
    def device(self):
        """Return the cached device, which may be absent after a failed load."""
        return self.client.getDevice(self.smartHome, self.id)

    @property
    def device_info(self):
        return sub_device_info(
            self.hass, self.smartHome, self.id, "Thermostat " + self.zone
        )

    async def async_update(self):
        device = self.device
        if device is None:
            self._attr_available = False
            return

        # A faulty device still has valid cached setpoints, so the thermostat
        # stays usable; only the measurement it cannot make goes away.
        self._attr_available = True
        self._attr_current_temperature = plausible_celsius(
            device.get("temperature_air")
        )

        minimum, maximum = setpoint_limits(device)
        if minimum is not None:
            self._attr_min_temp = minimum
        if maximum is not None:
            self._attr_max_temp = maximum

        if device.get("heating_up") == "0":
            self._attr_hvac_action = (
                HVACAction.OFF if device.get("gv_mode") == "1" else HVACAction.IDLE
            )
        elif device.get("heat_cool") == "1":
            self._attr_hvac_action = HVACAction.COOLING
        else:
            self._attr_hvac_action = HVACAction.HEATING

        if device.get("gv_mode") == "1":
            self._attr_hvac_mode = HVACMode.OFF
        elif device.get("heat_cool") == "1":
            self._attr_hvac_mode = HVACMode.COOL
        else:
            self._attr_hvac_mode = HVACMode.HEAT

        # An unrecognised mode leaves the preset unknown rather than raising.
        self._attr_preset_mode = PRESET_MODE_MAP.get(str(device.get("gv_mode")))
        self._attr_target_temperature = target_celsius(device)

        # The raw setpoints, in degrees Fahrenheit, as the only window onto the
        # wire format outside diagnostics. Always floats: assigning the
        # deci-Fahrenheit string here meant a later multiplication did string
        # repetition and sent a thirty digit number to the thermostat.
        for field in SETPOINT_FIELDS:
            value = device.get(field)
            self._attr_extra_state_attributes[field] = (
                float(value) / 10.0 if value is not None else None
            )
        self._attr_extra_state_attributes["gv_mode"] = device.get("gv_mode")

    def _setpoint_for(self, gv_mode: str) -> str:
        """Return the deci-Fahrenheit value to send when entering a mode.

        Reads from the cached device rather than from entity attributes, so a
        value can never be re-encoded from something already encoded.
        """
        if gv_mode == "2":
            return DEFROST_DECI_F
        device = self.device or {}
        field = SETPOINT_TO_WRITE.get(gv_mode, "consigne_manuel")
        celsius = deci_f_to_celsius(device.get(field))
        return celsius_to_deci_f(celsius) if celsius is not None else "0"

    async def _push(self, value: str, gv_mode: str):
        func = functools.partial(
            self.client.pushTemperature, self.smartHome, self.deviceID, value, gv_mode
        )
        await self.hass.async_add_executor_job(func)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self._attr_extra_state_attributes[
                "previous_gv_mode"
            ] = self._attr_extra_state_attributes.get("gv_mode", "0")
            await self._push("0", PRESET_MODE_REVERSE_MAP[PRESET_OFF])
            return

        previous = self._attr_extra_state_attributes.get("previous_gv_mode", "0")
        await self._push(self._setpoint_for(previous), previous)

    async def async_set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        gv_mode = PRESET_MODE_REVERSE_MAP.get(preset_mode)
        if gv_mode is None:
            _LOGGER.warning("Unknown preset mode %s requested", preset_mode)
            return

        if preset_mode == PRESET_OFF:
            self._attr_extra_state_attributes[
                "previous_gv_mode"
            ] = self._attr_extra_state_attributes.get("gv_mode", "0")
            await self._push("0", gv_mode)
            return

        await self._push(self._setpoint_for(gv_mode), gv_mode)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        device = self.device
        if device is None or is_faulty(device):
            _LOGGER.warning(
                "Not setting a temperature on device %s, which is not reporting",
                self.id,
            )
            return

        value = celsius_to_deci_f(temperature)
        gv_mode = str(device.get("gv_mode"))

        # Reloading the devices takes up to the poll interval, so the cache is
        # updated optimistically. Only the active mode's setpoint is touched:
        # writing consigne_confort regardless of mode made the comfort setpoint
        # appear to change when the user adjusted an eco one.
        field = SETPOINT_TO_WRITE.get(gv_mode, "consigne_manuel")
        if gv_mode == "2":
            field = "consigne_hg"
        device[field] = value
        device["consigne_manuel"] = value
        self.client.setDevice(self.smartHome, self.id, device)

        await self._push(value, gv_mode)
