"""Guard against Home Assistant interfaces this integration uses going away.

Home Assistant announces removals as warnings long before they take effect. The
two that reached users -- the options flow break and `via_device` -- were both
announced and both sat unread in a log, because nothing ran this code before
release. These tests turn that announcement into a failing build.

Deprecations from the frame helper arrive as log records rather than as Python
warnings, so `filterwarnings` does not see them and `caplog` is the only place
they can be caught.
"""
import logging

from homeassistant.core import HomeAssistant
import pytest

from custom_components.watts_vision.const import DOMAIN

from . import init_integration

# Home Assistant reports a custom integration's misuse of a deprecated API
# through this logger, naming the integration and the offending call.
FRAME_HELPER_LOGGER = "homeassistant.helpers.frame"


def _our_deprecation_reports(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return deprecation reports that name this integration.

    Narrow on purpose. A warning from Home Assistant itself or from another
    component must not fail this build -- a suite that goes red for someone
    else's reasons is a suite people learn to ignore, which is how the two
    known deprecations got as far as they did.
    """
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
        and record.name == FRAME_HELPER_LOGGER
        and DOMAIN in record.getMessage()
    ]


async def test_setup_reports_no_deprecated_api_use(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
):
    """Setting up the integration uses no interface Home Assistant has deprecated."""
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        await init_integration(hass, with_devices=True)

    reports = _our_deprecation_reports(caplog)

    assert not reports, "Home Assistant reported deprecated API use:\n" + "\n".join(
        reports
    )


async def test_other_components_do_not_fail_this_build(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
):
    """A deprecation from elsewhere is ignored by the filter above.

    Confirms the guard is narrow enough to be trustworthy, rather than a
    tripwire that fires on unrelated platform churn.
    """
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        logging.getLogger(FRAME_HELPER_LOGGER).warning(
            "Detected that custom integration 'some_other_thing' calls a "
            "deprecated thing"
        )

    assert not _our_deprecation_reports(caplog)
