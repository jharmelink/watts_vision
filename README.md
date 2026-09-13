![GitHub release](https://img.shields.io/github/release/jharmelink/watts_vision.svg) [![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Watts Vision for Home Assistant

These are my first steps in creating an add on for home assistant and learning python. There's a lot left to do, including:
- All the things that aren't default options, like program, stop boost, etc.

I'm learning by doing. Please be kind.

> **Stopping a boost is done** — see [Boost](#boost) below. Setting a boost's duration works too, rather than always getting two hours.
>
> Program mode can be selected and read, but the weekly schedule itself still cannot be edited from Home Assistant. The schedule turns out to be in the data the integration already receives — 48 half-hour slots across seven days — so it is no longer out of reach, just unwritten.

## Which integration do you need?

This integration is for the **original Watts Vision** system. If you have **Watts Vision+**, use the official [Watts Vision +](https://www.home-assistant.io/integrations/watts/) integration instead — it is built and maintained by Watts, ships with Home Assistant, and needs no HACS.

**Check your central unit**, not your thermostats:

| Your central unit | Use this |
|---|---|
| **BT-CT02-RF** (or older) | This integration |
| **BT-CT03-RF**, **BT-ST03-RF** | The official [Watts Vision +](https://www.home-assistant.io/integrations/watts/) integration |

The central unit is what talks to the Watts cloud, so it decides which system you are on. Thermostat models are not a reliable guide — a BT-D03-RF thermostat works with both generations, but paired to a BT-CT02-RF central unit it can only reach the original platform.

The two systems use completely separate clouds and log-ins, so there is no overlap and nothing to migrate. If the official integration supports your hardware, prefer it.

### A note on support

Watts has moved on to Vision+, and the original platform receives no further attention from them. This integration talks to an undocumented API that can change without warning, and there is nobody upstream to report problems to. It aims to fail visibly rather than silently: when something cannot be read, entities are expected to go *unavailable* rather than show a wrong value.

## Requirements
A Watts Vision system Cental unit is required to be able to see the settings remotely. See [Watts Vision Smart Home](https://wattswater.eu/catalog/regulation-and-control/watts-vision-smart-home/) and watch the [guide on youtube (Dutch)](https://www.youtube.com/watch?v=BLNqxkH7Td8).

## HACS

Add https://github.com/jharmelink/watts_vision to the custom repositories in HACS. A new repository will be found. Click Download and restart Home Assistant. Go to Settings and then to Devices & Services. Click + Add Integration and search for Watts Vision.

## Manual Installation

Copy the watts_vision folder from custom_components to your custom_components folder of your home assistant instance, go to devices & services and click on '+ add integration'. In the new window search for Watts Vision and click on it. Fill out the form with your credentials for the watts vision smart home system.

## What you get

A device per thermostat, grouped under a device for the central unit, with:

| Entity | What it is |
|---|---|
| Thermostat | Target temperature and preset mode. Setpoints step by 0.1 °C |
| Air temperature | What the device measures |
| Target temperature | The setpoint of whichever mode is active |
| Heating mode | Comfort, eco, frost protection, boost, program, off |
| Heating | Whether the device is currently calling for heat |
| Problem | Whether the device is reporting a fault |
| Error | What that fault is, with the raw code as an attribute |

The central unit also gets a **Last communication** sensor.

Not every device the central unit reports is a thermostat. A receiver has no setpoints, so it gets the entities that make sense for it and no thermostat. Where an entity is deliberately absent, the reason is in the log and in diagnostics.

## When something is wrong

Entities go **unavailable** rather than showing a wrong value. A device with a flat battery or a hardware fault stops reporting a temperature, and its *Problem* sensor turns on — so nothing invents a reading, and nothing lands in your long-term statistics that was never measured.

The fault code is a bitfield and this integration only claims to understand the values it has evidence for. Anything else reads as *Unrecognised fault*, with the raw number kept as an attribute so it can be reported rather than guessed at.

## Boost

A boost heats at the boost setpoint for a while and then returns to whatever was running before. Selecting the **boost** preset still gives the two hours this integration has always sent, but you can now choose:

```yaml
action: watts_vision.start_boost
target:
  entity_id: climate.thermostat_woonkamer
data:
  duration: 45        # minutes
```

And end one early, which previously meant selecting another preset — and that also rewrote the preset's setpoint, which was rarely what anyone wanted:

```yaml
action: watts_vision.stop_boost
target:
  entity_id: climate.thermostat_woonkamer
```

Stopping returns the thermostat to the mode that was active before the boost, without changing that mode's temperature. If nothing remembers what that was — after a Home Assistant restart, say — it returns to comfort.

While a boost is running, the thermostat's `boost_seconds_remaining` attribute counts it down.

## Diagnostics

Settings → Devices & Services → Watts Vision → ⋮ → **Download diagnostics**, or the same menu on an individual device.

Because the API is undocumented, the export includes the raw device payloads as they arrive, alongside what the integration made of them and which entities it created or skipped. That is usually enough to explain any surprise without anyone having to reproduce it.

Credentials are removed and identifiers are replaced with consistent stand-ins, so devices can still be told apart. Have a look before sharing it anyway.
