"""Tests for the Watts Vision API client.

The client's contract is that every failure leaves it as a `WattsVisionError`
and every success returns a value. Callers previously had to distinguish a
failure from an empty result by inspecting `None`, and transport failures
escaped as `requests` exceptions nobody caught.
"""
from datetime import datetime, timedelta
import logging
import threading
from unittest.mock import Mock, patch

import pytest
import requests

from custom_components.watts_vision.exceptions import (
    WattsVisionApiError,
    WattsVisionAuthError,
    WattsVisionConnectionError,
    WattsVisionTokenRejected,
)
from custom_components.watts_vision.watts_api import WattsApi

PASSWORD = "a-very-secret-password"

TOKEN_RESPONSE = {
    "access_token": "token-1",
    "expires_in": 300,
    "refresh_token": "refresh-1",
    "refresh_expires_in": 1800,
}


def build_client(hass=None) -> WattsApi:
    """Return a client with no token yet acquired."""
    return WattsApi(hass, "user@example.com", PASSWORD)


def response(status: int = 200, json_body: dict | None = None) -> Mock:
    """Return a stand-in for a requests Response."""
    mock = Mock()
    mock.status_code = status
    mock.json.return_value = json_body or {}
    return mock


def ok_body(data: dict | None = None) -> dict:
    return {"code": {"code": "1", "key": "OK", "value": "ok"}, "data": data or {}}


# ─── Token acquisition ─────────────────────────────────────────────────────


def test_login_returns_the_token():
    client = build_client()
    with patch("requests.post", return_value=response(200, TOKEN_RESPONSE)):
        assert client.getLoginToken() == "token-1"


def test_a_valid_token_is_reused_without_a_request():
    client = build_client()
    with patch("requests.post", return_value=response(200, TOKEN_RESPONSE)) as post:
        client.getLoginToken()
        client.getLoginToken()
    assert post.call_count == 1


def test_rejected_credentials_raise_auth_error():
    client = build_client()
    with patch("requests.post", return_value=response(401)):
        with pytest.raises(WattsVisionAuthError):
            client.getLoginToken()


def test_unreachable_cloud_raises_connection_error():
    """The 2026-09-11 outage sent this straight through to entity updates."""
    client = build_client()
    with patch(
        "requests.post", side_effect=requests.exceptions.ConnectionError("no dns")
    ):
        with pytest.raises(WattsVisionConnectionError):
            client.getLoginToken()


def test_a_timeout_raises_connection_error():
    client = build_client()
    with patch("requests.post", side_effect=requests.exceptions.Timeout("slow")):
        with pytest.raises(WattsVisionConnectionError):
            client.getLoginToken()


def test_every_request_carries_a_timeout():
    """A hung connection must not pin an executor thread forever."""
    client = build_client()
    with patch("requests.post", return_value=response(200, TOKEN_RESPONSE)) as post:
        client.getLoginToken()
    assert post.call_args.kwargs["timeout"] > 0


def test_token_acquisition_raises_no_typeerror_or_nameerror():
    """`raise None` raised TypeError; an unbound payload raised NameError.

    Both were reachable in ordinary use. Neither may come back.
    """
    client = build_client()
    for outcome in (
        response(401),
        response(500),
        response(200, TOKEN_RESPONSE),
    ):
        with patch("requests.post", return_value=outcome):
            try:
                client.getLoginToken(forcelogin=True)
            except (TypeError, NameError) as err:  # pragma: no cover - the bug
                pytest.fail(f"token acquisition raised {type(err).__name__}: {err}")
            except WattsVisionAuthError:
                pass


def test_a_successful_retry_reports_success():
    """The config flow bug: a successful retry used to report failure.

    `getLoginToken` returned None because the retry branch omitted `return`, so
    `test_authentication` concluded that valid credentials were invalid.
    """
    client = build_client()
    client._refresh_token = "refresh-0"
    client._refresh_expires_in = datetime.now() + timedelta(hours=1)

    # The refresh is refused, the full login that follows succeeds.
    with patch(
        "requests.post",
        side_effect=[response(401), response(200, TOKEN_RESPONSE)],
    ):
        assert client.getLoginToken() == "token-1"


def test_test_authentication_is_true_for_good_credentials():
    client = build_client()
    with patch("requests.post", return_value=response(200, TOKEN_RESPONSE)):
        assert client.test_authentication() is True


