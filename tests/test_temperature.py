"""Tests for the deci-Fahrenheit conversion boundary.

The expected values are not invented. Every one was read off a real
installation, which is what makes them worth asserting: the arithmetic was
rewritten twice before on the assumption that it was wrong, and it never was.
"""
import pytest

from custom_components.watts_vision.temperature import (
    celsius_to_deci_f,
    deci_f_to_celsius,
    is_plausible,
    plausible_celsius,
)

# Observed on the reference installation, with what each decodes to.
OBSERVED = [
    ("446", 7.0),  # consigne_hg, frost protection on every device
    ("563", 13.5),
    ("572", 14.0),
    ("590", 15.0),
    ("689", 20.5),
    ("698", 21.0),
]


@pytest.mark.parametrize(("raw", "celsius"), OBSERVED)
def test_observed_values_decode_exactly(raw, celsius):
    assert deci_f_to_celsius(raw) == pytest.approx(celsius)


def test_off_grid_values_are_reported_as_they_are():
    """Two setpoints sit off the half-degree grid, from the truncation defect.

    They are reported as stored rather than snapped: the device holds tenths of
    a degree Fahrenheit, so these are what it actually has.
    """
    assert deci_f_to_celsius("591") == pytest.approx(15.0556, abs=1e-4)
    assert deci_f_to_celsius("699") == pytest.approx(21.0556, abs=1e-4)


@pytest.mark.parametrize(
    ("celsius", "expected"),
    [
        (15.1, "592"),  # int() gave 591: the observed defect
        (21.1, "700"),  # int() gave 699: the observed defect
        (20.5, "689"),
        (20.6, "691"),
        (7.0, "446"),
        (15.0, "590"),
    ],
)
def test_writes_round_rather_than_truncate(celsius, expected):
    assert celsius_to_deci_f(celsius) == expected


def test_every_half_degree_survives_a_round_trip():
    """5.0 to 37.0 °C is the range the devices report as their limits."""
    for step in range(10, 75):
        celsius = step / 2
        assert deci_f_to_celsius(celsius_to_deci_f(celsius)) == pytest.approx(celsius)


def test_a_tenth_of_a_degree_survives_within_the_device_resolution():
    """The device stores 0.1 °F, so 0.1 °C is not exactly representable.

    The error must stay well inside the tenth of a degree Home Assistant
    displays, or the card would show a value the user did not choose.
    """
    for step in range(50, 371):
        celsius = step / 10
        round_tripped = deci_f_to_celsius(celsius_to_deci_f(celsius))
        assert round_tripped == pytest.approx(celsius, abs=0.03)


@pytest.mark.parametrize("raw", [None, "", "not a number", {}, []])
def test_unusable_values_decode_to_none(raw):
    """Setpoint keys arrive present-but-null for devices without setpoints."""
    assert deci_f_to_celsius(raw) is None


def test_the_dead_device_sentinel_is_not_a_temperature():
    """About 100 °C, and it was being recorded as a room temperature."""
    assert deci_f_to_celsius("2124") == pytest.approx(100.22, abs=0.01)
    assert is_plausible(deci_f_to_celsius("2124")) is False
    assert plausible_celsius("2124") is None


@pytest.mark.parametrize("raw", ["446", "689", "2124", None, "rubbish"])
def test_decoding_never_raises(raw):
    """Every value the API returns is untrusted input."""
    deci_f_to_celsius(raw)
    plausible_celsius(raw)


def test_plausible_values_pass_through():
    assert plausible_celsius("689") == pytest.approx(20.5)
    assert plausible_celsius("446") == pytest.approx(7.0)
