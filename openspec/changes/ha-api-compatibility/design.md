## Context

Two Home Assistant interfaces this integration depends on have moved. One has already broken, the other has a date.

```
  config_flow.py:100   self.config_entry = config_entry
                       AttributeError: property 'config_entry' of
                       'OptionsFlowHandler' object has no setter
                       → the options flow is dead TODAY

  device_info          "via_device": (DOMAIN, self.smartHome)
                       in climate.py, sensor.py, binary_sensor.py,
                       central_unit.py
                       → "will stop working in Home Assistant 2027.8.0"
```

Both were announced by Home Assistant in advance, as deprecation warnings in the log. The reference installation shows them plainly. Nobody saw them, because nothing looks.

### Why the drift went unnoticed

```
  .github/workflows/hassfest.yml      validates manifest.json metadata
  .github/workflows/hacs_action.yml   validates HACS repository structure
  ─────────────────────────────────────────────────────────────────────
  neither loads the integration. No workflow runs pytest.
```

`requirements.test.txt` already pulls in `pytest-homeassistant-custom-component`, the tool built precisely for this. Nothing invokes it. `tests/test_init.py` consists entirely of commented-out code — the setup test exists as a ghost of an intention. The only executing test is a partial config flow test, and even that never runs outside a developer's own machine.

So the integration has never been loaded against a current Home Assistant except by its users, and the first report of an incompatibility is a user hitting an error. Both defects in this change are consequences of that, which is why the change is as much about detection as about the two fixes.

Supporting evidence that the environment has moved on: the reference installation's tracebacks run under **Python 3.14**, while `setup.cfg` still declares `python_version = 3.13` for mypy, and pytest is invoked with `--strict`, renamed to `--strict-markers` several releases ago.

## Goals / Non-Goals

**Goals:**

- Restore the options flow.
- Migrate off `via_device` before Home Assistant 2027.8.0, keeping the hub relationship intact.
- Make Home Assistant deprecation warnings from this integration fail a build rather than accumulate in a user's log.
- Have CI actually load the integration.

**Non-Goals:**

- Modern entity naming. `_attr_has_entity_name` with translation keys is the current pattern, and this integration predates it — but adopting it renames entities and breaks automations. It belongs with a change already touching entity identity, not here.
- Comprehensive test coverage. A setup smoke test is enough to make CI meaningful; making the suite genuinely thorough is separate work.
- Any change to entity behaviour, temperature decoding, the API client, or presets. Those are the other three changes.
- Migrating to the Vision+ platform, which the project scope excludes.

## Decisions

### Confirm the `via_device` replacement rather than guess it

The warning says to use `via_device_id` instead, but it is reported against Home Assistant's own internal `device_registry.async_get_or_create` call, not against the `device_info` dictionary this integration writes. An integration supplies `via_device` as an identifier tuple and Home Assistant resolves it; `via_device_id` is a registry-level device id, which an integration does not have at the point it declares `device_info`.

**Chosen:** treat the exact replacement as unknown and confirm it against current Home Assistant developer documentation and a core integration doing the same thing, before writing any code. The requirement in the spec is behavioural — the hub relationship survives without a doomed interface — precisely so the implementation is not locked to a guess.

This is the same discipline the project applies to the Watts API, for the same reason: a plausible-looking guess that turns out wrong is worse than an acknowledged unknown.

### Fail the build on this integration's deprecation warnings

Catching a removal when it is announced rather than when it fires is the whole point. Home Assistant warns for months or years first.

**Chosen:** configure the test run so deprecation warnings attributable to this integration are errors. Warnings from Home Assistant itself or from other components must not fail the build, or the suite becomes noise and gets disabled — which is a worse outcome than the status quo.

Filtering precisely matters. Home Assistant's warnings name the offending file, as both examples here do, so filtering on this integration's path is the natural discriminator.

### A smoke test that loads the integration, not a mock

A test that never instantiates the integration would not have caught either defect. `pytest-homeassistant-custom-component` provides a real `hass` instance.

**Chosen:** at minimum, set up the config entry and open the options flow. The options flow break is invisible to any test that does not open it, which is exactly how it reached a user. The Watts cloud is mocked; the Home Assistant side is real.

### Pin CI to a supported Home Assistant version, and let it move

Pinning forever reproduces the current problem more slowly. Tracking latest means unrelated upstream churn can break the build.

**Chosen:** run against the version `pytest-homeassistant-custom-component` resolves to, and let it float. For a project whose entire purpose is surviving on a platform it does not control, being told early that something moved is the feature, not the nuisance. A pinned second job could be added later if the noise proves unmanageable.

## Risks / Trade-offs

**The `via_device` migration could duplicate devices.** → Device identity is what groups entities and carries their history. Getting the relationship wrong could create a second central unit device, orphaning entities from the original. The spec requires that existing devices are reused; verify on the live installation, which already has devices registered from the current code, rather than only on a clean test instance.

**Failing on deprecation warnings could block unrelated work.** → A newly announced deprecation would turn the build red for a change that has nothing to do with it. That is the intended trade-off — it is how a dated removal gets noticed — but the filter must be narrow enough that only this integration's own warnings count, or the suite gets switched off.

**Letting the Home Assistant version float means CI can break without a code change.** → Accepted deliberately. A project maintaining a legacy integration against a platform it does not control wants that signal. The failure will be informative rather than mysterious, because it will name the interface.

**Restoring `tests/test_init.py` may surface further failures.** → Plausible: nothing has loaded this integration under test for a long time, and the other three changes describe several ways setup misbehaves. Failures found are pre-existing bugs, not regressions from this change, and should be recorded against whichever change owns them rather than expanding this one.

## Migration Plan

1. Delete the `config_entry` assignment and add a test that opens the options flow. Independently shippable, fixes a live user-facing break, one line of production code.
2. Add the CI job running the existing tests plus a setup smoke test. No production code changes.
3. Turn on deprecation-as-error and fix whatever it surfaces beyond the two already known.
4. Migrate `via_device` once the replacement is confirmed, verifying on an installation with existing registered devices.
5. Clean up `CONNECTION_CLASS`, the class shadowing, `data=None`, `--strict`, and the mypy Python version.

Steps 1 and 2 carry almost no risk and deliver most of the value. Step 4 is the one that can damage an existing installation's device registry.

## Open Questions

- **What replaces `via_device` in `device_info`?** Needs confirmation from current Home Assistant documentation and a core integration doing the same thing. Deliberately not guessed.
- **Does `async_create_entry(title="", data=None)` still behave correctly in the options flow?** Entry data is expected to be a mapping. It is not currently throwing, but it may be relying on tolerance that is itself deprecated.
- **Which Home Assistant version is the floor?** The integration declares no minimum. `hacs.json` and `manifest.json` could state one, which would make "supported version" mean something concrete rather than implied.
- **Are there deprecation warnings beyond these two?** The reference installation's log shows only these, but it is one installation exercising one set of code paths. Step 3 will answer it properly.
