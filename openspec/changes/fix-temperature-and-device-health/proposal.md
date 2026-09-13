## Why

The integration silently produces wrong data instead of reporting that something is wrong. On a live 9-device installation we confirmed three failures happening right now: a dead thermostat battery is recorded as a **100.2 °C room temperature** in long-term statistics, which are confirmed to be recording on the reference installation; the battery-alarm sensor that should have caught it **does not exist** for exactly the two devices whose batteries are dead; and a ninth device is missing its climate entity entirely. None of this surfaces to the user — no `unavailable` state, no repair issue, no log they would ever look at.

Separately, setpoints drift off the device's own 0.5 °C grid because the write path truncates instead of rounding, which is the "small temperature deviation" that two previous commits (`58f9f60`, `df8486e`) tried and failed to fix — and the second of those introduced a rounding regression that is still in `main`.

## What Changes

**Temperature correctness**

- Round instead of truncate when writing setpoints. `climate.py` uses `str(int(temp * 10))`; `int(591.8)` stores `591`, so a 15.1 °C request becomes a 15.06 °C setpoint. Confirmed on two live devices (`59.1 °F`, `69.9 °F`).
- Stop offering a setpoint resolution finer than the device stores. The entity currently accepts 0.1 °C input it has no way to hold. The device grid appears to be 0.5 °C, but a third-party implementation of the same API uses 0.1 °C, so the step is declared only once confirmed empirically.
- Revert the rounding regression in `WattsVisionSetTemperatureSensor`. `round(x * 2, 1) / 2` yields 0.05 °C resolution (19.55, 19.65), not the half-degree snap it was meant to be. It also makes the target sensor disagree with the air-temperature sensor beside it.
- Stop overriding `SensorEntity.state` and report through `native_value` instead. The override bypasses Home Assistant's own unit conversion, which is why each sensor hand-rolls a duplicate F→C conversion while declaring `native_unit_of_measurement` as °F for a value that is in °C. Long-term statistics are confirmed to be recording today — Home Assistant compiles them from recorded states, not from `native_value`, so the override never blocked them — and the reported unit does not change, so the series stays continuous. This is a correctness and maintainability fix, not a repair of something broken.

**Device health and availability**

- Treat an unrecognised `error_code` as a degraded device, not a crash. `ERROR_MAP[error_code]` is an unguarded dict lookup over `{0, 1}`; any other code raises `KeyError` during the first update, and because entities are added with `update_before_add=True`, **the entity is never created at all**.
- Treat any nonzero error code as a fault and expose the raw code, so that behaviour never depends on enumerating a code space we cannot see. A third-party implementation corroborates `1` as battery failure and adds `2` temperature sensor, `3` communication error and `4` floor sensor; these are adopted as documented defaults, not asserted as fact. The two dead-battery devices are therefore reporting something other than `1` — most likely `3` — since `1` would have resolved and their entities would exist. The adjacent `if error_code > 1` battery warning is currently unreachable because the lookup above it raises first.
- Expose battery state as a proper battery entity so Home Assistant's standard low-battery handling applies.
- Implement the `available` property. All six entity classes set `self._available = True` and none of them read it.
- Keep sentinel readings out of statistics. A device that cannot report must go `unavailable`, not publish a number.

**Device heterogeneity**

- Create entities based on what a device actually reports. One device in this installation has no `consigne_*` fields, so its climate and target-temperature entities crash on first update and vanish, while its other four entities work.
- Stop hardcoding `"model": "BT-D03-RF"` for every device.

**Diagnostics**

- Add a Home Assistant diagnostics platform so a user can download the integration's raw API data as redacted JSON from the integration page. Because the API is undocumented and unreachable, every future bug currently begins by asking a user to hand-craft template queries; this replaces that with one button. It would have answered all three of this change's open questions in a single click, and it surfaces fields the integration ignores entirely.
- Log unrecognised API values — unknown error codes, unknown `gv_mode` values, devices missing expected fields — once each, so that schema drift is visible rather than silent.

