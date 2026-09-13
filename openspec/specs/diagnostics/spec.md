# diagnostics Specification

## Purpose
TBD - created by archiving change fix-temperature-and-device-health. Update Purpose after archive.
## Requirements
### Requirement: Credentials and account identifiers are always redacted

Diagnostics output SHALL never contain credentials, tokens, or identifiers that could be used to access the user's account. Redaction MUST be applied by an allow-list-free mechanism that fails safe: a newly added field that has not been considered MUST NOT leak simply because nobody remembered to redact it.

Diagnostics are routinely pasted into public issue trackers. This requirement takes precedence over the usefulness of any individual field.

#### Scenario: Credentials never appear

- **WHEN** a user downloads diagnostics
- **THEN** the output contains no username, password, access token, or refresh token
- **AND** this holds regardless of which parts of the integration's state are included

#### Scenario: Account and hardware identifiers are masked

- **WHEN** diagnostics include smart home or device records
- **THEN** MAC addresses, smart home identifiers, and device identifiers are redacted
- **AND** values are replaced with a consistent placeholder rather than removed, so structure remains readable

#### Scenario: Redaction survives an unexpected API field

- **WHEN** the API returns a field the integration has never seen
- **THEN** that field does not cause a credential or identifier to be emitted unredacted

### Requirement: Raw API data is included verbatim

Diagnostics SHALL include the API's device and zone payloads as received, after redaction and without any decoding, rounding, renaming, or filtering. Fields the integration does not use MUST be included.

The purpose is to make an undocumented API observable. Data the integration already understands is the least valuable part of the output.

#### Scenario: Unused fields are preserved

- **WHEN** the API returns fields the integration ignores
- **THEN** those fields appear in the diagnostics output

#### Scenario: Raw values are not pre-decoded

- **WHEN** a temperature field is included
- **THEN** it appears as the raw API value, not as a converted temperature

### Requirement: The integration's interpretation accompanies the raw data

Alongside the raw payloads, diagnostics SHALL include what the integration made of them: the decoded values, the entities it created for each device, and any entity it declined to create together with the reason.

This lets a reader see exactly where the integration's understanding and the API's behaviour diverge, which is the question that matters when the API cannot be consulted.

#### Scenario: A skipped entity is explained

- **WHEN** a device did not receive a climate entity because it reports no setpoint fields
- **THEN** diagnostics record that the entity was skipped and why

#### Scenario: Decoded and raw values sit side by side

- **WHEN** a device reports a setpoint
- **THEN** diagnostics show both the raw API value and the temperature the integration derived from it

### Requirement: Unrecognised values are surfaced, not swallowed

When the integration encounters a value it does not recognise — an unknown error code, an unknown operating mode, or a device missing fields it expected — it SHALL record this in diagnostics and log it once. Repeated occurrences of the same unrecognised value MUST NOT repeat the log entry.

#### Scenario: An unknown error code is reported once

- **WHEN** a device reports an error code the integration has no label for
- **THEN** the code is logged once with the device it came from
- **AND** the same code on the same device does not log again on subsequent refreshes
- **AND** the code appears in diagnostics

#### Scenario: An unknown operating mode is reported

- **WHEN** a device reports a `gv_mode` outside the known set
- **THEN** the mode is logged once and appears in diagnostics
- **AND** the device's entities continue to function

### Requirement: Diagnostics are available per device

Diagnostics SHALL be downloadable for an individual device as well as for the whole config entry, so a single unexpected device can be inspected without exporting the entire installation.

#### Scenario: A single device is exported

- **WHEN** a user downloads diagnostics from a device page
- **THEN** the output covers that device only
- **AND** the same redaction rules apply

