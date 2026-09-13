![GitHub release](https://img.shields.io/github/release/pwesters/watts_vision.svg) [![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Watts Vision for Home Assistant

These are my first steps in creating an add on for home assistant and learning python. There's a lot left to do, including:
- All the things that aren't default options, like program, stop boost, etc.

I'm learning by doing. Please be kind.

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

Add https://github.com/pwesters/watts_vision to the custom repositories in HACS. A new repository will be found. Click Download and restart Home Assistant. Go to Settings and then to Devices & Services. Click + Add Integration and search for Watts Vision.

## Manual Installation

Copy the watts_vision folder from custom_components to your custom_components folder of your home assistant instance, go to devices & services and click on '+ add integration'. In the new window search for Watts Vision and click on it. Fill out the form with your credentials for the watts vision smart home system.
