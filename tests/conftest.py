"""Fixtures for testing the Watts Vision component."""
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom integrations in every test.

    Without this, Home Assistant refuses to set up anything under
    custom_components and every setup test fails for the wrong reason.
    """
    yield
