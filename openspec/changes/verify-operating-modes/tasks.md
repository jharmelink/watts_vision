## 1. Prerequisites

- [x] 1.1 Confirmed: fix-temperature-and-device-health is released as 0.5.0 and archived, so an unmapped mode can no longer destroy an entity
- [x] 1.2 Confirmed: diagnostics shipped in 0.5.0, and two exports have already been taken
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

- [x] 4.1 Decided: in program mode the weekly schedule owns the setpoint, so none is sent. `gv_mode 8` now has an explicit branch saying that, rather than falling through the chain to an empty payload while its caller computed a value that was discarded. `gv_mode 11` keeps writing `consigne_manuel`, which reads as a manual override of a running programme
- [x] 4.2 Added, including one asserting program mode sends no `consigne_*` at all
- [x] 4.3 Done in fix-temperature-and-device-health: only the active mode's setpoint is written to the cache
- [x] 4.4 Done in fix-temperature-and-device-health

## 5. Frost protection

- [ ] 5.1 Try writing a frost-protection temperature other than 7.0 °C on hardware and record whether the device accepts it
- [ ] 5.2 If accepted, stop hardcoding `446` and let the user choose within the device's reported range
- [ ] 5.3 If refused, keep the fixed value but refuse the request with a reason instead of substituting silently
- [x] 5.4 Done in fix-temperature-and-device-health: limits come from the device's own `min_set_point` and `max_set_point`

## 6. Boost

- [x] 6.1 Added `watts_vision.start_boost` with a duration in minutes, replacing the hardcoded 7200 seconds
- [x] 6.2 Two hours, matching what the integration always sent, documented in the code, the service description and the release notes
- [x] 6.3 Added `watts_vision.stop_boost`. It returns to the mode active before the boost and re-sends the setpoint that mode already holds, so nothing changes -- whether the API accepts a mode change carrying no setpoint is unknown and not worth discovering on a live heating system
- [x] 6.4 Falls back to comfort when nothing remembers the previous mode, as after a restart: it is the mode a thermostat is normally in and cannot leave a room unheated by accident
- [x] 6.5 Exposed as `boost_seconds_remaining` on the climate entity, from `time_boost`
- [x] 6.6 Added, with English and Dutch translations

## 7. Record what stays unknown

- [x] 7.1 Recorded from the diagnostics export: `nv_mode` equals `gv_mode` on all nine devices, so nothing distinguishes them in practice and nothing depends on the difference
- [ ] 7.2 Record whether the `peremption` difference for frost protection has any observable effect
- [x] 7.3 README updated: stopping a boost and choosing its duration are documented as done, and the programme field is recorded as reachable but unwritten. The author's own list is left as he wrote it, with a note beneath

## 8. Release

- [x] 8.1 103 tests pass and all seven pre-commit hooks pass
- [ ] 8.2 Verify on the live installation that every preset still behaves as before for the modes that were already working
- [x] 8.3 Documented in the README and in the service descriptions. Frost protection behaviour is unchanged, pending the hardware test
- [ ] 8.4 Bump the version in `manifest.json`
