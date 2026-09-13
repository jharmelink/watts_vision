"""Client for the Watts Vision cloud API.

The API is undocumented and unreachable: there is no specification, no contact
with its developers and no notice of change. The client's job is therefore to
fail in ways a caller can act on, never to guess and never to hide a problem.

Every failure leaves here as a `WattsVisionError`. No `requests` exception is
allowed past this module.
"""
from datetime import datetime, timedelta
import logging
import threading

from homeassistant.core import HomeAssistant
import requests

from .exceptions import (
    WattsVisionApiError,
    WattsVisionAuthError,
    WattsVisionConnectionError,
    WattsVisionError,
    WattsVisionTokenRejected,
)

_LOGGER = logging.getLogger(__name__)

TOKEN_URL = (
    "https://auth.smarthome.wattselectronics.com"
    "/realms/watts/protocol/openid-connect/token"
)
BASE_URL = "https://smarthome.wattselectronics.com/api/v0.1/human"
CLIENT_ID = "app-front"

# Comfortably longer than any observed response, and well short of the 120
# second poll interval so a hung request cannot overlap the next one. Chosen
# without measurements; see the open questions in the change design.
REQUEST_TIMEOUT = 30

# The cloud is asked for Dutch; kept as-is because the wire format is out of
# scope for this module's error handling.
LANG = "nl_NL"


