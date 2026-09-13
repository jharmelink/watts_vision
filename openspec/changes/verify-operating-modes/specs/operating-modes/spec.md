## ADDED Requirements

### Requirement: Every mode mapping records its provenance

The integration SHALL record, for every operating mode it claims to understand, what the mode means and what evidence supports that claim. A mapping confirmed on hardware MUST be distinguishable from one inherited without verification.

#### Scenario: A confirmed mapping is marked as confirmed

- **WHEN** a mode's meaning has been observed directly on a device
- **THEN** the mapping records that it was confirmed by observation

#### Scenario: An unverified mapping is not presented as fact

- **WHEN** a mode's meaning has been inherited or inferred but never observed
- **THEN** the mapping records it as unverified
- **AND** a reader can tell which entries are which without consulting history

### Requirement: Each mode reads its own setpoint field

The target temperature reported for a device SHALL come from the setpoint field belonging to that device's active mode. The integration MUST NOT report a setpoint from a different mode.

#### Scenario: Comfort reports the comfort setpoint

- **WHEN** a device is in comfort mode
- **THEN** the target temperature is read from the comfort setpoint field

#### Scenario: Eco reports the eco setpoint

- **WHEN** a device is in eco mode
- **THEN** the target temperature is read from the eco setpoint field
- **AND** the comfort setpoint is not reported as the target

#### Scenario: A mode with no setpoint reports none

- **WHEN** a device is in a mode that has no target temperature
- **THEN** no target temperature is reported

### Requirement: Writing a setpoint affects only the active mode

Setting a target temperature SHALL update the setpoint belonging to the active mode, both at the device and in any local cache. It MUST NOT alter the setpoint of a mode that is not active.

#### Scenario: Adjusting the target while in eco leaves comfort alone

- **WHEN** a device is in eco mode
- **AND** the user sets a new target temperature
- **THEN** the eco setpoint is updated
- **AND** the comfort setpoint is unchanged, in the cache as well as at the device

#### Scenario: Switching modes preserves other setpoints

- **WHEN** a device is switched from one mode to another
- **THEN** the setpoints belonging to the modes not selected are unchanged

### Requirement: A requested value is either used or refused

When the user supplies a temperature, the integration SHALL either send that value to the device or decline the request with a reason. It MUST NOT accept a value, substitute a different one, and report success.

#### Scenario: Frost protection does not silently substitute

- **WHEN** the user sets a frost protection temperature
- **THEN** either that temperature is sent to the device
- **OR** the request is refused because the device does not permit it
- **AND** in neither case is a different temperature sent while reporting success

#### Scenario: A mode taking no setpoint does not compute one

- **WHEN** a mode is selected that accepts no target temperature
- **THEN** no setpoint is computed for it
- **AND** no value is silently discarded

### Requirement: Every supported mode has explicit write handling

Each mode the integration offers SHALL have defined behaviour when written. A mode MUST NOT reach the request layer and fall through to an empty payload by omission.

#### Scenario: Selecting program mode behaves deliberately

- **WHEN** the user selects program mode
- **THEN** the request sent to the device is the one program mode is defined to require
- **AND** the behaviour is the result of an explicit decision rather than an unmatched branch

#### Scenario: An offered preset is always writable

- **WHEN** a preset appears in the entity's list of available presets
- **THEN** selecting it produces a defined request

### Requirement: Boost duration is controllable

The user SHALL be able to choose how long a boost lasts, rather than receiving a fixed duration.

#### Scenario: A boost runs for the requested duration

- **WHEN** the user starts a boost with a given duration
- **THEN** that duration is sent to the device

#### Scenario: A default applies when no duration is given

- **WHEN** a boost is started without a duration
- **THEN** a documented default is used

### Requirement: A boost can be stopped

The user SHALL be able to end a boost before it expires and return the device to the mode that preceded it, without having to select another preset and thereby rewrite that preset's setpoint.

#### Scenario: Stopping a boost restores the previous mode

- **WHEN** a device is boosting
- **AND** the user stops the boost
- **THEN** the device returns to the mode that was active before the boost
- **AND** no setpoint belonging to that mode is modified

#### Scenario: Remaining boost time is visible

- **WHEN** a device is boosting
- **THEN** the time remaining is available to the user

### Requirement: Changing a mode mapping is a breaking change

Altering what an existing mode maps to SHALL be treated as a breaking change. The integration MUST NOT silently redefine a preset that users' automations may reference.

#### Scenario: A corrected mapping is announced

- **WHEN** evidence shows an existing mode mapping is wrong
- **THEN** correcting it is released as a breaking change with the correction described
- **AND** users are told which presets changed meaning

#### Scenario: An unverified mapping is not changed speculatively

- **WHEN** a third-party implementation disagrees about a mode's meaning
- **AND** no direct observation resolves the disagreement
- **THEN** the existing mapping is retained
- **AND** the disagreement is recorded rather than acted upon
