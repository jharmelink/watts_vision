## Context

The integration polls the Watts cloud API every 120 seconds into a single mutable dict (`WattsApi._smartHomeData`) and lets each entity read from it during its own `async_update`. There is no `DataUpdateCoordinator`. Six entity classes exist; all six set `self._available = True` in `__init__` and none of them define an `available` property.

The problems in this change were confirmed against a live nine-device installation on a metric system. That evidence shapes several decisions below, so it is recorded here rather than left in a conversation:

```
  DEVICE            climate   air_temp   target   mode   error   heating
  ───────────────── ───────── ────────── ──────── ────── ─────── ─────────
  6 healthy devices    ✓        ~21        ✓       ✓      ✓        ✓
  studio               ✓      ⚠ 100.2      ✓       ✓   ✗ GONE      ✓
  logeer_kamer         ✓      ⚠ 100.2      ✓       ✓   ✗ GONE      ✓
  woonkamer (2nd)   ✗ GONE      12.0    ✗ GONE     ✓      ✓        ✓
```

Three facts established from that data:

1. **The API unit is deci-Fahrenheit, and the device grid appears to be 0.5 °C.** Every healthy setpoint decodes to an exact half-degree Celsius: `446 → 7.0`, `563 → 13.5`, `572 → 14.0`, `590 → 15.0`, `689 → 20.5`, `698 → 21.0`. The read arithmetic has always been correct; the two historical commits that rewrote the conversion formula (`58f9f60`, `df8486e`) were chasing a bug that was not there. The grid itself is less certain than the unit — see the Risks section.
2. **Off-grid setpoints come from the write path.** Two devices hold `591` and `699`, which reproduce exactly from `int(591.8)` and `int(699.8)` — a user requesting 15.1 °C and 21.1 °C through a UI that should never have offered those values, with `int()` truncating instead of rounding.
3. **Entity loss is caused by `update_before_add=True` plus unguarded lookups.** `ERROR_MAP[error_code]` raises `KeyError` for an unmapped code, and `smartHomeDevice["consigne_confort"]` raises `KeyError` for a device without setpoints. In both cases Home Assistant drops the entity silently and permanently.

### Constraints

The Watts Vision API is **undocumented, third-party, and unreachable**. We have no control over it, no contact with its developers, no specification, and no notice of change. Everything we believe about it is inferred from observing one installation.

This is a hard constraint on the design, not a caveat:

