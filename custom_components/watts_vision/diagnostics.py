"""Diagnostics for Watts Vision.

The valuable content here is the part of the API payload the integration does
*not* understand. Every investigation into this integration has so far started
with someone hand-writing template queries in Developer Tools, and even then
could only see values that reached an entity attribute -- the sentinel behind
the 100 C readings is the root cause of a user-visible bug and is exposed
nowhere in Home Assistant at all.

So the raw payload is included verbatim, after redaction, and what the
integration made of it sits alongside rather than instead.
"""
from __future__ import annotations

import hashlib
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import API_CLIENT, DOMAIN, PRESET_MODE_MAP
from .device_state import (
    SETPOINT_FIELDS,
    error_code,
    error_label,
    has_usable_setpoints,
    is_faulty,
    target_celsius,
)
from .temperature import deci_f_to_celsius, is_plausible

REDACTED = "**REDACTED**"

# Matched as substrings of a key, lower-cased, so a field nobody has thought
# about yet is caught by its name rather than by having been listed. The API is
# undocumented and can add fields without notice, and diagnostics get pasted
# into public issue trackers.
SENSITIVE_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "auth",
    "credential",
    "mail",
    "mac",
    "phone",
    "address",
    "latitude",
    "longitude",
    "gps",
)

# Identifiers are pseudonymised rather than removed, so devices can still be
# told apart in the output without the values being usable against the account.
IDENTIFIER_FRAGMENTS = ("smarthome_id", "id_device", "device_id", "uuid", "serial")


def _pseudonym(value: Any) -> str:
    digest = hashlib.sha256(str(value).encode()).hexdigest()
    return f"id-{digest[:12]}"


def _redact(value: Any, secrets: set[str]) -> Any:
    """Redact recursively, by key name and by value.

    Two independent defences, because either alone is insufficient. Key matching
    catches fields we can name; value matching catches a field we cannot, such as
    a new key holding the account's email under a name nobody predicted.
    """
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in SENSITIVE_FRAGMENTS):
                redacted[key] = REDACTED
            elif lowered == "id" or any(
                fragment in lowered for fragment in IDENTIFIER_FRAGMENTS
            ):
                redacted[key] = _pseudonym(item) if item is not None else None
            else:
                redacted[key] = _redact(item, secrets)
        return redacted
    if isinstance(value, (list, tuple)):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, str) and value and value in secrets:
        return REDACTED
    return value


def _secrets_of(entry: ConfigEntry, client) -> set[str]:
    """Every value known to be secret, for value-based redaction."""
    values = {
        entry.data.get("username"),
        entry.data.get("password"),
        getattr(client, "_token", None),
        getattr(client, "_refresh_token", None),
    }
    return {str(value) for value in values if value}


def _interpretation(device: dict) -> dict:
    """What the integration made of one device, next to its raw values."""
    air = deci_f_to_celsius(device.get("temperature_air"))
    setpoints = has_usable_setpoints(device)
    return {
        "decoded": {
            "air_temperature_celsius": air,
            "air_temperature_plausible": is_plausible(air),
            "target_temperature_celsius": target_celsius(device),
            "setpoints_celsius": {
                field: deci_f_to_celsius(device.get(field)) for field in SETPOINT_FIELDS
            },
            "preset_mode": PRESET_MODE_MAP.get(str(device.get("gv_mode"))),
            "error_code": error_code(device),
            "error_label": error_label(device),
            "faulty": is_faulty(device),
        },
        "unrecognised": {
            "gv_mode": (
                device.get("gv_mode")
                if str(device.get("gv_mode")) not in PRESET_MODE_MAP
                else None
            ),
            "air_temperature_implausible": (
                device.get("temperature_air") if not is_plausible(air) else None
            ),
        },
        "entities": {
            "climate": setpoints,
            "target_temperature": setpoints,
            "air_temperature": True,
            "heating_mode": True,
            "heating": True,
            "problem": True,
            "error": True,
        },
        "skipped": (
            None
            if setpoints
            else "No usable setpoint values, so this device is not a thermostat"
        ),
    }


def _payload(hass: HomeAssistant, entry: ConfigEntry, only_device: str | None = None):
    client = hass.data.get(DOMAIN, {}).get(API_CLIENT)
    smart_homes = client.getSmartHomes() if client else []
    secrets = _secrets_of(entry, client) if client else set()

    devices = []
    for smart_home in smart_homes or []:
        for zone in smart_home.get("zones") or []:
            for device in zone.get("devices") or []:
                if only_device and device.get("id") != only_device:
                    continue
                devices.append(
                    {
                        "zone_label": zone.get("zone_label"),
                        # Verbatim, including every field the integration
                        # ignores. That is the point of the export.
                        "raw": _redact(device, secrets),
                        "integration": _interpretation(device),
                    }
                )

    return {
        "note": (
            "Raw values are tenths of a degree Fahrenheit. Identifiers are "
            "pseudonymised consistently, so devices can be told apart without "
            "the values being usable against the account."
        ),
        # Built field by field rather than from entry.as_dict(), so nothing in
        # the config entry can reach the output by being forgotten about.
        "entry": {
            "version": entry.version,
            "domain": entry.domain,
            "source": entry.source,
            "username": REDACTED,
            "password": REDACTED,
        },
        "smart_home_count": len(smart_homes or []),
        "device_count": len(devices),
        "devices": devices,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the whole installation."""
    return _payload(hass, entry)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a single device.

    Lets one unexpected device be inspected without exporting the whole
    installation, which is how the receiver in the reference installation would
    have been identified.
    """
    identifier = next(
        (value for domain, value in device.identifiers if domain == DOMAIN), None
    )
    return _payload(hass, entry, only_device=identifier)
