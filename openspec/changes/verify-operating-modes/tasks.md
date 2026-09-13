## 1. Prerequisites

- [ ] 1.1 Confirm `fix-temperature-and-device-health` has landed, so an unmapped `gv_mode` can no longer destroy an entity
- [ ] 1.2 Confirm diagnostics are available, so each observation is one download rather than a hand-written template
- [ ] 1.3 Choose a test device in a room where an unexpected heating mode does no harm, and record its starting mode and every setpoint so the state can be restored

## 2. Establish ground truth on hardware

- [ ] 2.1 From the **physical thermostat**, not through Home Assistant, put the test device into each mode its screen offers in turn
- [ ] 2.2 For each mode, record the raw `gv_mode`, every `consigne_*` value, `time_boost`, `nv_mode`, and what the device's own display says
- [ ] 2.3 Note any `gv_mode` value outside the known set `0, 1, 2, 3, 4, 8, 11`
- [ ] 2.4 Determine what distinguishes `gv_mode` `8` from `11`, both currently labelled program
- [ ] 2.5 Write the confirmed mapping into `const.py` with provenance marking each entry confirmed or unverified
- [ ] 2.6 Restore the test device to its recorded starting state

## 3. Resolve or record the dispute

- [ ] 3.1 Compare the observed mapping against the current one and against the Homey app's
- [ ] 3.2 If the current mapping is confirmed, record that the dispute is settled and why
- [ ] 3.3 If it is wrong, do not fix it here — raise a separate breaking change naming every preset that changes meaning, since automations reference them

## 4. Mode write handling

- [ ] 4.1 Decide what program mode should write, then either add the missing `gv_mode 8` branch or stop the caller computing a setpoint that is discarded
- [ ] 4.2 Add a test asserting every preset the entity offers produces a defined request, so no mode can fall through to an empty payload again
- [ ] 4.3 Fix `async_set_temperature` so it updates only the active mode's setpoint in the cache, not `consigne_confort` unconditionally
- [ ] 4.4 Add a test that setting a target while in eco leaves the comfort setpoint untouched

## 5. Frost protection

- [ ] 5.1 Try writing a frost-protection temperature other than 7.0 °C on hardware and record whether the device accepts it
- [ ] 5.2 If accepted, stop hardcoding `446` and let the user choose within the device's reported range
- [ ] 5.3 If refused, keep the fixed value but refuse the request with a reason instead of substituting silently
- [ ] 5.4 Remove the forced 7.0 °C `min_temp`/`max_temp` override in `climate.py`, or justify it from the device's reported limits

## 6. Boost

- [ ] 6.1 Add a service to start a boost with a caller-supplied duration, replacing the hardcoded `time_boost` of 7200
- [ ] 6.2 Document the default duration used when the plain boost preset is selected without a service call
- [ ] 6.3 Add a service to stop a boost, returning the device to the mode active before it without writing a setpoint
- [ ] 6.4 Fall back to a documented default mode when the previous mode is unknown, such as after a restart
- [ ] 6.5 Expose the remaining boost time from `time_boost`
- [ ] 6.6 Add `services.yaml` entries and translations for both services

## 7. Record what stays unknown

- [ ] 7.1 Record observed behaviour of `nv_mode` versus `gv_mode`, or that nothing was learned
- [ ] 7.2 Record whether the `peremption` difference for frost protection has any observable effect
- [ ] 7.3 Update the README's outstanding-work list to reflect what this change closed

## 8. Release

- [ ] 8.1 Run the existing test suite and the pre-commit hooks
- [ ] 8.2 Verify on the live installation that every preset still behaves as before for the modes that were already working
- [ ] 8.3 Document the new services and any changed frost-protection behaviour
- [ ] 8.4 Bump the version in `manifest.json`