- **Every value the API returns is untrusted input.** Unknown error codes, absent fields, unexpected device types and sentinel readings are all normal operating conditions, not exceptional ones. Any lookup, cast or index over API data must be total.
- **We must not encode guesses as facts.** Where the meaning of a value is unknown, the integration reports the raw value and describes it as unrecognised, rather than inventing a label. The existing `ERROR_MAP` is an example of the failure mode: a plausible-looking guess that turned out to be wrong and took entities down with it.
- **The unit contract is inference, but it is now corroborated.** Two independent reverse-engineerings of the same endpoints decode temperatures identically: the [Homey Watts Vision app](https://github.com/idleprocess-zero/watts-vision-homey-app) uses `Math.round((c * 1.8 + 32) * 10)` and `Math.round(((w / 10 - 32) / 1.8) * 10) / 10`, and the Home Assistant community thread documents `(value / 10 - 32) / 1.8`. Three implementations, one contract. Notably the Homey app also **rounds rather than truncates** on the write path, independently arriving at the fix specified here. Code should still fail visibly rather than silently if a value cannot be decoded.
- **The unit may be a per-device property, not a platform constant.** The official integration reads `thermostat.temperature_unit` from each device and selects Celsius or Fahrenheit accordingly. If the legacy platform exposes a comparable field, the blanket assumption that the wire format is always deci-Fahrenheit could be wrong for some users even though it holds for the reference installation. The diagnostics work in this change is the cheapest way to find out: the raw payload will show whether such a field exists.
- **Third-party implementations are evidence, not authority.** They are useful precisely because they observed devices we cannot. But they are themselves guesses, they may target a different platform version, and where they disagree with us the disagreement must be resolved by evidence rather than by deferring to either side. See the operating mode conflict below.
- **The API can change without warning.** Firmware or cloud updates may add codes, add device types, or alter field names. The integration's job is to degrade into `unavailable` when that happens, never to crash and never to invent data.

Since Home Assistant 2026.1 there is also an official, vendor-maintained core integration, `watts`, at Platinum quality tier. It targets the Watts Vision+ platform and supports gateways **BT-CT03-RF** and **BT-ST03-RF** only. The reference installation's gateway is a **BT-CT02-RF**, which is not on that list.

The gateway, not the thermostat, determines the platform: BT-D03-RF thermostats appear on the official integration's supported sub-device list, but they reach the cloud through whichever gateway they are paired with. This repository therefore serves the BT-CT02-RF installed base — users whose hardware cannot move to the official integration and for whom no upstream maintainer exists. That sharpens the constraints above rather than relaxing them: there is no vendor to escalate to, and no prospect of V1 bugs being fixed at source.

The practical consequence is that the change is designed so that **no open question blocks correctness**. Resolving them improves labels and diagnostics; it is not a prerequisite for shipping.

## Goals / Non-Goals

**Goals:**

- One conversion boundary between the API's deci-Fahrenheit integers and the rest of the integration.
- Setpoint writes that round-trip losslessly at whatever resolution the device actually stores.
- Temperature readings that reach long-term statistics.
- A device that cannot report says so, rather than publishing a plausible-looking number.
- No entity disappears because of unexpected data.

**Non-Goals:**

- Migrating to `DataUpdateCoordinator`. It is the right long-term shape and would make availability cleaner, but it touches every entity and every platform setup; bundling it would make this change unreviewable. The `available` work here is written so a later coordinator migration can absorb it.
- Multi config entry support. `hass.data[DOMAIN][API_CLIENT]` is keyed by domain only, so a second entry clobbers the first. Real, separate.
- API client hardening — request timeouts, real exception types, the `raise None` in `getLoginToken`, the unused `firstTry` parameters.
- Purging existing `100.2 °C` readings from the statistics database.
- Supporting device features the integration does not expose today: programs, boost duration, cooling setpoints.
- Replacing the optimistic-update hack. `climate.py` fakes immediate state by reaching into `client._smartHomeData` — the same fifteen-line nested walk copy-pasted three times — because the refresh interval is 120 seconds. The official integration solves this properly by polling every 5 seconds for a short window after a command instead of faking anything. That is the right answer and it belongs with the coordinator migration, not here; this change only fixes the type corruption in the existing hack.

## Decisions

### Convert at the API boundary; entities speak Celsius

Two conversion strategies were considered.

**Option A — entities keep `temperature_unit = FAHRENHEIT` and Home Assistant converts.** This is what `climate.py` does today and it is correct for display. The integration writes no conversion code at all.

**Option B — a single conversion function pair at the API boundary; every entity reports Celsius.** Home Assistant still converts Celsius to Fahrenheit for users on imperial systems, so no user loses anything.

**Chosen: Option B.** The deciding factor is the setpoint grid. That grid is fundamentally Celsius — the device stores whole or half degrees Celsius and the cloud re-expresses them in tenths of a Fahrenheit degree. Under Option A, `target_temperature_step` has to be declared in the entity's unit, making a 0.5 °C step into 0.9 °F: an awkward number, a delta rather than a temperature (so it must not be unit-converted with the offset formula), and a value whose correct handling by the frontend we would have to verify. Under Option B the step is expressed directly in the unit the grid actually lives in, whatever its value turns out to be.

The secondary benefit is that rounding then happens in exactly one place instead of being reimplemented per entity, which is precisely the failure mode this change exists to end.

```
  ┌─────────────────────────────────────────────────────────────┐
  │  API  "689"  ──► deci_f_to_celsius() ──►  20.5 °C           │
  │                                             │                │
  │                                             ▼                │
  │                              every entity, native_value      │
  │                              native_unit = °C                │
  │                                             │                │
  │                                             ▼                │
  │                        HA converts to the user's unit,       │
  │                        applies precision, records statistics │
  │                                                              │
  │  API  "689"  ◄── celsius_to_deci_f() ◄──  20.5 °C           │
  │                  round(), never int()                        │
  └─────────────────────────────────────────────────────────────┘
```

### Drive availability from device state, not from the sentinel value

The dead-battery reading converts to roughly 100.2 °C, which corresponds to a raw value near `2124`. Matching that number exactly would be brittle: we do not know it precisely, we do not know whether it varies by firmware or device type, and it would silently stop working if it changed.

**Chosen:** availability is derived from `error_code`. A device whose error code indicates a fault that prevents measurement reports `available = False` for its measurement entities. A plausibility bound on temperature (a room thermostat reporting outside roughly -20 °C to 60 °C is not reporting) is kept as a second line of defence, not as the primary mechanism — it catches sentinels we have not seen without our having to enumerate them.

Setpoint entities are treated separately from measurement entities: the two dead-battery devices still report valid `consigne_*` values from the cloud's cache, so their target temperature remains meaningful even while their air temperature does not.

### Replace unguarded lookups with total functions

Both entity-loss bugs are the same shape: a dict lookup that assumes the API's value space. The fix is not to add more keys to `ERROR_MAP` — a new firmware will invent another code — but to make the lookup total.

`ERROR_MAP` gains a fallback path so that any unrecognised code yields a usable state plus the raw code for diagnosis.

Because the API is undocumented and cannot be clarified (see Constraints), the integration SHALL NOT attribute meaning to an error code it has no direct evidence for. The rule is therefore structural rather than enumerated:

```
  error_code == 0        →  healthy
  error_code != 0        →  faulted; measurement entities unavailable
  known code             →  additionally labelled (e.g. battery failure)
  unknown code           →  labelled as an unrecognised fault, raw code exposed
```

This ships correctly without knowing what any particular nonzero code means. Discovering that a specific code indicates battery failure only improves the *label*; it does not change the behaviour.

Third-party evidence now exists for the code space. The Homey app decodes:

```
  1  Battery failure          2  Temperature sensor fault
  3  Communication error      4  Floor sensor fault
                                 default: "Hardware error code N"
```

This corroborates the existing `DEF_BAT_TH → 1` mapping, which changes the picture: the two dead-battery devices in the test installation are **not** reporting code `1`, because `ERROR_MAP[1]` would have resolved and their entities would exist. Combined with their sentinel temperature reading, **code `3`, communication error, is the leading hypothesis** — a dead battery stops the thermostat transmitting, the gateway loses contact, and reports both a comms fault and a placeholder temperature.

These labels SHALL be adopted as plausible defaults with their provenance recorded, not asserted as fact. The structural rule above is what the behaviour depends on; the labels are cosmetic and replaceable. Task 1.1 still settles it from the logs.

### The operating mode map is disputed and must not be changed blind

The Homey app decodes `gv_mode` differently from this integration:

```
  code   this integration        Homey app
  ────   ────────────────────    ──────────
   0     Comfort                 comfort     agree
   1     Off                     program     CONFLICT
   2     Frost Protection        eco         CONFLICT
   3     Eco                     off         CONFLICT
   4     Boost                   boost       agree
   8     Program on              —
  11     Program off             eco         CONFLICT
```

**Chosen: keep this integration's mapping, and treat the conflict as unresolved rather than silently adopting either side.**

The evidence favours the existing mapping. `consigne_hg` is *hors gel* — French for frost protection — and reads `446`, exactly 7.0 °C, on every device in the test installation; this integration pairs `gv_mode 2` with that field, while the Homey app has no frost-protection concept at all despite the field being present in the payload. The `gv_mode 1` push sends `consigne_manuel: "0"`, which is what an off state looks like. The Homey app maps both `2` and `11` to eco, which has the shape of a guess, and its source declares itself a debug build targeting the newer Vision+ platform, so its constants may describe a different system.

The official Watts-maintained integration settles the *concept set*, though not the numbering. Its library enumerates exactly six thermostat modes:

```
  vendor (visionpluspython)     this integration
  ─────────────────────────     ────────────────────────
  COMFORT                       Comfort              (0)
  ECO                           Eco                  (3)
  DEFROST                       Frost Protection     (2)
  TIMER                         Boost                (4)
  PROGRAM                       Program on / off     (8, 11)
  OFF                           Off                  (1)
```

That is this integration's set, one-for-one, with *boost* and *timer* naming the same idea. Critically DEFROST is a first-class vendor mode, matching `PRESET_DEFROST` paired with `consigne_hg` (*hors gel*, frost protection) — whereas the Homey app has no such concept and folds that code into eco. Three lines of evidence now favour this integration's semantics over Homey's.

The numbering itself stays unresolved: the V2 API transmits modes as **strings** (`ThermostatMode[mode.upper()]`), so the vendor library never exposes the numeric `gv_mode` codes that V1 uses. No amount of reading the official integration will settle which number means what.

There is a further reason to discount the conflict. The Homey app applies a single set of mode constants across *both* platforms it supports, but V2 serves a newer hardware generation (Vision+) that the V1 devices cannot become. If the two generations differ in mode semantics, at most one of those mappings can be right for V1 hardware — and this integration's mapping was derived from V1 devices, which is the only hardware it targets.

That reasoning is still not conclusive. The test installation cannot settle it: every device is in mode `0` or `3`, and the preset each one displays is derived from the very map under dispute, so the observation is circular.

Because presets are user-visible and have been stable for years, changing them would silently alter the meaning of existing automations. The mapping therefore stays as it is, the conflict is recorded, and resolving it is a separate change with its own evidence. What this change *does* fix is that an unrecognised mode can no longer destroy an entity — which is the part that matters regardless of who is right.

### Detect features per device rather than maintaining a device-type registry

The ninth device has no `consigne_*` fields. Two ways to handle it: recognise its device type and know what a device of that type supports, or check which fields it actually reports.

The official integration's documentation supplies the first real inventory of Watts device models, which is worth recording since the API is otherwise opaque:

```
  gateways     BT-CT03-RF  BT-ST03-RF          (reference installation: BT-CT02-RF)
  sub-devices  BT-D03-RF   BT-DP02-RF  BT-A02-RF  BT-A03-RF  BT-TH02-RF
               PR03-RF     PR03-RF16   BT-WR03-RF  BT-WR02-RF
```

Several of these are plainly not thermostats. `BT-TH02-RF` is the leading candidate for the reference installation's setpoint-less ninth device — it reports a temperature, a mode, a heating state and an error code but no `consigne_*`, which is what a sensor rather than a thermostat would produce. Receiver and relay modules such as `PR03-RF` and `BT-WR02-RF` would produce a similar shape. This list is a hypothesis generator, not a supported-device list for this integration.

**Chosen: field presence.** We do not have a list of Watts device types, we cannot enumerate what future ones report, and the failure mode of guessing wrong is the silent entity loss we are trying to eliminate. Checking for the fields an entity needs, before creating that entity, is total by construction. The device type reported by the API is used for the device registry model string, but not to gate entity creation.

### Preserve every existing unique_id

Entity history in Home Assistant is keyed on `unique_id`. Changing any existing one orphans that entity's recorded history and leaves a stale registry entry. All current unique ID formats are kept exactly as they are. New entities — the battery entity, the previously-crashing climate and error entities — get new IDs and appear as new entities.

Friendly names may change to disambiguate devices sharing a zone. Existing entities keep their `entity_id` because the registry is keyed on `unique_id`, so automations continue to work; only display names change.

### Diagnostics exist to observe the API, not to describe the integration

A conventional diagnostics dump reports what an integration thinks is going on. Here the valuable content is the opposite: the parts of the API payload the integration does *not* understand.

Every investigation into this integration starts the same way — a user is asked to hand-craft Jinja template queries in Developer Tools, and even then can only see values that reached an entity attribute. The `temperature_air` sentinel behind the 100.2 °C readings is a good example: it is the root cause of a user-visible bug and it is not exposed anywhere in Home Assistant, because the integration converts it before anyone can see it.

**Chosen:** include the raw zone and device payloads verbatim after redaction, with the integration's interpretation alongside rather than instead. Fields the integration ignores are the point of the export, not noise in it.

This is also why unrecognised values get logged once each. Under the Constraints above, an unknown error code is a normal event rather than an error — but it is still the signal that the API has moved, and it should not be invisible.

**Redaction fails safe.** Diagnostics get pasted into public issue trackers, so the mechanism must protect fields nobody thought about. Home Assistant's `async_redact_data` operates on a named set of keys, which is a deny-list and therefore leaks anything newly added upstream. This is the platform convention — the official Watts integration uses it with a four-key list — so the stricter approach here is a deliberate deviation, justified by a legacy API that can add fields with no notice and no upstream to report them to. Given the API can add fields without warning, the redaction step must be structured so that an unfamiliar key cannot carry a credential or identifier into the output — for example by redacting on key patterns and by never passing the config entry's `data` through unfiltered. Getting this wrong is worse than shipping no diagnostics at all.

### Battery is a binary sensor, not a percentage sensor

The API exposes a fault code, not a charge level. `BinarySensorDeviceClass.BATTERY` expresses exactly that: on means low. A `SensorDeviceClass.BATTERY` percentage would require inventing numbers we do not have.

## Ruled Out

Recorded so they are not re-investigated. Each was a plausible theory about the "small temperature deviation" that was checked numerically and found not to be the cause.

- **The read-path conversion arithmetic is correct and always has been.** `round(((v / 10) - 32) * 5 / 9, 1)` returns the exact half-degree for every one of the 51 setpoints between 5.0 °C and 37.0 °C. There is no accumulated rounding error to find here.
- **The two historical "fix" commits were chasing a phantom.** `(int(v) - 320) * 5 / 9 / 10` and `((v / 10) - 32) * 5 / 9` are mathematically identical across the whole range, so `58f9f60` changed nothing — and the integer form it replaced was marginally *more* precise, being exact until the final divide. `df8486e` then introduced the 0.05 °C regression. Two commits, no progress.
- **`int()` truncation does not affect half-degree setpoints.** Converting every 0.5 °C step from 5.0 to 30.0 °C to deci-Fahrenheit and truncating gives the same answer as rounding. The truncation defect only bites for 0.1 °C inputs, which is why it took a UI offering an impossible resolution to expose it.
- **`min_set_point` / `max_set_point` decode correctly.** `410` and `986` give 5.0 °C and 37.0 °C, a sensible thermostat range. Not a source of error.
- **The 100.2 °C reading is not a conversion bug.** The climate entity and the sensor entity reach it by entirely different code paths and agree exactly, which means the value is faithful to the source data. The fault is upstream of the integration.

## Risks / Trade-offs

**Changing a sensor's `native_unit_of_measurement` from °F to °C may invalidate existing statistics.** → Home Assistant detects unit changes on entities with a `state_class` and can raise a statistics issue asking the user to confirm. For metric users the recorded *numbers* are unchanged (the old code already published Celsius), so the series remains continuous in value even if Home Assistant asks about the unit. Call this out in the change notes and verify on the test installation before release.

**Long-term statistics may not exist yet for these entities at all.** → Unconfirmed; it depends on whether the overridden `state` property has been blocking the recorder. If nothing was being recorded, there is nothing to invalidate and this risk evaporates. Resolving the open question below settles it.

**Devices becoming unavailable will break automations that assume a number is always present.** → This is the correct behaviour and the whole point of the change, but it is user-visible and can break a working automation. Document it prominently; a template that averaged house temperature was previously being fed 100.2 °C and was already wrong, just invisibly.

**Diagnostics could leak credentials into a public issue tracker.** → Treated as the highest-severity risk in this change. Redaction must fail safe against fields that do not exist yet, the config entry's `data` must never be passed through unfiltered, and the output must be inspected on the live installation before release. A leak here is unrecoverable in a way that a wrong temperature is not.

**A plausibility bound could suppress a legitimate extreme reading.** → Bounds are set well outside any room thermostat's real operating range, and the bound is a backstop rather than the primary mechanism. A device reporting a genuine 61 °C has a problem worth surfacing anyway.

**The 0.5 °C grid is less certain than when it was chosen.** → The decision rested on every clean setpoint in the test installation landing on an exact half-degree. Two pieces of counter-evidence have since appeared: the Homey app rounds to 0.1 °C and declares no step at all, and the test installation's own devices *persisted* the off-grid values `591` and `699` rather than snapping them. Both off-grid values sit in inactive comfort setpoints, so the device may never have applied them — which would explain the persistence without disproving the grid. Settle it empirically before implementing task 3.2: write an off-grid value to an **active** setpoint, wait for the device to apply it (the Homey app observes roughly 13 seconds), and see whether the value that comes back has snapped. If it has not, drop the step declaration and keep only the rounding fix.

**Declaring a 0.5 °C step is a visible UI change.** → Users who previously dragged to 15.1 °C will find they cannot. They were never getting 15.1 °C; they were getting 15.06 °C. The step change makes an existing limitation honest rather than introducing a new one — provided the grid is real; see above.

**Reverting the `round(x * 2, 1) / 2` expression changes displayed values.** → Only for off-grid setpoints, where it currently shows values like 15.05. Those readings were wrong; the change corrects them.

## Migration Plan

1. Land the conversion boundary and the write-path rounding first — these are self-contained and independently verifiable against the recorded live values (`446 → 7.0`, `689 → 20.5`, `15.1 °C → 592`).
2. Land the total lookups and feature detection. On the test installation this should make `sensor.error_studio`, `sensor.error_logeer_kamer` and one additional climate entity appear.
3. Land availability and the battery entity last, since it is the only step that removes data from statistics.
4. Verify on the live installation that the two dead-battery devices report unavailable rather than 100.2 °C, and that their battery entities show low.

Rollback is per-step; nothing here changes stored configuration or the config entry schema, so reverting the component restores previous behaviour without user action.

## Open Questions

None of these can be answered by asking Watts, and none of them block implementation. Each is answerable by observation on the live installation, and each improves a label or a default rather than changing behaviour.

- **What `error_code` does a dead battery actually report?** Answerable from the `KeyError` in Home Assistant's logs. Until then, a nonzero code is treated as a fault and exposed raw, which is already correct behaviour. Knowing the value only lets us print "battery failure" instead of "unrecognised fault".
- **What is the second woonkamer device?** Determines whether `device-discovery` merely skips setpoint-less devices or whether a distinct device type deserves first-class modelling, and whether 12.0 °C is a real reading from a cold location or another artefact.
- **Do these sensors currently appear in Developer Tools → Statistics?** Decides whether the `native_value` change restores a broken history or starts recording for the first time, and how loudly the unit change needs to be communicated.
- **Is this integration's `gv_mode` mapping correct?** A third-party implementation disagrees on four of seven codes. Not settleable from the test installation, and deliberately not changed here. Resolving it needs a device deliberately cycled through each mode with the raw `gv_mode` recorded at each step — a separate change, since altering presets would silently change the meaning of users' existing automations.
- **What is the long-term status of the V1 platform?** The Homey app authenticates against V1 (Keycloak, `auth.smarthome.wattselectronics.com`) and falls back to a V2 platform: Azure AD B2C at `visionlogin.b2clogin.com`, API at `prod-vision.watts.io`, under a scope named `homeassistant-api/homeassistant.read`. V2 is understood to serve a newer hardware generation (Vision+) rather than being a migration path for existing devices, so V1 remains the correct and only target for the installed base this integration serves. The residual question is how long Watts keeps V1 running for hardware that cannot move. Not addressed here; flagged because it would change the repository's priorities if the answer turned out to be "not long".
- **Does the API treat response code `8` as success?** The Homey app accepts both `'1'` and `'8'` as success codes, while this integration only accepts a `key` containing `OK`. If `8` is a legitimate success this integration may be discarding valid responses. Not investigated here.
- **Should the plausibility bound be configurable?** Defaulting to a fixed range is simpler; a Watts installation driving something other than room heating might need different limits. Deferred until someone reports needing it.
