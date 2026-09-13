"""Entity behaviour for devices that are faulty, partial, or ordinary.

The fixtures mirror the reference installation: a healthy thermostat, two
devices reporting the 12288 fault with the sentinel temperature, and a receiver
whose setpoint fields are present but null.
"""
import copy

from homeassistant.core import HomeAssistant
import pytest

from . import MOCK_DEVICE, init_integration

# A device that has stopped reporting: error_code 12288 is bits 12 and 13, and
# temperature_air is the sentinel that decodes to about 100 C.
FAULTY_DEVICE = {
    **MOCK_DEVICE,
    "id": "device-faulty",
    "id_device": "id-device-faulty",
    "temperature_air": "2124",
    "error_code": 12288,
}

# A receiver: reports a temperature and a mode, but its setpoint fields are
# present with null values rather than absent.
RECEIVER_DEVICE = {
    "id": "device-receiver",
    "id_device": "id-device-receiver",
    "nom_appareil": "nouvel appareil",
    "label_interface": "nouvel appareil",
    "temperature_air": "536",
    "gv_mode": "0",
    "heating_up": None,
    "heat_cool": None,
    "error_code": 0,
    "min_set_point": None,
    "max_set_point": None,
    "consigne_confort": None,
    "consigne_hg": None,
    "consigne_eco": None,
    "consigne_boost": None,
    "consigne_manuel": None,
}

ZONES = [
    {
        "zone_label": "Woonkamer",
        "devices": [
            {**copy.deepcopy(MOCK_DEVICE), "nom_appareil": "Verwarm.Therm"},
            copy.deepcopy(RECEIVER_DEVICE),
        ],
    },
    {"zone_label": "Studio", "devices": [copy.deepcopy(FAULTY_DEVICE)]},
]


@pytest.fixture
async def loaded(hass: HomeAssistant):
    """Set the integration up with the mixed device fixture."""
    return await init_integration(hass, with_devices=True, zones=copy.deepcopy(ZONES))


async def test_a_healthy_thermostat_reports_celsius(hass: HomeAssistant, loaded):
    """689 deci-Fahrenheit is 20.5 C, and that is what the entity reports."""
    state = hass.states.get("climate.thermostat_woonkamer_verwarm_therm")
    assert state is not None
    assert state.attributes["temperature"] == pytest.approx(20.5)
    assert state.attributes["current_temperature"] == pytest.approx(20.5)
    assert state.attributes["target_temp_step"] == 0.1


async def test_the_sentinel_is_not_published_as_a_temperature(
    hass: HomeAssistant, loaded
):
    """About 100 C was being recorded into long-term statistics."""
    state = hass.states.get("sensor.thermostat_studio_air_temperature_studio")
    assert state is not None
    assert state.state == "unavailable"


async def test_a_faulty_device_still_gets_its_error_entity(hass: HomeAssistant, loaded):
    """ERROR_MAP[12288] raised KeyError, and the entity was never created."""
    state = hass.states.get("sensor.thermostat_studio_error_studio")
    assert state is not None
    assert state.state == "Not reporting"
    assert state.attributes["raw_error_code"] == 12288


async def test_a_faulty_device_reports_a_problem(hass: HomeAssistant, loaded):
    """A problem, not a battery: the code does not say why it stopped."""
    state = hass.states.get("binary_sensor.thermostat_studio_problem_studio")
    assert state is not None
    assert state.state == "on"

    healthy = hass.states.get(
        "binary_sensor.thermostat_woonkamer_verwarm_therm_problem_woonkamer_verwarm_therm"
    )
    assert healthy.state == "off"


async def test_a_receiver_gets_no_thermostat(hass: HomeAssistant, loaded):
    """Null setpoints are not setpoints, and a presence check would miss that."""
    assert hass.states.get("climate.thermostat_woonkamer") is None
    assert (
        hass.states.get("sensor.thermostat_woonkamer_target_temperature_woonkamer")
        is None
    )


async def test_a_receiver_keeps_the_entities_it_can_support(
    hass: HomeAssistant, loaded
):
    """It loses only what it cannot have, and by decision rather than by crash."""
    assert (
        hass.states.get("sensor.thermostat_woonkamer_air_temperature_woonkamer")
        is not None
    )
    assert (
        hass.states.get("sensor.thermostat_woonkamer_heating_mode_woonkamer")
        is not None
    )
    assert (
        hass.states.get("binary_sensor.thermostat_woonkamer_heating_woonkamer")
        is not None
    )
    assert hass.states.get("sensor.thermostat_woonkamer_error_woonkamer") is not None


async def test_climate_and_sensor_agree_on_the_target(hass: HomeAssistant, loaded):
    """The spec requires these to report the same number, and they did not.

    Availability was tied to the device's health, so a faulty device showed a
    target on its thermostat card and "unavailable" on the sensor beside it.
    A setpoint is configuration the cloud holds, not a measurement the device
    makes, so it stays knowable while the device is silent.
    """
    for zone in ("woonkamer_verwarm_therm", "studio"):
        climate = hass.states.get(f"climate.thermostat_{zone}")
        sensor = hass.states.get(f"sensor.thermostat_{zone}_target_temperature_{zone}")
        assert climate is not None and sensor is not None
        assert sensor.state != "unavailable"
        assert float(sensor.state) == pytest.approx(climate.attributes["temperature"])


async def test_a_faulty_device_keeps_the_setpoints_the_cloud_holds(
    hass: HomeAssistant, loaded
):
    """Its measurements go away; what was configured for it does not."""
    assert hass.states.get("sensor.thermostat_studio_air_temperature_studio").state == (
        "unavailable"
    )
    assert hass.states.get("binary_sensor.thermostat_studio_heating_studio").state == (
        "unavailable"
    )
    assert hass.states.get("sensor.thermostat_studio_heating_mode_studio").state == (
        "comfort"
    )
    assert (
        hass.states.get("sensor.thermostat_studio_target_temperature_studio").state
        != "unavailable"
    )


async def test_no_entity_publishes_nan(hass: HomeAssistant, loaded):
    """`if self._state != NaN` was always true, so nan reached the state."""
    for state in hass.states.async_all():
        assert state.state.lower() != "nan"


async def test_a_device_that_never_reports_heating_says_so(hass: HomeAssistant, loaded):
    """The receiver reports heating_up as null, not as "0".

    Comparing null against "0" came out unequal, so the sensor read on while
    the thermostat beside it read off.
    """
    state = hass.states.get("binary_sensor.thermostat_woonkamer_heating_woonkamer")
    assert state is not None
    assert state.state == "unavailable"


async def test_devices_sharing_a_zone_are_named_by_the_device(
    hass: HomeAssistant, loaded
):
    """Not by whichever Home Assistant happened to register second.

    `nom_appareil` is a name the user sets in the Watts app, so it tells them
    which physical device an entity belongs to. "_2" never did.
    """
    ids = {state.entity_id for state in hass.states.async_all()}

    # The named device carries its name.
    assert any("verwarm_therm" in entity_id for entity_id in ids)
    # The receiver does not: "nouvel appareil" is the factory default and names
    # nothing, so it falls back to the zone label rather than putting French
    # for "new device" in front of the user.
    assert not any("nouvel_appareil" in entity_id for entity_id in ids)
    assert "sensor.thermostat_woonkamer_air_temperature_woonkamer" in ids
