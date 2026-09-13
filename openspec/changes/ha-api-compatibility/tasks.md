## 1. Fix the live break

- [ ] 1.1 Delete the `self.config_entry = config_entry` assignment in `OptionsFlowHandler.__init__`, which raises `AttributeError` on current Home Assistant
- [ ] 1.2 Confirm the options flow still reaches `self.config_entry` correctly through the base class
- [ ] 1.3 Add a test that opens the options flow and submits changed credentials — the defect is invisible to any test that never opens it
- [ ] 1.4 Verify on the live installation that the integration's options can be opened and credentials changed

## 2. Make CI run the code

- [ ] 2.1 Add a workflow that installs `requirements.test.txt` and runs pytest on every push and pull request
- [ ] 2.2 Restore `tests/test_init.py`, which currently contains only commented-out code, as a real setup test
- [ ] 2.3 Add a smoke test that sets up the config entry against a real `hass` instance with the Watts cloud mocked
- [ ] 2.4 Replace the deprecated `--strict` pytest option in `setup.cfg` with `--strict-markers`
- [ ] 2.5 Update the mypy `python_version` in `setup.cfg`, which declares 3.13 while the reference installation runs 3.14

## 3. Catch drift automatically

- [ ] 3.1 Configure the test run so Home Assistant deprecation warnings originating from this integration are errors
- [ ] 3.2 Confirm the filter is narrow enough that warnings from Home Assistant or other components do not fail the build
- [ ] 3.3 Fix whatever deprecations this surfaces beyond the two already known, or record them against the change that owns them
- [ ] 3.4 Add a test asserting that setting up the integration produces no deprecation warning from its own code

## 4. Migrate off via_device

- [ ] 4.1 Confirm from current Home Assistant documentation and a core integration what replaces `via_device` in `device_info` — do not guess, since the warning names an internal registry parameter an integration does not supply directly
- [ ] 4.2 Apply the confirmed replacement in `climate.py`, `sensor.py`, `binary_sensor.py` and `central_unit.py`
- [ ] 4.3 Verify sub-devices still appear grouped under the central unit
- [ ] 4.4 Verify on an installation with devices already registered that no duplicate device entries are created and no entity loses its history
- [ ] 4.5 Confirm the deprecation warning no longer appears

## 5. Remove vestigial platform API

- [ ] 5.1 Remove `CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL` and its import; `iot_class` in `manifest.json` already carries this
- [ ] 5.2 Stop shadowing the imported `ConfigFlow` base class with the subclass of the same name
- [ ] 5.3 Check whether `async_create_entry(title="", data=None)` in the options flow should pass a mapping rather than `None`

## 6. Release

- [ ] 6.1 Run the full test suite and the pre-commit hooks
- [ ] 6.2 Consider declaring a minimum supported Home Assistant version in `manifest.json` and `hacs.json`, so "supported version" is stated rather than implied
- [ ] 6.3 Bump the version in `manifest.json`
- [ ] 6.4 Note the restored options flow in the release description, since affected users currently cannot change credentials at all
