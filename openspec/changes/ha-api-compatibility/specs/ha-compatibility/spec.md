## ADDED Requirements

### Requirement: User-facing flows survive Home Assistant upgrades

The config flow and options flow SHALL remain functional on supported Home Assistant versions. A user MUST be able to open the integration's options and change stored credentials without encountering an error.

#### Scenario: Options can be opened

- **WHEN** a user opens the integration's configuration options
- **THEN** the options form is presented
- **AND** no exception is raised

#### Scenario: Credentials can be changed

- **WHEN** a user submits new credentials through the options flow
- **AND** those credentials are valid
- **THEN** the config entry is updated and reloaded

#### Scenario: The flow does not assign platform-owned state

- **WHEN** the options flow is constructed
- **THEN** it does not assign to attributes that Home Assistant provides as read-only properties

### Requirement: No interface is used past its removal

The integration SHALL NOT depend on a Home Assistant interface after the version in which that interface stops working. Where the platform announces a removal, the integration MUST migrate before that release.

#### Scenario: A dated removal is migrated in time

- **WHEN** Home Assistant announces that an interface the integration uses will stop working in a future release
- **THEN** the integration migrates off that interface before that release

#### Scenario: Vestigial platform API is removed

- **WHEN** an interface the integration references has been superseded and its value now lives elsewhere
- **THEN** the reference is removed rather than left in place

### Requirement: Device relationships survive the migration

The central unit SHALL remain the parent device of the thermostats and other sub-devices it reports, however that relationship is expressed to the device registry.

#### Scenario: Sub-devices remain grouped under the central unit

- **WHEN** devices are registered
- **THEN** each sub-device is shown as connected via the central unit
- **AND** this holds without using an interface scheduled for removal

#### Scenario: Existing devices are not duplicated

- **WHEN** the integration is upgraded on an installation that already has devices registered
- **THEN** the existing devices are reused
- **AND** no duplicate device entries are created

### Requirement: The test suite runs automatically

The integration's tests SHALL run in continuous integration on every push and pull request, against a supported Home Assistant version. Validation that inspects only metadata is not sufficient.

#### Scenario: Tests run on a pull request

- **WHEN** a pull request is opened
- **THEN** the test suite is executed
- **AND** a failing test fails the check

#### Scenario: The integration is actually loaded

- **WHEN** the test suite runs
- **THEN** at least one test sets the integration up through Home Assistant
- **AND** a failure to set up is reported as a test failure

### Requirement: Deprecation warnings fail the build

Home Assistant deprecation warnings originating from this integration SHALL cause the test suite to fail. A dated removal MUST be detected when the platform announces it, not when it takes effect.

#### Scenario: A newly announced deprecation is caught

- **WHEN** a Home Assistant release begins warning about an interface the integration uses
- **AND** the test suite runs against that release
- **THEN** the suite fails and identifies the warning

#### Scenario: Warnings from other components do not fail the build

- **WHEN** a deprecation warning originates from Home Assistant or another integration
- **THEN** it does not fail this integration's test suite