class WattsApi:
    """Interface to the Watts API."""

    def __init__(self, hass: HomeAssistant, username: str, password: str):
        """Init the client."""
        self._hass = hass
        self._username = username
        self._password = password
        self._token = None
        self._token_expires = None
        self._refresh_token = None
        self._refresh_expires_in = None
        self._smartHomeData = []
        # Entity updates and the refresh timer both reach this client from
        # executor threads. The lock covers token acquisition only: holding it
        # across data requests would make every entity queue behind every other.
        self._token_lock = threading.Lock()

    # ─── Authentication ────────────────────────────────────────────────────

    def test_authentication(self) -> bool:
        """Return whether the stored credentials are accepted.

        Kept as a boolean for callers that only need a yes or no. Anything that
        must tell a wrong password from an unreachable cloud should call
        `getLoginToken` and catch instead.
        """
        try:
            return self.getLoginToken(forcelogin=True) is not None
        except WattsVisionError:
            return False

    def getLoginToken(self, forcelogin: bool = False) -> str:
        """Return a valid access token, acquiring one if necessary.

        Every path either returns a token or raises. Callers previously had to
        cope with `None` being returned after a *successful* retry, which is
        what told users with valid credentials that they were invalid.
        """
        with self._token_lock:
            now = datetime.now()

            # Re-checked inside the lock so threads queued behind the winner
            # reuse the token it obtained rather than requesting another.
            if not forcelogin and self._token_is_valid(now):
                return self._token

            if not forcelogin and self._can_refresh(now):
                try:
                    return self._request_token(self._refresh_payload(), "refresh")
                except (WattsVisionAuthError, WattsVisionTokenRejected):
                    _LOGGER.debug(
                        "Refresh token was not accepted, falling back to login"
                    )

            return self._request_token(self._login_payload(), "login")

    def _token_is_valid(self, now: datetime) -> bool:
        return bool(self._token and self._token_expires and self._token_expires > now)

    def _can_refresh(self, now: datetime) -> bool:
        return bool(
            self._refresh_token
            and self._refresh_expires_in
            and self._refresh_expires_in > now
        )

    def _login_payload(self) -> dict:
        return {
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
            "client_id": CLIENT_ID,
        }

    def _refresh_payload(self) -> dict:
        return {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": CLIENT_ID,
        }

    def _request_token(self, payload: dict, operation: str) -> str:
        """Exchange a payload for a token. Must be called holding the lock.

        The payload carries the password or the refresh token, so it is never
        logged, at any level.
        """
        now = datetime.now()
        try:
            response = requests.post(
                url=TOKEN_URL, data=payload, timeout=REQUEST_TIMEOUT
            )
        except requests.exceptions.RequestException as err:
            raise WattsVisionConnectionError(
                f"Could not reach the Watts cloud to {operation}"
            ) from err

        if response.status_code != 200:
            raise WattsVisionAuthError(
                f"Watts cloud refused to {operation} "
                f"(status {response.status_code})"
            )

        data = response.json()
        self._token = data["access_token"]
        self._token_expires = now + timedelta(seconds=data["expires_in"])
        self._refresh_token = data["refresh_token"]
        self._refresh_expires_in = now + timedelta(seconds=data["refresh_expires_in"])
        _LOGGER.debug(
            "Access token acquired by %s, refresh valid until %s",
            operation,
            self._refresh_expires_in,
        )
        return self._token

    # ─── Requests ──────────────────────────────────────────────────────────

    def _post(self, operation: str, path: str, query: dict, retry: bool = True) -> dict:
        """Make an authenticated request and return its data.

        Owns the timeout, the response check and the one-shot
        re-authenticate-and-retry, so no public method has to repeat any of it.
        `operation` names the caller so a log entry says what actually failed.
        """
        token = self.getLoginToken()
        payload = {"token": "true", "lang": LANG, **query}

        try:
            response = requests.post(
                url=f"{BASE_URL}{path}",
                headers={"Authorization": f"Bearer {token}"},
                data=payload,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise WattsVisionConnectionError(
                f"Could not reach the Watts cloud for {operation}"
            ) from err

        if response.status_code == 401:
            if retry:
                _LOGGER.debug("Token rejected for %s, re-authenticating", operation)
                self.getLoginToken(forcelogin=True)
                return self._post(operation, path, query, retry=False)
            raise WattsVisionTokenRejected(
                f"Watts cloud rejected the access token for {operation}"
            )

        if response.status_code != 200:
            raise WattsVisionApiError(
                f"Watts cloud returned status {response.status_code} "
                f"for {operation}"
            )

        result = response.json()
        code = result.get("code") or {}
        if "OK" not in str(code.get("key", "")):
            raise WattsVisionApiError(
                f"Watts cloud reported an error for {operation}: "
                f"code {code.get('code')}, key {code.get('key')}, "
                f"value {code.get('value')}"
            )

        return result

    # ─── Data ──────────────────────────────────────────────────────────────

    def loadData(self):
        """Load smart homes and their devices."""
        self._smartHomeData = self.loadSmartHomes()
        return self.reloadDevices()

    def loadSmartHomes(self):
        """Load the user's smart homes."""
        result = self._post(
            "loading smart homes", "/user/read/", {"email": self._username}
        )
        return result["data"]["smarthomes"]

    def loadDevices(self, smarthome: str):
        """Load the zones, and their devices, for one smart home."""
        result = self._post(
            "loading devices", "/smarthome/read/", {"smarthome_id": smarthome}
        )
        return result["data"]["zones"]

    def reloadDevices(self) -> bool:
        """Refresh the devices of every smart home.

        Raises rather than reporting success when a load fails, so a caller
        cannot mistake stale cached data for a completed refresh.
        """
        for smart_home in self._smartHomeData or []:
            smart_home["zones"] = self.loadDevices(smart_home["smarthome_id"])
        return True

    def getSmartHomes(self):
        """Return the cached smart homes."""
        return self._smartHomeData

    def getDevice(self, smarthome: str, deviceId: str):
        """Return a cached device, or None when it is not present.

        A lookup rather than a request: `None` here means the device is not in
        the cache, which is a legitimate answer, not a failure to report.
        """
        for smart_home in self._smartHomeData or []:
            if smart_home["smarthome_id"] != smarthome:
                continue
            for zone in smart_home.get("zones") or []:
                for device in zone.get("devices") or []:
                    if device["id"] == deviceId:
                        return device
        return None

    def setDevice(self, smarthome: str, deviceId: str, newState: str):
        """Replace a cached device, returning it, or None when not present."""
        for smart_home in self._smartHomeData or []:
            if smart_home["smarthome_id"] != smarthome:
                continue
            for zone in smart_home.get("zones") or []:
                devices = zone.get("devices") or []
                for index, device in enumerate(devices):
                    if device["id"] == deviceId:
                        devices[index] = newState
                        return devices[index]
        return None

    def pushTemperature(
        self, smarthome: str, deviceID: str, value: str, gvMode: str
    ) -> bool:
        """Send a setpoint and mode to a device."""
        query = {
            "context": "1",
            "smarthome_id": smarthome,
            "query[id_device]": deviceID,
            "query[time_boost]": "0",
            "query[gv_mode]": gvMode,
            "query[nv_mode]": gvMode,
            "peremption": "15000",
        }
        extra = {}
        if gvMode == "0":
            extra = {
                "query[consigne_confort]": value,
                "query[consigne_manuel]": value,
            }
        elif gvMode == "1":
            extra = {"query[consigne_manuel]": "0"}
        elif gvMode == "2":
            extra = {
                "query[consigne_hg]": "446",
                "query[consigne_manuel]": "446",
                "peremption": "20000",
            }
        elif gvMode == "3":
            extra = {
                "query[consigne_eco]": value,
                "query[consigne_manuel]": value,
            }
        elif gvMode == "4":
            extra = {
                "query[time_boost]": "7200",
                "query[consigne_boost]": value,
                "query[consigne_manuel]": value,
            }
        elif gvMode == "11":
            extra = {"query[consigne_manuel]": value}
        query.update(extra)

        self._post("pushing a setpoint", "/query/push/", query)
        return True

    def getLastCommunication(self, smarthome: str):
        """Return how long ago the central unit last reached the cloud."""
        result = self._post(
            "checking the last communication",
            "/sandbox/check_last_connexion/",
            {"smarthome_id": smarthome},
        )
        return result["data"]