def test_rejected_credentials_are_not_retried():
    """Repeated failed logins risk locking the account, so a refusal is final.

    The original code retried a failed login blindly, then discarded the result
    of the retry. Both halves of that are gone: the retry because it is unsafe,
    and the discarded result because it told users with valid credentials that
    they were invalid.
    """
    client = build_client()
    with patch("requests.post", return_value=response(401)) as post:
        assert client.test_authentication() is False
    assert post.call_count == 1


def test_test_authentication_is_false_when_credentials_are_wrong():
    client = build_client()
    with patch("requests.post", return_value=response(401)):
        assert client.test_authentication() is False


def test_concurrent_expiry_produces_one_login():
    """Entity updates and the refresh timer can arrive at the same instant."""
    client = build_client()
    barrier = threading.Barrier(5)

    def slow_post(*args, **kwargs):
        return response(200, TOKEN_RESPONSE)

    with patch("requests.post", side_effect=slow_post) as post:

        def worker():
            barrier.wait()
            client.getLoginToken()

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert post.call_count == 1


def test_credentials_never_reach_the_log(caplog: pytest.LogCaptureFixture):
    client = build_client()
    caplog.set_level(logging.DEBUG)

    with patch("requests.post", return_value=response(401)):
        client.test_authentication()
    with patch("requests.post", return_value=response(200, TOKEN_RESPONSE)):
        client.getLoginToken()

    assert PASSWORD not in caplog.text
    assert "user@example.com" not in caplog.text
    assert "token-1" not in caplog.text


# ─── Data requests ─────────────────────────────────────────────────────────


def authenticated_client() -> WattsApi:
    client = build_client()
    client._token = "token-1"
    client._token_expires = datetime.now() + timedelta(hours=1)
    return client


def test_a_successful_request_returns_data():
    client = authenticated_client()
    body = ok_body({"smarthomes": [{"smarthome_id": "sh1"}]})
    with patch("requests.post", return_value=response(200, body)):
        assert client.loadSmartHomes() == [{"smarthome_id": "sh1"}]


def test_an_error_code_in_a_well_formed_response_raises():
    client = authenticated_client()
    body = {"code": {"code": "7", "key": "KO", "value": "nope"}, "data": None}
    with patch("requests.post", return_value=response(200, body)):
        with pytest.raises(WattsVisionApiError) as err:
            client.loadSmartHomes()
    # The raw values are all a user of an undocumented API can report.
    assert "7" in str(err.value)
    assert "nope" in str(err.value)


def test_the_failing_operation_is_named():
    """`check_response` said "fetching user data" whatever had failed."""
    client = authenticated_client()
    with patch("requests.post", return_value=response(500)):
        with pytest.raises(WattsVisionApiError) as err:
            client.pushTemperature("sh1", "dev1", "689", "0")
    assert "setpoint" in str(err.value)


def test_a_rejected_token_is_retried_once():
    client = authenticated_client()
    responses = [
        response(401),
        response(200, TOKEN_RESPONSE),
        response(200, ok_body({"zones": []})),
    ]
    with patch("requests.post", side_effect=responses):
        assert client.loadDevices("sh1") == []


def test_a_token_rejected_twice_gives_up():
    """No unbounded recursion, and no endless login attempts."""
    client = authenticated_client()
    responses = [
        response(401),
        response(200, TOKEN_RESPONSE),
        response(401),
    ]
    with patch("requests.post", side_effect=responses):
        with pytest.raises(WattsVisionTokenRejected):
            client.loadDevices("sh1")


def test_a_failed_refresh_does_not_report_success():
    """`reloadDevices` returned True even when every load had failed."""
    client = authenticated_client()
    client._smartHomeData = [{"smarthome_id": "sh1"}]
    with patch(
        "requests.post", side_effect=requests.exceptions.ConnectionError("no dns")
    ):
        with pytest.raises(WattsVisionConnectionError):
            client.reloadDevices()


def test_getdevice_returns_none_when_not_cached():
    """A cache miss is an answer, not a failure, and stays a `None`."""
    client = authenticated_client()
    client._smartHomeData = [
        {"smarthome_id": "sh1", "zones": [{"devices": [{"id": "dev1"}]}]}
    ]
    assert client.getDevice("sh1", "dev1") == {"id": "dev1"}
    assert client.getDevice("sh1", "nope") is None
    assert client.getDevice("other", "dev1") is None
