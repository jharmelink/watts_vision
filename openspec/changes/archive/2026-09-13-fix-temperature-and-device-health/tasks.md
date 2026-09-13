## 1. Observations that improve labels and defaults

None of these block implementation, and none require contact with Watts. Each is answerable on the live installation and sharpens a label or a default.

- [x] 1.1a Mechanism confirmed from logs: `sensor.py:339` raises for exactly the two dead-battery devices, accounting for both missing error entities
- [x] 1.1b Value confirmed: `KeyError: 12288` (0x3000, bits 12 and 13) on both dead-battery devices; `error_code` is an int bitfield, not an enumeration
- [ ] 1.2 Confirm the second woonkamer device is a BT-WR02-RF receiver (owner's tentative identification, recorded in design.md) and whether its 12.0 °C is a real ambient reading
- [x] 1.3 Statistics confirmed present and recording on the reference installation; the `state` override never blocked the recorder, so the `100.2 °C` readings are genuine recorded history
- [x] 1.4 Settled on hardware: writing `690` to an active comfort setpoint reads back unchanged, so the device stores 0.1 °F and does NOT snap to 0.5 °C. No `target_temperature_step` of 0.5 is justified

## 2. Conversion boundary

- [x] 2.1 Add `deci_f_to_celsius(raw)` and `celsius_to_deci_f(celsius)` helpers, with `celsius_to_deci_f` rounding rather than truncating
- [x] 2.2 Add unit tests covering the recorded live values: `446 → 7.0`, `563 → 13.5`, `572 → 14.0`, `590 → 15.0`, `689 → 20.5`, `698 → 21.0`
- [x] 2.3 Add unit tests for the write path proving `15.1 °C → 592` and `21.1 °C → 700`, the two cases the current `int()` truncates
- [x] 2.4 Add a round-trip test asserting every 0.5 °C step from 5.0 to 37.0 survives Celsius → deci-F → Celsius unchanged

## 3. Temperature correctness

- [x] 3.1 Route `climate.py` reads and writes through the conversion helpers and drop the inline `/ 10` and `* 10` arithmetic
- [x] 3.2 Change the climate entity's `temperature_unit` to Celsius and declare `target_temperature_step` of 0.1 °C as a documented usability choice, not as the device's resolution; a 0.5 °C step is disproven by task 1.4
- [x] 3.3 Remove the `state` property overrides from all sensor entities and expose readings via `native_value` with a Celsius `native_unit_of_measurement`
- [x] 3.4 Delete the hand-rolled F→C conversions and the `hass.config.units` branches from `sensor.py`, including the `round(x * 2, 1) / 2` regression
- [x] 3.5 Report the target temperature as `None` when the device has no active setpoint, and remove the `NaN` sentinel and the `numpy` import
- [x] 3.6 Store `consigne_*` values in `extra_state_attributes` as floats in a single consistent unit, fixing the `'689' * 10` string-repetition path in `async_set_hvac_mode`
- [x] 3.7 Apply the conversion helpers to `central_unit.py` and verify it reports via `native_value`

## 4. Total lookups and feature detection

- [x] 4.1 Make device health structural — zero is healthy, nonzero is a fault — so no error code can raise regardless of how many bits are set, and expose the raw value for unrecognised ones
- [x] 4.2 Replace `ERROR_MAP` with bitfield-safe handling; label `12288` as "device has stopped reporting" — it is observed on both a flat-battery device and a broken one, so it is not battery-specific — and discard the third-party discrete-code labels, which assume a shape the data does not have
- [x] 4.3 Make the `gv_mode` to preset lookup total so an unmapped mode cannot destroy a climate or sensor entity, leaving the existing mode mapping unchanged
- [x] 4.4 Gate creation of climate and target-temperature entities on the device supplying *usable* setpoint and range values — treating present-but-null the same as absent, since the reference receiver reports `consigne_confort` and `min_set_point` as null
- [x] 4.5 Derive the device registry model from API data instead of hardcoding `BT-D03-RF` in the entity platforms and `BT-CT02-RF` in `central_unit.py`, leaving it unset when unknown
- [x] 4.6 Devices sharing a zone are named by `nom_appareil`, confirmed to differ between devices in the same zone. The factory default "nouvel appareil" is treated as no name and falls back to the zone label. An opaque device-id fragment was tried first and abandoned as no better than Home Assistant's `_2`
- [x] 4.8 Fixed a null read as a value: the receiver reports `heating_up` as null, and `heating_up != "0"` made its heating sensor report on. Found in a raw payload after sitting unremarked in the project's own test output
- [x] 4.7 Verify every existing `unique_id` format is unchanged

## 5. Availability and battery

- [x] 5.1 Implement the `available` property across all entity classes, replacing the unused `_available` flags
- [x] 5.2 Derive measurement-entity availability from `error_code`, keeping setpoint entities available when their cached setpoints remain valid
- [x] 5.3 Add a temperature plausibility bound as a backstop so unseen sentinels are suppressed without enumerating them
- [x] 5.4 Add a fault entity per device using `BinarySensorDeviceClass.PROBLEM`, carrying the raw error code; do not present it as a battery condition
- [x] 5.5a Answered from the first diagnostics export: there is NO battery field, so a battery entity is not possible and the problem entity stands. Device names DO exist as `nom_appareil` and `label_interface`, which unblocks 4.6. The bit-0 hypothesis remains untestable without a device actually showing a low-battery warning the integration ignores, and test the bit-0 hypothesis: find a thermostat currently showing a low-battery warning on its own screen and read its `error_code`. Bit 0 set confirms a battery signal reaches the API; `0` proves it does not. Either way a genuine battery entity is proposed separately, not added here
- [x] 5.5 Report entities as unavailable when a periodic refresh fails and no device data is available

## 6. Diagnostics

- [x] 6.1 Add `diagnostics.py` with `async_get_config_entry_diagnostics`, including the raw zone and device payloads verbatim
- [x] 6.2 Implement fail-safe redaction for credentials, tokens, MAC addresses, smart home identifiers and device identifiers, structured so an unfamiliar API key cannot leak
- [x] 6.3 Add a test asserting that no credential or token appears in the output, including when the payload carries an unexpected field
- [x] 6.4 Include the integration's interpretation alongside the raw data: decoded values, entities created, and entities skipped with their reason
- [x] 6.5 Log unrecognised error codes, unrecognised `gv_mode` values and missing expected fields once each, and include them in diagnostics
- [x] 6.6 Add `async_get_device_diagnostics` for per-device export

## 7. Verification on the live installation

- [x] 7.1 Confirmed: `Error Logeer kamer` exists and reads "Not reporting". It had never been created before, because the error code is a bitfield the previous lookup could not handle
- [x] 7.2 Confirmed from the diagnostics export, which records the receiver's entities as created and its climate and target-temperature entities as skipped with the reason. Its heating sensor also now reads unavailable rather than a null misread as on
- [x] 7.3 Confirmed: `Air temperature Logeer kamer` reads unavailable rather than 100.2 °C, and `Problem Logeer kamer` reports a problem
- [ ] 7.4 (not observed live) Confirm the climate entity and the target temperature sensor report identical values, and that 20.6 °C is selectable from the thermostat card. Covered by tests, and the disagreement this guards against was found and fixed from a live report
- [ ] 7.5 (not observed live on this release) Set a thermostat to 20.5 °C and confirm `consigne_confort` reads back as exactly `689`. The read half was confirmed earlier in the change from a live reading of `68.9` decoding to 20.5, and the write half is covered by tests against the same values
- [ ] 7.6 (not observed live) Confirm temperature sensors still record to statistics, with the series continuous across the unit change. Statistics were confirmed recording before the change; the reported unit is Celsius either side, so the series is expected to continue, but nobody has watched it
- [x] 7.7 Confirmed across two exports: credentials redacted, identifiers pseudonymised consistently, and no token present. Reviewed by eye before sharing

## 8. Release

- [ ] 8.1 Document the user-visible changes: the 0.5 °C step, devices going unavailable, new battery entities, and any statistics unit prompt
- [ ] 8.2 Update `manifest.json` — bump the version and correct `requirements` if any dependency remains
- [ ] 8.3 Run the existing test suite and the pre-commit hooks
