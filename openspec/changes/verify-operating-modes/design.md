## Context

`gv_mode` drives everything user-facing. It selects the preset shown, decides which `consigne_*` field is read as the target temperature, and determines the payload written on any change. It is decoded by two unguarded dict lookups — `PRESET_MODE_MAP[gv_mode]` and its reverse — and by an `if`/`elif` chain in `pushTemperature`.

The current mapping, and what each mode writes:

```
  code  preset            read from          pushTemperature writes
  ────  ────────────────  ─────────────────  ──────────────────────────────────
   0    Comfort           consigne_confort   consigne_confort + consigne_manuel
   1    Off               (none)             consigne_manuel = 0
   2    Frost Protection  consigne_hg        consigne_hg = 446, manuel = 446,
                                             peremption = 20000   ← value ignored
   3    Eco               consigne_eco       consigne_eco + consigne_manuel
   4    Boost             consigne_boost     time_boost = 7200, consigne_boost,
                                             consigne_manuel      ← duration fixed
   8    Program on        consigne_manuel    NOTHING — no branch exists
  11    Program off       consigne_manuel    consigne_manuel
```

Three things in that table are defects rather than decisions. Mode `8` matches no branch, so `extrapayload` stays empty and the setpoint the caller computed is discarded in silence. Mode `2` substitutes `446` for whatever the user asked for. Mode `4` fixes the boost at two hours.

`climate.py` compounds the frost-protection case by forcing `min_temp` and `max_temp` both to 7.0 °C whenever the mode is `2`, so the UI presents a range with exactly one value in it.

`async_set_temperature` writes `consigne_manuel` **and** `consigne_confort` into the cached device dict regardless of the active mode, while `pushTemperature` sends the correct mode-specific field. The device ends up right and the cache ends up wrong, until the next refresh corrects it.

### The dispute

The Homey app decodes four of seven codes differently — `1` as program rather than off, `2` as eco rather than frost protection, `3` as off rather than eco, and `11` as eco rather than program off. Evidence favouring the current mapping is set out in the design of `fix-temperature-and-device-health` and is not repeated here; in summary it is the `consigne_hg` field name, the zero setpoint written for mode `1`, and the vendor's own six-mode enumeration, which matches this integration's concept set one-for-one and includes a distinct DEFROST that the Homey app lacks entirely.

None of that is proof. The vendor library transmits modes as strings, so it will never expose the numbering. Only hardware can settle it.

## Goals / Non-Goals

**Goals:**

- Establish by observation what each numeric mode means, and record the evidence.
- Make every offered preset produce a defined request.
- Let the user control boost duration and stop a boost.
- Stop substituting values the user did not ask for.

**Non-Goals:**

- Changing any mode's meaning before hardware confirms it should change.
- Supporting modes never observed on real hardware. If the test finds mode `5`, it gets recorded; it does not get a preset until someone knows what it does.
- Implementing the weekly programme editor. Program mode as a *state* is in scope; editing the schedule behind it is a separate and much larger piece of work.
- Cooling. `heat_cool` is read in `climate.py` but no mode writes it.

## Decisions

### Observe before changing anything

The temptation is to adopt one of the competing mappings and move on. Both are guesses; adopting either without evidence just changes which guess is enshrined, and a wrong change here silently alters the meaning of `preset_mode` in every automation the users of this integration have written.

**Chosen:** treat the numbering as unknown until observed, and keep the current mapping meanwhile. The investigation is a prerequisite task, not a side effect of implementation.

The method is direct: put one device into each mode from the **physical thermostat** — not through this integration, which would make the observation circular — and record the raw `gv_mode` the API reports alongside what the device's own screen says. The physical display is the authority, because it is the device telling us what it thinks it is doing.

Diagnostics from `fix-temperature-and-device-health` make this straightforward: the raw payload is one download per mode.

### Make the lookups total first

Deliberately driving a device into unfamiliar states is exactly the scenario that destroys entities today: an unmapped `gv_mode` raises `KeyError` during `async_update`, and with `update_before_add=True` the entity is dropped permanently. Investigating modes before that is fixed risks losing entities on the test installation and needing a restart to get them back.

**Chosen:** `fix-temperature-and-device-health` lands first. This is a hard sequencing dependency, not a preference.

### Boost duration and stop need services, not entity attributes

Home Assistant's climate entity has no concept of a preset with a duration. `set_preset_mode` takes a preset name and nothing else.

Options considered: a `number` entity holding the duration that boost reads when started; encoding durations into preset names such as `boost_1h`; or custom services.

