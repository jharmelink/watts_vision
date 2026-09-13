"""Reading a Watts device's state without trusting any of it.

Every value the API returns is untrusted input. Unknown error codes, absent
fields and present-but-null fields are normal operating conditions, not
exceptional ones, so every lookup here is total: it returns something usable
for any input, and never raises.
"""
from .const import ERROR_LABELS, UNKNOWN_FAULT
from .temperature import deci_f_to_celsius

# Which setpoint field holds the target temperature in each operating mode.
# A mode absent from this map has no target temperature.
SETPOINT_FOR_MODE = {
    "0": "consigne_confort",
    "2": "consigne_hg",
    "3": "consigne_eco",
    "4": "consigne_boost",
    "8": "consigne_manuel",
    "11": "consigne_manuel",
}

# Every setpoint field a device might carry, used to decide whether a device
# is a thermostat at all.
SETPOINT_FIELDS = (
    "consigne_confort",
    "consigne_hg",
    "consigne_eco",
    "consigne_boost",
    "consigne_manuel",
)


def error_code(device) -> int | None:
    """Return a device's error code as an integer, or None if unreadable."""
    if not device:
        return None
    try:
        return int(device.get("error_code"))
    except (TypeError, ValueError):
        return None


def is_faulty(device) -> bool:
    """Return whether a device reports any fault.

    Structural rather than enumerated: zero is healthy and anything else is a
    fault. That holds for a bitfield as well as for a list of codes, which is
    why it survived the discovery that the field is a bitfield.
    """
    code = error_code(device)
    return code is not None and code != 0


def error_label(device) -> str:
    """Return a human-readable fault state, never raising on a new code."""
    code = error_code(device)
    if code is None:
        return UNKNOWN_FAULT
    return ERROR_LABELS.get(code, UNKNOWN_FAULT)


def has_usable_setpoints(device) -> bool:
    """Return whether a device is one you can set a temperature on.

    Tests for a usable *value*, not for a key. The reference installation's
    receiver reports `consigne_confort` and `min_set_point` as null, so a
    presence check would call it a thermostat and then crash converting null.
    """
    if not device:
        return False
    return any(
        deci_f_to_celsius(device.get(field)) is not None for field in SETPOINT_FIELDS
    )


def target_celsius(device) -> float | None:
    """Return the active target temperature, or None when there is not one.

    A mode with no setpoint, and a mode we do not recognise, both give None.
    An unrecognised mode must never raise: it would destroy the entity.
    """
    if not device:
        return None
    field = SETPOINT_FOR_MODE.get(str(device.get("gv_mode")))
    if field is None:
        return None
    return deci_f_to_celsius(device.get(field))


def setpoint_limits(device) -> tuple[float | None, float | None]:
    """Return the device's own setpoint range, as far as it reports one."""
    if not device:
        return (None, None)
    return (
        deci_f_to_celsius(device.get("min_set_point")),
        deci_f_to_celsius(device.get("max_set_point")),
    )


def device_name(device) -> str | None:
    """Return the name the API holds for a device, if it has a real one.

    `nom_appareil` is a user-settable name. An unconfigured device carries the
    factory default "nouvel appareil", French for "new device", which names
    nothing and is not worth putting in front of a user.
    """
    for field in ("nom_appareil", "label_interface"):
        name = (device or {}).get(field)
        if name and str(name).strip().lower() != "nouvel appareil":
            return str(name).strip()
    return None


def iter_devices(smart_homes):
    """Yield (smarthome_id, label, device) for every device reported.

    A zone is a control grouping rather than a location, and one can hold more
    than one device -- a thermostat and a receiver, say. Without a
    discriminator those are told apart only by Home Assistant appending "_2" to
    whichever it registers second, which depends on the order the API returns
    them in.

    The device's own name is used where a zone holds several, and only there,
    so a zone with one device keeps a clean name. A device with no real name
    falls back to the zone label and lets Home Assistant disambiguate, which is
    no worse than before.
    """
    for smart_home in smart_homes or []:
        for zone in smart_home.get("zones") or []:
            devices = zone.get("devices") or []
            shared = len(devices) > 1
            for device in devices:
                label = zone.get("zone_label")
                name = device_name(device) if shared else None
                if name:
                    label = f"{label} {name}"
                yield smart_home["smarthome_id"], label, device


def reports_heating_state(device) -> bool:
    """Return whether a device says anything about calling for heat.

    The receiver reports `heating_up` as null. Treating that as "not zero, so
    it must be heating" made its sensor read on while the thermostat beside it
    read off.
    """
    return bool(device) and device.get("heating_up") is not None
