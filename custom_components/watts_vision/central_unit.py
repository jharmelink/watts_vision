"""Watts Vision sensor platform -- central unit."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .exceptions import WattsVisionError
from .watts_api import WattsApi

_LOGGER = logging.getLogger(__name__)


class WattsVisionLastCommunicationSensor(SensorEntity):
    """How long ago the central unit last reached the Watts cloud."""

    def __init__(
        self, wattsClient: WattsApi, smartHome: str, label: str, mac_address: str
    ):
        super().__init__()
        self.client = wattsClient
        self.smartHome = smartHome
        self._label = label
        self._mac_address = mac_address
        self._attr_name = "Last communication " + label

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "last_communication_" + self.smartHome

    @property
    def device_info(self):
        connections = set()
        if self._mac_address:
            connections.add((dr.CONNECTION_NETWORK_MAC, self._mac_address))
        return {
            "identifiers": {(DOMAIN, self.smartHome)},
            "manufacturer": "Watts",
            "name": "Central Unit " + self._label,
            "model": "BT-CT02-RF",
            "connections": connections,
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

        difference = (data or {}).get("diffObj") or {}
        self._attr_available = bool(difference)
        if not difference:
            return

        self._attr_native_value = (
            "{} days, {} hours, {} minutes and {} seconds.".format(
                difference.get("days"),
                difference.get("hours"),
                difference.get("minutes"),
                difference.get("seconds"),
            )
        )