**Chosen: custom services**, one to start a boost with a duration and one to stop it. The official Vision+ integration reaches the same conclusion, exposing `activate_timer_mode` with a `duration` attribute — useful corroboration that this is the shape the vendor's own model wants. A `number` entity splits one user intention across two entities and leaves the duration ambiguous when boost is started from the standard preset control. Encoded preset names multiply presets and still cannot express arbitrary durations.

Selecting the plain `boost` preset keeps working and uses the documented default.

### Stopping a boost restores the previous mode

The device reports `time_boost` counting down, so a boost has a natural end. Today the only way to leave early is to select another preset, which also rewrites that preset's setpoint — a side effect the user did not ask for.

**Chosen:** stopping a boost returns the device to the mode that was active before it started, writing no setpoint. This needs the previous mode to be remembered. `climate.py` already keeps a `previous_gv_mode` in `extra_state_attributes` for the off/on transition; that mechanism is the obvious place, though it currently survives only in entity state and is lost on restart. Accept that limitation, and fall back to a sensible default when the previous mode is unknown, rather than building persistence for it.

### Frost protection: ask the device, do not assume

The hardcoded `446` may be correct — 7.0 °C is the conventional frost-protection temperature and every device in the reference installation reports exactly that. But the device also reports `min_set_point` and `max_set_point`, and the integration currently overrides both with 7.0 °C in this mode rather than consulting them.

**Chosen:** try writing a different frost-protection value on hardware and observe whether the device accepts it. If it does, stop substituting and let the user choose within the device's own range. If it refuses, keep `446` but make the entity refuse the request rather than silently substituting, and say why.

### What the software half could settle without hardware

Groups 4 and 6 turned out not to depend on the numbering being confirmed, and
were implemented first.

Program mode's missing branch resolved itself once a raw payload existed: the
`programme` field is the weekly schedule, 48 half-hour slots across seven days,
so in that mode the schedule owns the setpoint and none should be sent. The
absent branch was therefore the right behaviour arrived at by accident, and it
now says so explicitly rather than falling through to an empty payload while its
caller computed a value that was discarded. That `gv_mode 11` does write
`consigne_manuel` fits a manual override of a running programme, which is a
coherent reading of the pair.

Stopping a boost re-sends the setpoint the target mode already holds rather than
sending a mode with no setpoint at all. Whether the API accepts the latter is
unknown, and a live heating system is not where to find out. The effect is the
same -- nothing changes -- at the cost of one redundant field.

## Risks / Trade-offs

**This change requires manipulating a live heating system.** → The only change in the project that does. Cycling a thermostat through every mode in a house that is being heated is disruptive and, in winter, potentially damaging if a room is left in frost protection by accident. Do it outside heating season, on one device, in a room where the outcome does not matter, and record the starting state so it can be restored.

**Testing may leave a device in an unrecognised mode.** → Mitigated by the sequencing dependency: unmapped modes must be survivable before this starts. Note also that the physical thermostat can always restore a known mode independently of the integration.

**If the hardware test proves the current mapping wrong, the fix is breaking.** → Every affected preset changes meaning, and automations referencing them change behaviour silently. It would need a clear release note naming which presets changed and what they became. This is precisely why the mapping is not being changed speculatively — a wrong correction is worse than a known unknown, because it looks authoritative.

**Adding services expands the integration's surface.** → Services are versioned user-facing API; removing one later is itself breaking. Two services with narrow, obvious purposes is a modest cost for closing the longest-standing gap in the README.

**Boost restore-to-previous depends on state that does not survive a restart.** → A boost started before a Home Assistant restart cannot be stopped back to its true previous mode. Accepted: the fallback is a documented default, and the situation is rare and recoverable from the thermostat itself.

## Open Questions

- **What does each `gv_mode` value actually mean?** The question this change exists to answer. Needs hardware.
- **Do modes exist that this integration has never seen?** The known set is `0, 1, 2, 3, 4, 8, 11`. The gaps suggest there are more, and the vendor enumerates six named modes against this integration's seven codes, so at least one concept is represented by two numbers — the `8` and `11` program pair being the obvious candidate.
- **What distinguishes `nv_mode` from `gv_mode`?** They are always sent equal. Plausibly current versus new mode, but that is a guess about a French-derived abbreviation and nothing depends on it while they stay equal.
- **Why is `peremption` 20000 for frost protection and 15000 everywhere else?** Reads as a command expiry in milliseconds. Unexplained, and it is the only per-mode variation of a parameter otherwise treated as constant.
- **Does the device accept a frost-protection temperature other than 7.0 °C?** Determines whether the substitution is a limitation or a bug.
- **What should program mode write?** If the schedule owns the setpoint, writing none is correct and the caller should stop computing one. If the device expects `consigne_manuel` as an override, mode `8` needs a branch. Currently neither is true: a value is computed, then discarded.
