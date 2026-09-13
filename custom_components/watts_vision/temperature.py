"""The single boundary between the Watts wire format and the rest of the world.

The API expresses every temperature as an integer number of tenths of a degree
Fahrenheit: `446` is 7.0 °C, the frost protection setpoint, and `689` is 20.5 °C.
This was inferred from observation and corroborated by two independent
implementations of the same API.

Everything above this module speaks Celsius. Converting here rather than in each
entity is the point: the defect this replaces was the same conversion written
five times, three of them differently.
"""

# A room thermostat reporting outside this range is not reporting. It is a
# backstop against sentinel values we have not seen, not the primary way a
# faulty device is detected -- see the device health rules.
MIN_PLAUSIBLE_C = -20.0
MAX_PLAUSIBLE_C = 60.0


def deci_f_to_celsius(raw) -> float | None:
    """Decode an API temperature into Celsius.

    Returns `None` for anything unusable. The API sends setpoint keys with null
    values for devices that have no setpoints, so a missing value and a present
    null must be treated the same; a key-presence test is not enough.
    """
    if raw is None:
        return None
    try:
        return (float(raw) / 10.0 - 32.0) * 5.0 / 9.0
    except (TypeError, ValueError):
        return None


def celsius_to_deci_f(celsius) -> str:
    """Encode a Celsius temperature for the API.

    Rounds to the nearest tenth of a degree Fahrenheit. Truncating instead --
    which is what `int()` did -- lost up to a tenth of a degree on every write,
    and is why two setpoints on the reference installation sit off the grid.
    """
    return str(round((float(celsius) * 9.0 / 5.0 + 32.0) * 10.0))


def is_plausible(celsius: float | None) -> bool:
    """Return whether a decoded temperature could be a real room reading."""
    return celsius is not None and MIN_PLAUSIBLE_C <= celsius <= MAX_PLAUSIBLE_C


def plausible_celsius(raw) -> float | None:
    """Decode an API temperature, returning `None` when it cannot be real.

    A device that has stopped reporting sends a sentinel rather than omitting
    the field. On the reference installation that sentinel decodes to about
    100 °C, and was being recorded into long-term statistics as a room
    temperature.
    """
    celsius = deci_f_to_celsius(raw)
    return celsius if is_plausible(celsius) else None
