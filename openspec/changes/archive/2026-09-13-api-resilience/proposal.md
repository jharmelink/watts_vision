## Why

`watts_api.py` cannot report failure. Every call that goes wrong returns `None`, `False`, or nothing at all, so callers cannot tell a wrong password from a dropped connection from a cloud outage — and entities downstream index into `None` and raise.

Three defects in the authentication path are live bugs rather than architectural debt, and one of them is user-facing: a transient failure during setup makes the config flow report **"invalid credentials"** to someone whose credentials are correct.

No request has a timeout. A hung connection pins a Home Assistant executor thread indefinitely, and there are five such calls.

This matters more here than in an integration with an upstream. The API is undocumented and unreachable, the vendor has moved to Vision+, and nobody will fix a failure mode at source. The integration's own error handling is the only thing standing between a cloud hiccup and a user with no idea what broke.

## What Changes

**Authentication defects**

- **`raise None` raises `TypeError`, not the intended error.** `getLoginToken` ends its failure path with `raise None`, which Python rejects as "exceptions must derive from BaseException". The caller sees a confusing type error instead of an authentication failure.
- **A successful retry still reports failure.** The retry branch calls `self.getLoginToken(forcelogin=True, firstTry=False)` without `return`, so the outer call falls through and returns `None` even when the retry obtained a valid token. `test_authentication` then evaluates `token is not None` as `False`, and the config flow tells a user with valid credentials that their credentials are invalid.
- **An unreachable-token branch leaves `payload` unbound.** When neither the login nor the refresh condition matches, `getLoginToken` logs "Getting token called unneeded" and falls through to `requests.post(data=payload)` with `payload` never assigned, raising `NameError`.

**Failure reporting**

- Replace `None` and `False` returns with typed exceptions so callers can distinguish authentication failure, connectivity failure, and an API-level error response.
- Catch transport failures and re-raise them as the integration's own types. A DNS outage on 2026-09-11 sent raw `requests.exceptions.ConnectionError` straight through `central_unit.py` entity updates and the `__init__.py` refresh timer, unhandled. No entity went unavailable; they logged and kept reporting stale values.
- `check_response` logs "Something went wrong fetching user data" for every failing call regardless of which operation failed, which misleads anyone reading logs for a failed setpoint push.
- `reloadDevices` returns `True` unconditionally, so `loadData` reports success even when every device load returned `None`.

**Robustness**

- Add a timeout to all five `requests.post` calls.
- Wire up, or remove, the vestigial `firstTry` parameters. They appear on `loadSmartHomes`, `loadDevices`, `pushTemperature` and `getLastCommunication` and are never referenced in any of those bodies — scaffolding for a retry-on-401 that was never implemented. Data calls currently do not re-authenticate when the cloud rejects a token.
- Guard concurrent token acquisition. Entity updates and the refresh timer both run in executor threads and can call `getLoginToken` simultaneously with no lock.
- Ensure credentials and tokens never reach logs or exception messages.

**Incidental**

- Remove the dead commented-out `setDevice` body and the unreachable `return None` that follows it.

## Capabilities

### New Capabilities

- `api-resilience`: how the API client reports failure to its callers, the guarantees it makes about not blocking, and the rules for authentication, retry, and credential safety.

### Modified Capabilities

None. The specs in `fix-temperature-and-device-health` describe entity behaviour and do not state requirements about the API client.

## Impact

**Code**

- `custom_components/watts_vision/watts_api.py` — the whole module
- `custom_components/watts_vision/__init__.py` — setup must act on typed failures rather than a bare `Exception` catch
- `custom_components/watts_vision/config_flow.py` — distinguish invalid credentials from an unreachable cloud
- New exception types, either in `watts_api.py` or a small `exceptions.py`

**Relationship to `fix-temperature-and-device-health`**

Independent; the two changes touch almost disjoint files. They can land in either order, but this one first makes the other simpler: its requirement that entities go `unavailable` when a refresh fails currently has to be implemented by checking for `None`, because the API layer has no way to say a refresh failed. Landing this first replaces that with a real signal.

This change is also lower risk — no entity, unit, or statistics behaviour changes — so it is a reasonable thing to ship on its own.

**User-visible**

- A wrong password and an unreachable cloud produce different, accurate messages during setup.
- Valid credentials are no longer rejected after a transient failure.
- A hung request fails after a bounded wait instead of consuming an executor thread forever.

**Not changed**

- No `DataUpdateCoordinator` migration, no multi config entry support, no change to the request payloads or endpoints. The wire format is left exactly as it is; this change is about what happens when it fails.
