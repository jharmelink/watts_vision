## ADDED Requirements

### Requirement: An unrecognised error code never destroys an entity

The integration SHALL tolerate any `error_code` value the API returns, including values it does not recognise. An unrecognised code MUST NOT raise during entity update, and MUST NOT prevent an entity from being created or cause it to be removed.

#### Scenario: A device reports an unmapped error code

- **WHEN** a device reports an `error_code` that the integration has no label for
- **THEN** the error entity is still created
- **AND** it reports that the device has an unrecognised fault rather than raising
- **AND** the raw code is available to the user for diagnosis

#### Scenario: Entity creation survives a failing first update

- **WHEN** a device's first update raises an unexpected error
- **THEN** the remaining devices' entities are still created
- **AND** the failure is logged in a form the user can act on

### Requirement: Fault meaning is never guessed

The integration SHALL derive device health structurally from whether an error code is zero, not from an enumeration of codes. It MUST NOT attribute a specific fault meaning to a code for which there is no direct evidence.

#### Scenario: A nonzero code is treated as a fault without being named

- **WHEN** a device reports a nonzero `error_code` whose meaning is unknown
- **THEN** the device is treated as faulted
- **AND** the reported state describes it as an unrecognised fault
- **AND** the raw code is exposed so the user can report it

#### Scenario: A code with evidence behind it is labelled

- **WHEN** a device reports an error code the integration has confirmed evidence for
- **THEN** the reported state uses the specific label for that fault

#### Scenario: Zero means healthy

- **WHEN** a device reports an `error_code` of zero
- **THEN** the device is treated as healthy
- **AND** its measurement entities remain available

### Requirement: Battery state is exposed as a battery entity

The integration SHALL expose each battery-powered device's battery condition using the Home Assistant battery device class, so that standard low-battery handling in the user interface and in automations applies.

#### Scenario: A healthy device reports a good battery

- **WHEN** a device reports no fault
- **THEN** its battery entity reports a normal state

#### Scenario: A failed battery is surfaced

- **WHEN** a device reports the error code that indicates battery failure
- **THEN** its battery entity reports a low or failed battery state
- **AND** the condition is visible without the user inspecting logs

### Requirement: A device that cannot report goes unavailable

Every entity SHALL implement the `available` property and derive it from the state of the underlying device. When a device cannot produce a valid reading, its affected entities MUST report as unavailable rather than publishing a value.

#### Scenario: A dead battery makes readings unavailable

- **WHEN** a device's battery has failed and it can no longer report a temperature
- **THEN** its temperature entities report as unavailable
- **AND** no numeric temperature is recorded to long-term statistics for the duration of the fault

#### Scenario: Availability recovers

- **WHEN** a previously faulted device begins reporting valid data again
- **THEN** its entities return to available
- **AND** they resume publishing readings

#### Scenario: A failed API refresh does not publish stale data as fresh

- **WHEN** the periodic refresh fails and no device data is available
- **THEN** entities depending on that data report as unavailable

### Requirement: Sentinel readings are never published as measurements

The integration SHALL NOT publish an out-of-band sentinel value as if it were a measurement. A temperature reading that falls outside the plausible operating range of a room thermostat MUST be treated as absent.

#### Scenario: The dead-battery sentinel is suppressed

- **WHEN** a device with a failed battery reports a `temperature_air` sentinel that converts to approximately 100 °C
- **THEN** the air temperature entity reports as unavailable
- **AND** it does not publish 100.2 °C
- **AND** nothing is written to long-term statistics for that reading

#### Scenario: A plausible reading is published normally

- **WHEN** a device reports an air temperature within the plausible range
- **THEN** the reading is published unchanged
