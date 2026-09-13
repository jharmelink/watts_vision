from datetime import timedelta

from homeassistant.components.climate.const import (
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
)

API_CLIENT = "api"

CENTRAL_UNIT_IDS = "central_unit_ids"

DOMAIN = "watts_vision"

PRESET_DEFROST = "Frost Protection"
PRESET_OFF = "Off"
PRESET_PROGRAM_ON = "Program on"
PRESET_PROGRAM_OFF = "Program off"

PRESET_MODE_MAP = {
    "0": PRESET_COMFORT,
    "1": PRESET_OFF,
    "2": PRESET_DEFROST,
    "3": PRESET_ECO,
    "4": PRESET_BOOST,
    "8": PRESET_PROGRAM_ON,
    "11": PRESET_PROGRAM_OFF,
}

PRESET_MODE_REVERSE_MAP = {
    PRESET_COMFORT: "0",
    PRESET_OFF: "1",
    PRESET_DEFROST: "2",
    PRESET_ECO: "3",
    PRESET_BOOST: "4",
    PRESET_PROGRAM_ON: "8",
    PRESET_PROGRAM_OFF: "11",
}

SCAN_INTERVAL = timedelta(seconds=120)

# `error_code` is a BITFIELD, not an enumeration. The reference installation's
# two faulty devices both report 12288, which is 0x3000: bits 12 and 13. Any
# lookup that assumes a short list of discrete codes will eventually miss, which
# is how the previous ERROR_MAP took two entities down with it.
#
# Health is therefore derived structurally -- zero is healthy, anything else is
# a fault -- and labels are applied only where there is evidence.
NO_ISSUES = "No issues"
NOT_REPORTING = "Not reporting"
UNKNOWN_FAULT = "Unrecognised fault"

# Observed, with provenance, not guessed. 12288 appears on a device with a flat
# battery AND on one the owner considers simply broken, so it says the device
# has stopped reporting, not why. It is deliberately not labelled as a battery
# fault: telling someone to replace a battery in a failed thermostat sends them
# to fix the wrong thing.
ERROR_LABELS = {
    0: NO_ISSUES,
    12288: NOT_REPORTING,
}

ERROR_OPTIONS = [NO_ISSUES, NOT_REPORTING, UNKNOWN_FAULT]
