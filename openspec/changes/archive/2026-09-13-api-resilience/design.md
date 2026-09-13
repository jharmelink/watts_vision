## Context

`WattsApi` is a synchronous `requests` client run through `hass.async_add_executor_job`. It holds the username and password so it can re-authenticate, caches an access token and refresh token, and keeps all device state in a single mutable `_smartHomeData` dict that entities read directly.

Its error handling has one shape throughout: detect a problem, log it, return a falsy value. `check_response` returns `False`; `loadSmartHomes`, `loadDevices` and `getLastCommunication` return `None`; `pushTemperature` returns `False`; `reloadDevices` returns `True` regardless. Nothing raises anything a caller can act on.

There is a second failure mode, and it is the opposite of the first. When the transport itself fails, nothing is swallowed — a raw `requests` exception escapes the client entirely. A DNS outage on the reference installation on 2026-09-11 produced exactly this:

```
  requests.exceptions.ConnectionError  propagated unhandled out of

    central_unit.py:51   async_update          →  getLastCommunication
    __init__.py:38       refresh_devices       →  reloadDevices → loadDevices
                                               →  _refresh_token_if_expired
                                               →  getLoginToken
```

`check_response` was never reached; `requests` raised before any response existed. So the client swallows API-level errors into `None` and leaks transport errors as third-party exception types, and a caller has to handle both. During that outage no entity went unavailable — they logged and kept reporting stale values, which is precisely the behaviour `fix-temperature-and-device-health` requires fixing and cannot fix alone.

The consequences are visible at both ends of the integration. At setup, `async_setup_entry` wraps the login in a bare `except Exception` and returns `False`, so every failure looks the same to Home Assistant. At the entity end, a failed refresh leaves `getDevice` returning `None` and entities immediately index into it.

Three defects sit in `getLoginToken` specifically, confirmed present at the time of writing:

```
  ~line 57   else: _LOGGER.debug("Getting token called unneeded.")
             falls through to requests.post(data=payload) with payload unbound
                                                            → NameError

  ~line 81   self.getLoginToken(forcelogin=True, firstTry=False)
             no `return`; the outer call falls off the end and returns None
             even though the retry succeeded

  ~line 88   raise None
             → TypeError: exceptions must derive from BaseException
```

The middle one is user-facing. `test_authentication` does `token = self.getLoginToken(True); return token is not None`, so a transient failure followed by a successful retry evaluates to `False`, and `config_flow` reports `invalid_auth` to a user whose credentials are correct.

Four methods carry a `firstTry` parameter that no body references — `loadSmartHomes`, `loadDevices`, `pushTemperature`, `getLastCommunication`. Only `getLoginToken` uses its own. These are vestigial scaffolding for a retry-on-401 that was never implemented, which is why a data call whose token the cloud rejects simply logs "Unauthorized" and returns `None`.

## Goals / Non-Goals

**Goals:**

- Callers can distinguish why something failed and act accordingly.
- No request can block an executor thread indefinitely.
- Correct credentials are never reported as incorrect.
- Token handling has no undefined path and no unbounded recursion.

**Non-Goals:**

- Changing the wire format. Endpoints, payload keys, `peremption` values and the `lang` parameter stay exactly as they are. This change is about what happens when a request fails, not what the request says.
- Migrating to an async HTTP client. `requests` in an executor is adequate; swapping to `aiohttp` belongs with the coordinator migration.
- `DataUpdateCoordinator`, multi config entry support, or anything about entity behaviour.
- Caching or retry policy beyond a single re-authentication attempt. Sophisticated backoff is unwarranted for a 120-second poll.

## Decisions

### Raise typed exceptions rather than returning sentinels

The existing code contains commented-out `APIException`, `UnauthorizedException` and `UnHandledStatuException` raises, so the original author reached for exactly this and then backed it out — presumably because nothing was ready to catch them.

**Chosen:** a small exception hierarchy with one base class, and distinct subclasses for invalid credentials, a rejected token, an unreachable cloud, and an API-level error response. Callers that currently test for `None` become callers that catch.

This must cover transport failures as well as API-level ones. Every `requests` exception — connection, DNS, timeout, read — is caught at the request boundary and re-raised as the integration's own type, so no caller ever sees a `requests` class. Today a `ConnectionError` reaching an entity update is a third-party exception nobody declared, which is why it escapes.

Four classes, not more. The distinctions that matter are the ones a caller acts on differently:

```
  invalid credentials   → config flow shows "invalid auth"; do not retry
  rejected token        → re-authenticate once, retry once
  cannot reach cloud    → entities go unavailable; retry next poll
  API error response    → surface the cloud's own code and message
```

Mapping these onto Home Assistant's `ConfigEntryAuthFailed` and `ConfigEntryNotReady` at the setup boundary is left to the implementation; the requirement is that the distinction survives long enough to be made.

### Retry once, at the request layer, not per method

The `firstTry` parameters attempted per-method retry and were never finished. Threading a retry flag through every public method is the wrong shape — it is four places to get wrong, and the flag leaks into the signature of everything.

