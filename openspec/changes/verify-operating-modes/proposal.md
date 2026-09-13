## Why

`gv_mode` is the single most consequential value this integration decodes. It decides which preset a user sees, which setpoint field is read as the target temperature, and which fields are written when anything changes. It is also the value we are least sure about.

A third-party implementation of the same API disagrees with this integration on four of seven codes. Three lines of circumstantial evidence favour this integration — the `consigne_hg` field name (*hors gel*, frost protection), the zero setpoint written for the off mode, and the vendor's own mode enumeration in the official Vision+ integration — but none of them is proof, and the reference installation cannot settle it because every device sits in mode `0` or `3` and the preset each displays is derived from the very map in dispute.

Meanwhile the mode handling that does exist has gaps that were never decisions. `gv_mode 8` has no branch in `pushTemperature` at all, so selecting "Program on" computes a setpoint and silently discards it. Boost hardcodes a two-hour duration with no way to choose one and no way to stop early. Frost protection hardcodes 7.0 °C and ignores what the user asked for. These are the "program, stop boost, etc." the README has listed as unfinished since the project began.

This change establishes what the modes actually are, records the evidence, and fixes the handling that is demonstrably wrong regardless of how the numbering question resolves.

## What Changes

**Establish ground truth**

- Cycle a device through every reachable mode on real hardware, recording the raw `gv_mode` the API reports at each step alongside the physical thermostat's own display. This is the only way to settle the numbering, and it requires hardware.
- Record the resulting mapping with its provenance, so a future reader knows which entries are confirmed and which are inherited assumptions.
- Determine whether modes exist that the integration has never seen. The known set is `0, 1, 2, 3, 4, 8, 11`; the gaps in that sequence suggest there are more.

**Fix handling that is wrong independent of the numbering**

- `gv_mode 8` falls through `pushTemperature`'s `if`/`elif` chain to an empty payload. The caller computes a setpoint from `consigne_manuel` and it is discarded without comment. Either program mode legitimately takes no setpoint — in which case the caller should not compute one — or it needs a branch.
- **Boost duration is hardcoded** to `time_boost: "7200"`. A user cannot choose a duration.
- **Boost cannot be stopped.** Leaving boost requires selecting another preset, which also rewrites that preset's setpoint. There is no way to simply end a boost and return to what was running before.
- **Frost protection ignores the requested temperature**, hardcoding `consigne_hg: "446"`. `climate.py` compounds this by forcing both `min_temp` and `max_temp` to 7.0 °C whenever the mode is `2`, so the UI offers a single selectable value.
- Setting a temperature writes `consigne_confort` into the local cache regardless of the active mode, so adjusting the target while in eco makes the comfort setpoint appear to change until the next refresh.

**Document what remains unexplained**

- `nv_mode` is always sent equal to `gv_mode`, with no explanation of what distinguishes them.
- `peremption` is `15000` everywhere except frost protection, where it is `20000`.

**Explicitly not changed**

- The mode-to-preset mapping stays exactly as it is until the hardware test says otherwise. Presets appear in users' automations and dashboards; changing what `eco` means would silently alter behaviour in installations we cannot see.

## Capabilities

### New Capabilities

- `operating-modes`: what the device's operating modes are, how each maps to a Home Assistant preset and HVAC mode, which setpoint field each reads and writes, and the rules governing changes to that mapping.

### Modified Capabilities

None. `device-health` in `fix-temperature-and-device-health` requires that an unrecognised mode cannot destroy an entity; that requirement stands unchanged and is a prerequisite for safely investigating modes on live hardware.

## Impact

**Code**

- `custom_components/watts_vision/const.py` — the mode maps and their recorded provenance
- `custom_components/watts_vision/watts_api.py` — `pushTemperature`'s per-mode payloads, including the missing `gv_mode 8` branch
- `custom_components/watts_vision/climate.py` — preset handling, the forced frost-protection temperature range, the cache write in `async_set_temperature`
- Possibly a new service for boost duration and for stopping a boost, since neither fits the standard climate entity model

**Depends on**

`fix-temperature-and-device-health` should land first. Investigating modes means deliberately putting a device into states the integration may not recognise, and today an unmapped `gv_mode` raises `KeyError` during the first update and silently destroys the entity. Making that lookup total is a precondition for doing this safely.

**User-visible**

- Boost gains a controllable duration and a way to stop, the longest-standing gap in the README.
- Frost protection stops being a single fixed temperature, if the device permits a range.
- No preset changes name or meaning unless the hardware test proves the current mapping wrong, in which case that becomes a breaking change with its own announcement.

**Risk**

This is the only change in the project that requires deliberately manipulating a live heating system. It should be done outside heating season or in a room where an unexpected mode does no harm.
