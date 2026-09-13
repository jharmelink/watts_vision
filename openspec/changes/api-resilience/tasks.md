## 1. Exception types and the request helper

- [ ] 1.1 Add an exception hierarchy: a base error plus invalid credentials, rejected token, cloud unreachable, and API error response
- [ ] 1.2 Add an internal request helper that owns the timeout, the response check, and error raising, and route all five `requests.post` call sites through it
- [ ] 1.2a Catch every `requests` exception at that boundary and re-raise as an integration type, so no `requests` class can reach a caller — verified against the 2026-09-11 DNS outage traceback
- [ ] 1.3 Make the helper name the failing operation in every log entry and exception, replacing the hardcoded "Something went wrong fetching user data"
- [ ] 1.4 Add tests covering each failure class: timeout, connection error, HTTP 401, an error code in a well-formed response, and success

## 2. Authentication defects

- [ ] 2.1 Return the token from the retry path in `getLoginToken` so a successful retry reports success
- [ ] 2.2 Add a test proving `test_authentication` returns `True` when the first attempt fails and the retry succeeds — the config flow bug
- [ ] 2.3 Remove the undefined path that reaches `requests.post` with `payload` unbound; return the existing valid token when no new one is needed
- [ ] 2.4 Replace `raise None` with a real exception
- [ ] 2.5 Add a test asserting no path through token acquisition raises `NameError` or `TypeError`

## 3. Token lifecycle

- [ ] 3.1 Guard token acquisition with a `threading.Lock`, re-checking validity inside the lock so queued threads reuse the token just obtained
- [ ] 3.2 Confirm the lock covers acquisition only, so a slow request cannot block unrelated calls
- [ ] 3.3 Implement one-shot re-authenticate-and-retry in the request helper for a rejected token, with no unbounded recursion
- [ ] 3.4 Never retry after an explicit invalid-credentials response, to avoid repeated failed logins against the user's account
- [ ] 3.5 Add a test for concurrent expiry producing exactly one authentication request

## 4. Honest failure reporting

- [ ] 4.1 Make `reloadDevices` report failure when device loads fail, instead of returning `True` unconditionally
- [ ] 4.2 Convert the public methods to raise rather than return `None` or `False`
- [ ] 4.3 Audit and update every caller: `__init__.py` setup, `config_flow.py`, and every entity calling `getDevice`
- [ ] 4.4 Map exceptions at the setup boundary onto the appropriate Home Assistant config entry failure, so a wrong password and an unreachable cloud are reported differently
- [ ] 4.5 Confirm no unhandled exception can escape an entity update

## 5. Credential safety

- [ ] 5.1 Audit every log statement and exception message for credential or token content, including at debug level
- [ ] 5.2 Add a test asserting the password never appears in log output on a failed login

## 6. Cleanup

- [ ] 6.1 Remove the unused `firstTry` parameters from `loadSmartHomes`, `loadDevices`, `pushTemperature` and `getLastCommunication`
- [ ] 6.2 Remove the dead commented-out `setDevice` body and the unreachable `return None` after it
- [ ] 6.3 Remove the commented-out exception raises now that real ones exist

## 7. Open questions to settle

- [ ] 7.1 Record observed response times from the live installation and choose a timeout from evidence rather than the 30 second guess
- [ ] 7.2 Determine whether response code `8` is a success, and accept it if so
- [ ] 7.3 Agree explicitly with `fix-temperature-and-device-health` whether a failed refresh clears or keeps the cache, and record the decision in both designs

## 8. Release

- [ ] 8.1 Run the existing test suite and the pre-commit hooks
- [ ] 8.2 Verify on the live installation that setup succeeds normally and that a deliberately wrong password reports invalid credentials rather than a generic error
- [ ] 8.3 Bump the version in `manifest.json`
