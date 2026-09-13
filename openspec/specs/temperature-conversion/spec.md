# temperature-conversion Specification

## Purpose
TBD - created by archiving change fix-temperature-and-device-health. Update Purpose after archive.
## Requirements
### Requirement: API temperature values are deci-Fahrenheit

The Watts Vision API SHALL be treated as expressing every temperature field as an integer number of tenths of a degree Fahrenheit. This applies to `temperature_air`, `min_set_point`, `max_set_point`, and every `consigne_*` field.

The integration MUST NOT reinterpret this unit based on the user's locale, the `lang` request parameter, or the Home Assistant unit system. Decoding this wire format into the integration's internal unit SHALL happen at a single boundary. Conversion from there to the user's display unit is Home Assistant's responsibility, not the integration's.

#### Scenario: Frost protection setpoint is decoded

- **WHEN** the API reports `consigne_hg` as `446`
- **THEN** the integration treats it as 44.6 °F
- **AND** Home Assistant displays 7.0 °C on a metric system

#### Scenario: Comfort setpoint round-trips exactly

- **WHEN** the API reports `consigne_confort` as `689`
- **THEN** the reported target temperature is exactly 20.5 °C on a metric system
- **AND** no rounding error is introduced by the integration

### Requirement: Setpoint writes round to the nearest deci-Fahrenheit

When converting a requested temperature into the integer deci-Fahrenheit value sent to the API, the integration SHALL round to the nearest integer. It MUST NOT truncate.

#### Scenario: A value that truncates downward is rounded correctly

- **WHEN** a setpoint of 15.1 °C is requested
- **AND** the conversion to deci-Fahrenheit yields 591.8
- **THEN** the integration sends `592`
- **AND** it does not send `591`

#### Scenario: A half-degree setpoint is unaffected

- **WHEN** a setpoint of 20.5 °C is requested
- **THEN** the integration sends `689`

### Requirement: Offered resolution does not misrepresent the device

The integration MUST NOT declare a `target_temperature_step` that implies a precision the device does not have, and MUST NOT declare one so coarse that a user cannot reach a value the device can hold. Where a step is offered for usability, it SHALL be documented as a convenience rather than as the device's resolution.

The device stores setpoints in tenths of a degree Fahrenheit, confirmed by writing an off-grid value to an active setpoint on hardware and reading it back unchanged. No exact Celsius step exists, so the step offered is a usability choice: 0.1 °C, which keeps every value a user is likely to want reachable from the thermostat card.

#### Scenario: A requested value is stored as the nearest the device can hold

- **WHEN** a user requests a target temperature that is not exactly representable
- **THEN** the nearest value the device can store is written
- **AND** the value reported back is the one actually stored, not the one requested

#### Scenario: No false precision is claimed

- **WHEN** the integration declares a setpoint step
- **THEN** that step is not presented as the device's storage resolution

#### Scenario: A tenth-degree value is selectable and honoured

- **WHEN** a user selects 20.6 °C on the thermostat card
- **THEN** the nearest storable value is written
- **AND** the value reported back rounds to 20.6 °C for display

#### Scenario: An off-grid value already stored on the device is reported as-is

- **WHEN** the API reports a setpoint of `591`, which is 15.0556 °C
- **THEN** the integration reports that value without snapping it to 15.0 °C or 15.5 °C
- **AND** the reported value is identical across every entity that exposes it

### Requirement: Temperature entities report through native_value

Every temperature sensor SHALL expose its reading via `native_value` together with a `native_unit_of_measurement` that truthfully describes that value. Sensor entities MUST NOT override the `state` property, and MUST NOT convert between units themselves or inspect the Home Assistant unit system.

#### Scenario: Long-term statistics are recorded

- **WHEN** a temperature sensor declaring `state_class = MEASUREMENT` publishes a reading
- **THEN** the reading is available to the Home Assistant recorder's long-term statistics

#### Scenario: The declared unit matches the value

- **WHEN** a sensor publishes a temperature reading
- **THEN** its `native_unit_of_measurement` is the unit that value is actually expressed in
- **AND** Home Assistant performs any conversion to the user's display unit

#### Scenario: Entities do not branch on the user's unit system

- **WHEN** any entity produces a temperature value
- **THEN** it does so identically regardless of whether Home Assistant is configured as metric or imperial

### Requirement: Rounding is consistent across entities

All entities derived from the same underlying API field SHALL report the same value. The integration MUST NOT apply per-entity rounding that produces a resolution finer or coarser than the underlying data.

#### Scenario: Target temperature agrees between climate and sensor entities

- **WHEN** a device's active setpoint is read by both the climate entity and the target temperature sensor
- **THEN** both report the same temperature
- **AND** neither reports a value at 0.05 °C resolution

### Requirement: Temperature attributes retain a single type

Values stored in `extra_state_attributes` for the `consigne_*` fields SHALL always be floats expressed in degrees Fahrenheit. The integration MUST NOT store the deci-Fahrenheit string that is sent to the API.

#### Scenario: A mode change does not corrupt a stored setpoint

- **WHEN** the HVAC mode or preset is changed
- **AND** the integration updates its cached `consigne_*` attributes optimistically
- **THEN** those attributes still hold floats in degrees Fahrenheit
- **AND** a subsequent setpoint write derived from them sends a plausible temperature

### Requirement: Absent setpoints are reported as unknown

When a device is in a mode that has no target temperature, the target temperature SHALL be reported as unknown. The integration MUST NOT publish `nan` or any other placeholder number.

#### Scenario: A thermostat switched off has no target

- **WHEN** a device reports `gv_mode` of `1`, meaning off
- **THEN** the target temperature sensor state is unknown
- **AND** no numeric value is recorded to statistics

