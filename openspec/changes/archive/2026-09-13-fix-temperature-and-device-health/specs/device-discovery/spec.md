## ADDED Requirements

### Requirement: Entities are created from the fields a device reports

The integration SHALL decide which entities to create for a device based on whether that device supplies values those entities can use. A field that is present but null MUST be treated the same as a field that is absent; a key-presence test is not sufficient. A device that supplies no usable setpoint MUST NOT be given a climate entity or a target temperature entity, and its remaining entities MUST still be created.

#### Scenario: A device without setpoints still yields its usable entities

- **WHEN** a device reports usable `temperature_air`, `gv_mode`, `heating_up` and `error_code` but no usable setpoint
- **THEN** its air temperature, heating mode, heating state and error entities are created
- **AND** no climate entity and no target temperature entity are created for it
- **AND** no entity creation raises

#### Scenario: A null field is treated as absent

- **WHEN** a device reports a setpoint key whose value is null
- **THEN** that setpoint is treated as unavailable
- **AND** no entity is created that would depend on converting it

#### Scenario: A full thermostat yields the full entity set

- **WHEN** a device reports usable setpoint values
- **THEN** a climate entity and a target temperature entity are created alongside its other entities

### Requirement: Partial device data degrades without silent entity loss

A device whose data is incomplete or unexpected SHALL NOT cause entities to disappear without explanation. Where an entity cannot be created, the reason MUST be discoverable by the user.

#### Scenario: An unsupported device is reported rather than dropped

- **WHEN** the integration encounters a device it cannot fully model
- **THEN** the entities it can support are created
- **AND** the unsupported aspect is surfaced to the user rather than only appearing as a missing entity

### Requirement: Device model is not hardcoded

The integration SHALL derive each device's reported model from the API data rather than assigning a fixed model string to every device.

#### Scenario: A non-thermostat device is not labelled as a thermostat

- **WHEN** a device that is not a BT-D03-RF thermostat is registered
- **THEN** its device registry entry does not claim to be a BT-D03-RF

#### Scenario: An unknown model is left unset

- **WHEN** the API provides no model information for a device
- **THEN** the model is left unset rather than guessed

### Requirement: Entity naming distinguishes devices sharing a zone

When more than one device exists in the same zone, entity names SHALL distinguish them. The integration MUST NOT rely on Home Assistant's automatic numeric suffixing to disambiguate devices.

#### Scenario: Two devices in one zone are distinguishable

- **WHEN** a zone contains two devices
- **THEN** each device's entities are named such that a user can tell which physical device they belong to
- **AND** the names do not depend on the order devices are returned by the API
