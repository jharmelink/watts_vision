## ADDED Requirements

### Requirement: No request blocks indefinitely

Every outbound HTTP request SHALL specify a timeout. A request that exceeds it MUST fail as a connectivity error rather than continuing to wait.

#### Scenario: A hung connection fails within a bounded time

- **WHEN** the cloud accepts a connection but never responds
- **THEN** the call fails within the configured timeout
- **AND** the executor thread running it is released

#### Scenario: Every call site is covered

- **WHEN** any request is made to the Watts cloud
- **THEN** a timeout applies to it
- **AND** no call path exists that can wait forever

### Requirement: Failures are reported as typed exceptions

The API client SHALL raise a distinct exception type for each class of failure it can encounter, so that callers can act differently on each. It MUST NOT signal failure by returning `None`, `False`, or by returning normally.

The distinguishable classes are: invalid credentials, a token that the cloud rejected, an inability to reach the cloud, and an API response that reports an application-level error.

#### Scenario: Invalid credentials are distinguishable from an unreachable cloud

- **WHEN** authentication fails because the credentials are wrong
- **THEN** an authentication error is raised
- **AND** it is a different type from the error raised when the cloud cannot be reached

#### Scenario: A caller can tell that data is unavailable

- **WHEN** a device data request fails for any reason
- **THEN** the caller receives an exception rather than `None`
- **AND** no caller can mistake a failure for an empty result

#### Scenario: An API-level error response is surfaced

- **WHEN** the cloud returns a well-formed response whose code indicates an error
- **THEN** an API error is raised carrying the code and message the cloud supplied

### Requirement: A successful authentication returns the token

`getLoginToken` SHALL return the acquired token on every path that acquires one, including when the token was obtained by a retry after an initial failure.

#### Scenario: A retry that succeeds reports success

- **WHEN** the first token request fails
- **AND** the retry obtains a valid token
- **THEN** the call returns that token
- **AND** a caller testing the credentials concludes they are valid

#### Scenario: Valid credentials are never reported as invalid

- **WHEN** a user enters correct credentials during setup
- **AND** a transient failure occurs on the first attempt
- **THEN** setup succeeds
- **AND** the user is not told their credentials are invalid

### Requirement: Token acquisition has no undefined path

Every path through token acquisition SHALL either issue a well-formed request, return an existing valid token, or raise. There MUST NOT be a path that proceeds to send a request without having built one.

#### Scenario: A call when no token is needed does not fail

- **WHEN** token acquisition is invoked while the current token is still valid
- **THEN** the existing valid token is returned
- **AND** no request is sent
- **AND** no error is raised

### Requirement: A rejected token triggers exactly one re-authentication

When the cloud rejects a request because the token is no longer accepted, the client SHALL attempt re-authentication once and retry the original request once. It MUST NOT retry indefinitely, and MUST NOT recurse without bound.

#### Scenario: A data call recovers from a rejected token

- **WHEN** a device data request is rejected as unauthorised
- **AND** re-authentication succeeds
- **THEN** the original request is retried once and its result returned

#### Scenario: Repeated rejection gives up

- **WHEN** a request is rejected as unauthorised
- **AND** the retry after re-authentication is also rejected
- **THEN** an authentication error is raised
- **AND** no further attempt is made

### Requirement: Partial data loads are reported as failure

A refresh that fails to load data for any smart home SHALL report failure. It MUST NOT report success because it completed without raising.

#### Scenario: A total failure is not reported as success

- **WHEN** a refresh attempts to load devices for every smart home and each load fails
- **THEN** the refresh reports failure
- **AND** the previously cached data is not presented as freshly updated

### Requirement: Concurrent callers do not authenticate twice

Token acquisition SHALL be safe to call from multiple threads at once. When several callers find the token expired simultaneously, exactly one authentication request MUST be made and all callers MUST receive the resulting token.

#### Scenario: Simultaneous expiry produces one login

- **WHEN** several entity updates and the refresh timer all find the token expired at the same moment
- **THEN** exactly one authentication request is sent
- **AND** every caller proceeds with the same valid token

### Requirement: Errors identify the operation that failed

Every logged failure and every raised exception SHALL identify which operation failed. A message MUST NOT describe an operation other than the one that actually failed.

#### Scenario: A failed setpoint push is not reported as a user data failure

- **WHEN** pushing a temperature setpoint fails
- **THEN** the log entry identifies the setpoint push as the failing operation

### Requirement: Credentials never appear in logs or exceptions

The username, password, access token and refresh token SHALL never be written to logs or included in exception messages, at any log level.

#### Scenario: A failed login does not log the password

- **WHEN** authentication fails
- **THEN** the log records that authentication failed
- **AND** contains neither the password nor the username

#### Scenario: Debug logging stays safe

- **WHEN** debug logging is enabled
- **THEN** no credential or token value is written to the log
