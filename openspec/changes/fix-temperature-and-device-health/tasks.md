## 1. Observations that improve labels and defaults

None of these block implementation, and none require contact with Watts. Each is answerable on the live installation and sharpens a label or a default.

- [x] 1.1a Mechanism confirmed from logs: `sensor.py:339` raises for exactly the two dead-battery devices, accounting for both missing error entities
- [x] 1.1b Value confirmed: `KeyError: 12288` (0x3000, bits 12 and 13) on both dead-battery devices; `error_code` is an int bitfield, not an enumeration
- [ ] 1.2 Confirm the second woonkamer device is a BT-WR02-RF receiver (owner's tentative identification, recorded in design.md) and whether its 12.0 °C is a real ambient reading
- [ ] 1.3 Check Developer Tools → Statistics for the Watts temperature sensors and record whether long-term statistics currently exist
- [ ] 1.4 Settle the 0.5 °C grid empirically: write an off-grid value to an *active* setpoint, wait for the device to apply it, and record whether the value that comes back has snapped

## 2. Conversion boundary

- [ ] 2.1 Add `deci_f_to_celsius(raw)` and `celsius_to_deci_f(celsius)` helpers, with `celsius_to_deci_f` rounding rather than truncating
- [ ] 2.2 Add unit tests covering the recorded live values: `446 → 7.0`, `563 → 13.5`, `572 → 14.0`, `590 → 15.0`, `689 → 20.5`, `698 → 21.0`
- [ ] 2.3 Add unit tests for the write path proving `15.1 °C → 592` and `21.1 °C → 700`, the two cases the current `int()` truncates
- [ ] 2.4 Add a round-trip test asserting every 0.5 °C step from 5.0 to 37.0 survives Celsius → deci-F → Celsius unchanged

## 3. Temperature correctness

- [ ] 3.1 Route `climate.py` reads and writes through the conversion helpers and drop the inline `/ 10` and `* 10` arithmetic
- [ ] 3.2 Change the climate entity's `temperature_unit` to Celsius, and declare `target_temperature_step` of 0.5 °C only if task 1.4 confirms the device snaps
- [ ] 3.3 Remove the `state` property overrides from all sensor entities and expose readings via `native_value` with a Celsius `native_unit_of_measurement`
- [ ] 3.4 Delete the hand-rolled F→C conversions and the `hass.config.units` branches from `sensor.py`, including the `round(x * 2, 1) / 2` regression
- [ ] 3.5 Report the target temperature as `None` when the device has no active setpoint, and remove the `NaN` sentinel and the `numpy` import
- [ ] 3.6 Store `consigne_*` values in `extra_state_attributes` as floats in a single consistent unit, fixing the `'689' * 10` string-repetition path in `async_set_hvac_mode`
- [ ] 3.7 Apply the conversion helpers to `central_unit.py` and verify it reports via `native_value`

## 4. Total lookups and feature detection

- [ ] 4.1 Make device health structural — zero is healthy, nonzero is a fault — so no error code can raise regardless of how many bits are set, and expose the raw value for unrecognised ones
- [ ] 4.2 Replace `ERROR_MAP` with bitfield-safe handling; label `12288` as observed-with-dead-battery with its provenance, and discard the third-party discrete-code labels, which assume a shape the data does not have
- [ ] 4.3 Make the `gv_mode` to preset lookup total so an unmapped mode cannot destroy a climate or sensor entity, leaving the existing mode mapping unchanged
- [ ] 4.4 Gate creation of climate and target-temperature entities on the device supplying *usable* setpoint and range values — treating present-but-null the same as absent, since the reference receiver reports `consigne_confort` and `min_set_point` as null
- [ ] 4.5 Derive the device registry model from API data instead of hardcoding `BT-D03-RF` in the entity platforms and `BT-CT02-RF` in `central_unit.py`, leaving it unset when unknown
- [ ] 4.6 Distinguish entity names for multiple devices sharing a zone without relying on Home Assistant's numeric suffixing
- [ ] 4.7 Verify every existing `unique_id` format is unchanged

## 5. Availability and battery

- [ ] 5.1 Implement the `available` property across all entity classes, replacing the unused `_available` flags
- [ ] 5.2 Derive measurement-entity availability from `error_code`, keeping setpoint entities available when their cached setpoints remain valid
- [ ] 5.3 Add a temperature plausibility bound as a backstop so unseen sentinels are suppressed without enumerating them
- [ ] 5.4 Add a battery entity per device using `BinarySensorDeviceClass.BATTERY`
- [ ] 5.5 Report entities as unavailable when a periodic refresh fails and no device data is available

## 6. Diagnostics

- [ ] 6.1 Add `diagnostics.py` with `async_get_config_entry_diagnostics`, including the raw zone and device payloads verbatim
- [ ] 6.2 Implement fail-safe redaction for credentials, tokens, MAC addresses, smart home identifiers and device identifiers, structured so an unfamiliar API key cannot leak
- [ ] 6.3 Add a test asserting that no credential or token appears in the output, including when the payload carries an unexpected field
- [ ] 6.4 Include the integration's interpretation alongside the raw data: decoded values, entities created, and entities skipped with their reason
- [ ] 6.5 Log unrecognised error codes, unrecognised `gv_mode` values and missing expected fields once each, and include them in diagnostics
- [ ] 6.6 Add `async_get_device_diagnostics` for per-device export

## 7. Verification on the live installation

- [ ] 7.1 Confirm `sensor.error_studio` and `sensor.error_logeer_kamer` now exist
- [ ] 7.2 Confirm the second woonkamer device keeps its four working entities, and that its climate and target-temperature entities are deliberately and visibly absent rather than crashing
- [ ] 7.3 Confirm the two dead-battery devices report unavailable instead of 100.2 °C, and that their battery entities show low
- [ ] 7.4 Confirm the climate entity and the target temperature sensor report identical values for the same device, at 0.5 °C resolution
- [ ] 7.5 Set a thermostat to 20.5 °C, wait for a refresh, and confirm `consigne_confort` reads back as exactly `689`
- [ ] 7.6 Confirm temperature sensors appear in Developer Tools → Statistics and are recording
- [ ] 7.7 Download diagnostics and inspect the output by eye for any unredacted credential, token or identifier before it is ever shared

## 8. Release

- [ ] 8.1 Document the user-visible changes: the 0.5 °C step, devices going unavailable, new battery entities, and any statistics unit prompt
- [ ] 8.2 Update `manifest.json` — bump the version and correct `requirements` if any dependency remains
- [ ] 8.3 Run the existing test suite and the pre-commit hooks