**Chosen:** a single internal request helper owns the timeout, the response check, and the one-shot re-authenticate-and-retry. Public methods call it and are freed of both concerns. The `firstTry` parameters are removed rather than wired up.

This also fixes the misleading log message: `check_response` currently hardcodes "Something went wrong fetching user data" for every operation, because it is a static method with no idea who called it. A request helper knows.

### Guard token acquisition with a lock

Entity updates and the refresh timer both reach the client through executor threads, and nothing serialises them. Several threads can find the token expired within the same instant and each start a login.

**Chosen:** a `threading.Lock` around acquisition, with a re-check inside the lock so that threads queued behind the winner use the token it obtained rather than requesting another. A `threading` primitive rather than an asyncio one, because the client runs in executor threads and knows nothing about the event loop.

### A failed refresh keeps the cache; availability carries the signal

Agreed with `fix-temperature-and-device-health`, which approaches the same
question from the entity side.

**Chosen:** a refresh that fails leaves the cached device data exactly as it
was, and says so by making the affected entities unavailable. Clearing the
cache would empty every entity during a brief outage and lose the last known
state for no gain, while silently keeping it and reporting it as current is the
behaviour this change exists to end.

The client's part is to raise rather than report success, so a caller can never
mistake stale data for a completed refresh. Deciding what a user sees is the
entity layer's part. This change implements the client half and the minimum
entity handling needed to stop an exception escaping an update; the fuller
availability rules belong to the other change.

### Keep the client synchronous

Making the client async would remove the executor hop and make the locking simpler. It would also touch every call site and every entity, and it is a prerequisite for nothing in this change.

**Chosen:** stay synchronous. Revisit with the coordinator migration, where the call sites are being rewritten anyway.

## Risks / Trade-offs

**Raising where callers previously received `None` will surface failures that were silently swallowed.** → That is the point, but it means users may start seeing setup failures and unavailable entities where previously they saw stale or wrong data. Every new raise needs a caller that handles it; an unhandled exception in an entity update is a worse failure than the one being fixed. Audit every call site in the same change rather than leaving some returning sentinels.

**A timeout that is too short will cause spurious failures on a slow cloud.** → The cloud is known to take roughly 13 seconds to apply a command, though that is the device round trip rather than the HTTP response. Pick a timeout generously above observed response times, and treat a timeout as a retryable connectivity error rather than a permanent one.

**Removing the `firstTry` parameters changes public method signatures.** → They are unused and this is a custom component with no external API consumers, but anything calling `WattsApi` directly would break. Nothing in the repository does.

**The lock could serialise more than intended.** → It must cover only token acquisition, not the requests that use the token, or every entity update will queue behind every other. Scope it narrowly and confirm a slow request does not block unrelated calls.

**A user could be logged out by a wrong-password retry loop.** → Some providers lock accounts after repeated failed logins. Capping re-authentication at one attempt per rejected request, and never retrying an explicit invalid-credentials response, keeps this bounded.

## Migration Plan

1. Introduce the exception types and the internal request helper with timeout and response checking, leaving existing public methods returning what they return today. No behaviour change; everything routes through one place.
2. Fix the three `getLoginToken` defects and add the lock. `test_authentication` starts reporting correctly.
3. Convert public methods to raise, auditing each caller in the same step — `__init__.py`, `config_flow.py`, and every entity that calls `getDevice`.
4. Remove the `firstTry` parameters and the dead commented-out `setDevice` body.

Steps 1 and 2 are independently shippable and carry almost no risk. Step 3 is where behaviour changes and where the testing effort belongs.

Rollback is per-step. Nothing here touches stored configuration or the config entry schema.

## Verification

Confirmed on the reference installation: setup succeeds normally, and a
deliberately wrong password reports invalid credentials rather than a generic
failure.

Not confirmed live: the `cannot_connect` path, which needs the host
disconnected from the internet. Unit tests cover connection failure and timeout
at the client, and the mapping onto the form, but nobody has yet watched a real
outage produce the new message. Worth noticing the next time one happens — the
reference installation had a DNS outage on 2026-09-11, so they do occur.

Note that verifying the wrong-password case proves only that the working case
still works. Under the previous code `test_authentication` swallowed every
exception into `False`, so an outage reported invalid credentials too; the
distinction is the deliverable, and only half of it has been seen.

## Open Questions

- **What timeout value?** Needs observed response times from the live installation. A first guess of 30 seconds is comfortably above a normal response and well below the 120-second poll interval, but it is a guess.
- **Does the cloud rate-limit or lock accounts after repeated failed logins?** Unknowable without testing against a real account, which risks the user's own account. Argues for conservative retry behaviour by default.
- **Is `code` `8` a success response?** Unresolved, and deliberately not guessed. The Homey app treats both `'1'` and `'8'` as success while this integration accepts only a `key` containing `OK`; the two read different fields, so neither corroborates the other. The existing check is kept because it is known to work, and the raised error now carries the raw `code`, `key` and `value`, which turns a silent rejection into something a user can report. Settle it if a report ever shows a discarded `8`.
