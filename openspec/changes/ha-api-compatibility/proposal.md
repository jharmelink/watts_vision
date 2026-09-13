## Why

The options flow is **broken right now**. Opening the integration's configuration raises:

```
File "custom_components/watts_vision/config_flow.py", line 100, in __init__
    self.config_entry = config_entry
AttributeError: property 'config_entry' of 'OptionsFlowHandler' object has no setter
```

Home Assistant made `config_entry` a read-only property on `OptionsFlow`; assigning it now fails. A user cannot change their username or password through the interface. The fix is deleting one line.

A second break has a date on it. Every platform passes `via_device` in its `device_info`, and Home Assistant warns this "will stop working in Home Assistant 2027.8.0". When it does, the relationship between the central unit and its thermostats breaks.

The underlying reason both drifted unnoticed is that **nothing runs this integration's code before release**. CI has two jobs — hassfest and HACS validation — and neither executes the integration. `tests/test_init.py` is commented out in its entirety, so the only real test is a partial config flow test, and no workflow runs pytest at all. Home Assistant's own deprecation warnings, which announced both of these well in advance, had nowhere to be seen.

## What Changes

**Fix what is broken**

- Remove the `config_entry` assignment in `OptionsFlowHandler.__init__`. The base class supplies it.
- Replace the deprecated `via_device` usage so the central unit remains the parent device of its thermostats, without relying on an API that stops working in Home Assistant 2027.8.0. The correct replacement must be confirmed against current Home Assistant documentation rather than guessed.

**Remove vestigial API usage**

- `CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL` in the config flow. The connection class moved into `manifest.json` as `iot_class`, which is already set correctly to `cloud_polling`.
- `class ConfigFlow(ConfigFlow, domain=DOMAIN)` shadows the imported base class with the subclass name, which works but obscures which is which.
- The options flow calls `async_create_entry(title="", data=None)`. Entry data is expected to be a mapping; `None` should be verified against current behaviour.

**Make drift visible**

- Add a CI job that actually runs the test suite against a supported Home Assistant version. `requirements.test.txt` already pulls in `pytest-homeassistant-custom-component`; nothing invokes it.
- Fail the test suite on Home Assistant deprecation warnings originating from this integration, so a dated removal is caught when it is announced rather than when it fires.
- Restore a real setup test. `tests/test_init.py` contains nothing but commented-out code.
- `setup.cfg` passes `--strict` to pytest, which has been renamed `--strict-markers`.
- `setup.cfg` declares `python_version = 3.13` for mypy, while Home Assistant is running Python 3.14 on the reference installation.

## Capabilities

### New Capabilities

- `ha-compatibility`: the integration's obligations toward the Home Assistant APIs it builds on — that it uses no interface past its removal, that user-facing flows keep working across upgrades, and that drift is detected automatically rather than by a user hitting an error.

### Modified Capabilities

None. The other active changes describe the integration's own behaviour and say nothing about the platform interfaces it consumes.

## Impact

**Code**

- `custom_components/watts_vision/config_flow.py` — the options flow break, `CONNECTION_CLASS`, the class shadowing, `data=None`
- `custom_components/watts_vision/climate.py`, `sensor.py`, `binary_sensor.py`, `central_unit.py` — `via_device` in every `device_info`
- `.github/workflows/` — a new job that runs the tests
- `tests/test_init.py` — currently empty of live code
- `setup.cfg` — pytest and mypy settings

**Relationship to the other changes**

Independent of all three. It touches the config flow and the device registry, not temperature decoding, the API client, or operating modes. It is the smallest of the four and contains the only defect a user is hitting today, so it is a reasonable one to ship first.

The CI job it adds benefits every subsequent change, since none of the other three currently has a way to run its tests automatically.

**User-visible**

- The integration's options can be opened and credentials changed again.
- No behaviour change to entities, temperatures, or presets.

**Not changed**

- No migration to modern entity naming (`_attr_has_entity_name` with translation keys). That would rename entities and break automations, and it belongs with a change that is already touching entity identity.
- No broadening of test coverage beyond a setup smoke test. Making the suite meaningful is worthwhile but is not what this change is for.
