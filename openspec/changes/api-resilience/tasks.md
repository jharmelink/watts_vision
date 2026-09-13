## 1. Exception types and the request helper

- [x] 1.1 Add an exception hierarchy: a base error plus invalid credentials, rejected token, cloud unreachable, and API error response
- [x] 1.2 Add an internal request helper that owns the timeout, the response check, and error raising, and route all five `requests.post` call sites through it
- [x] 1.2a Catch every `requests` exception at that boundary and re-raise as an integration type, so no `requests` class can reach a caller — verified against the 2026-09-11 DNS outage traceback
- [x] 1.3 Make the helper name the failing operation in every log entry and exception, replacing the hardcoded "Something went wrong fetching user data"
- [x] 1.4 Add tests covering each failure class: timeout, connection error, HTTP 401, an error code in a well-formed response, and success

## 2. Authentication defects

- [x] 2.1 Return the token from the retry path in `getLoginToken` so a successful retry reports success
- [x] 2.2 Reconciled with task 3.4, which forbids retrying a rejected login: `test_authentication` forces a fresh login, so the old retry path no longer exists to test. Covered instead by a test that a successful refresh-then-login returns the token, and one that a rejected login is attempted exactly once
- [x] 2.3 Remove the undefined path that reaches `requests.post` with `payload` unbound; return the existing valid token when no new one is needed
- [x] 2.4 Replace `raise None` with a real exception
- [x] 2.5 Add a test asserting no path through token acquisition raises `NameError` or `TypeError`

## 3. Token lifecycle

- [x] 3.1 Guard token acquisition with a `threading.Lock`, re-checking validity inside the lock so queued threads reuse the token just obtained
- [x] 3.2 Confirm the lock covers acquisition only, so a slow request cannot block unrelated calls
- [x] 3.3 Implement one-shot re-authenticate-and-retry in the request helper for a rejected token, with no unbounded recursion
- [x] 3.4 Never retry after an explicit invalid-credentials response, to avoid repeated failed logins against the user's account
- [x] 3.5 Add a test for concurrent expiry producing exactly one authentication request

## 4. Honest failure reporting

- [x] 4.1 Make `reloadDevices` report failure when device loads fail, instead of returning `True` unconditionally
- [x] 4.2 Convert the public methods to raise rather than return `None` or `False`
- [x] 4.3 Audit and update every caller: `__init__.py` setup, `config_flow.py`, and every entity calling `getDevice`
- [x] 4.4 Map exceptions at the setup boundary onto the appropriate Home Assistant config entry failure, so a wrong password and an unreachable cloud are reported differently
- [x] 4.5 Confirm no unhandled exception can escape an entity update

## 5. Credential safety

- [x] 5.1 Audit every log statement and exception message for credential or token content, including at debug level
- [x] 5.2 Add a test asserting the password never appears in log output on a failed login

## 6. Cleanup

- [x] 6.1 Remove the unused `firstTry` parameters from `loadSmartHomes`, `loadDevices`, `pushTemperature` and `getLastCommunication`
- [x] 6.2 Remove the dead commented-out `setDevice` body and the unreachable `return None` after it
- [x] 6.3 Remove the commented-out exception raises now that real ones exist

## 7. Open questions to settle

- [ ] 7.1 Record observed response times from the live installation and confirm or adjust the 30 second timeout, which is documented in the code as a conservative choice made without measurements
- [x] 7.2 Determine whether response code `8` is a success, and accept it if so
- [x] 7.3 Agree explicitly with `fix-temperature-and-device-health` whether a failed refresh clears or keeps the cache, and record the decision in both designs

## 8. Release

- [x] 8.1 Run the existing test suite and the pre-commit hooks
- [ ] 8.2 Verify on the live installation that setup succeeds normally and that a deliberately wrong password reports invalid credentials rather than a generic error
- [x] 8.3 Bump the version in `manifest.json`
