"""Watts Vision sensor platform -- central unit."""
import logging
from typing import Optional

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .exceptions import WattsVisionError
from .watts_api import WattsApi

_LOGGER = logging.getLogger(__name__)


class WattsVisionLastCommunicationSensor(SensorEntity):
    def __init__(
        self, wattsClient: WattsApi, smartHome: str, label: str, mac_address: str
    ):
        super().__init__()
        self.client = wattsClient
        self.smartHome = smartHome
        self._label = label
        self._name = "Last communication " + self._label
        self._state = None
        self._available = True
        self._mac_address = mac_address

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "last_communication_" + self.smartHome

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.smartHome)
            },
            "manufacturer": "Watts",
            "name": "Central Unit " + self._label,
            "model": "BT-CT02-RF",
            "connections": {("mac", self._mac_address)},
        }

    async def async_update(self):
        try:
            data = await self.hass.async_add_executor_job(
                self.client.getLastCommunication, self.smartHome
            )
        except WattsVisionError as err:
            # An entity update must not raise: Home Assistant logs a traceback
            # per entity per poll, which during the DNS outage of 2026-09-11
            # buried the log without telling anyone anything useful.
            _LOGGER.debug("Could not read the last communication time: %s", err)
            self._attr_available = False
            return

        self._attr_available = True
        self._state = "{} days, {} hours, {} minutes and {} seconds.".format(
            data["diffObj"]["days"],
            data["diffObj"]["hours"],
            data["diffObj"]["minutes"],
            data["diffObj"]["seconds"],
        )