**Incidental, same code paths**

- `climate.py` assigns the deci-Fahrenheit *string* `value` into `extra_state_attributes["consigne_confort"]`, where every other writer puts a float in °F. A later `int(attr * 10)` then performs string repetition: `'689' * 10` → `int('689689689689689689689689689689')` gets pushed to the thermostat as a setpoint.
- `if self._state != NaN` is always true (`NaN != NaN`), so the guard is dead code and `nan` is published as a sensor state rather than the entity going unknown. Drops the `numpy` import, which is not declared in `manifest.json`.

## Capabilities

### New Capabilities

- `temperature-conversion`: the deci-Fahrenheit ↔ Home Assistant unit contract, not offering a setpoint resolution finer than the device stores, lossless round-tripping of reads and writes, and how temperature values reach long-term statistics.
- `device-health`: device error codes, battery state, and the rules for when an entity reports a value versus going `unavailable` — including never publishing a sentinel reading as a measurement.
- `device-discovery`: which entities are created for a device based on the fields it actually reports, and how an unexpected or partial device degrades without losing entities.
- `diagnostics`: downloadable redacted API data for troubleshooting an undocumented upstream, and the visibility rules for values the integration does not recognise.

### Modified Capabilities

None. `openspec/specs/` is empty; this is the first change in the project.

## Impact

**Code**

- `custom_components/watts_vision/climate.py` — write path rounding, `target_temperature_step`, attribute typing, entity creation guard
- `custom_components/watts_vision/sensor.py` — `native_value` migration, removal of hand-rolled conversion and `state` overrides, `error_code` handling, `NaN` removal, `available`
- `custom_components/watts_vision/binary_sensor.py` — `available`
- `custom_components/watts_vision/central_unit.py` — `native_value`, `available`
- `custom_components/watts_vision/const.py` — `ERROR_MAP` codes and fallback
- `custom_components/watts_vision/diagnostics.py` — new module
- `custom_components/watts_vision/manifest.json` — declared requirements if `numpy` is retained

**User-visible**

- Long-term statistics keep recording as they do today, with the same values and the same unit. What changes is that `100.2 °C` and `nan` stop entering them. Readings already recorded remain until purged, which is out of scope here.
- Devices with dead batteries become `unavailable` instead of reporting a temperature, so automations reading them must tolerate an unavailable state.
- Setpoints step at the device's real resolution instead of accepting input the device cannot hold, once that resolution is confirmed.
- One additional climate entity and two additional error entities appear on the test installation.

**Not changed**

- No `DataUpdateCoordinator` migration, no multi-config-entry support, no API client hardening (timeouts, exception types). These are real problems in the same files but are separable and are deliberately left out to keep this change reviewable.

**Constraint**

Two independent reverse-engineerings of these endpoints — the Homey Watts Vision app and the Home Assistant community thread — corroborate the deci-Fahrenheit contract and the rounding fix, and supply candidate error-code labels. They also *disagree* with this integration on four of seven `gv_mode` values, a conflict recorded in design.md and deliberately left unresolved here. Beyond that, the Watts Vision API is undocumented, third-party, and unreachable — no control over it, no contact with its developers, no notice of change. Every value it returns is untrusted input, and the integration must never encode an unverified guess as fact. This is why the change makes lookups total rather than adding more entries to them, and why no open question below blocks implementation.

**Open questions carried into design**

All three are answerable by observation on the live installation; none require contact with Watts, and none gate correctness.

- The exact `error_code` a dead battery reports (from the `KeyError` in the logs) — improves a label only; a nonzero code is already handled as a fault.
- What the second woonkamer device physically is — decides whether `device-discovery` skips setpoint-less devices or models them as a distinct device type.
- Whether these sensors currently appear in Developer Tools → Statistics at all, which determines whether the `native_value` change restores history or starts it.
