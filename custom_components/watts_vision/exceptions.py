"""Errors raised by the Watts Vision API client.

Four classes, because four are the distinctions a caller acts on differently:

    WattsVisionAuthError        the credentials are wrong; do not retry
    WattsVisionTokenRejected    the token was refused; re-authenticate once
    WattsVisionConnectionError  the cloud is unreachable; try again next poll
    WattsVisionApiError         the cloud answered, and said no

Everything the client raises derives from `WattsVisionError`, and no `requests`
exception is allowed past the client boundary, so a caller never has to know
which HTTP library is underneath.
"""
from homeassistant.exceptions import HomeAssistantError


class WattsVisionError(HomeAssistantError):
    """Base class for every error raised by the Watts Vision client."""


class WattsVisionAuthError(WattsVisionError):
    """The supplied credentials were rejected.

    Retrying with the same credentials will fail the same way, and repeated
    failed logins risk locking the user's account, so this is never retried.
    """


class WattsVisionTokenRejected(WattsVisionError):
    """A request was refused because the access token was not accepted.

    Distinct from `WattsVisionAuthError`: the credentials may still be good and
    a single re-authentication is worth attempting.
    """


class WattsVisionConnectionError(WattsVisionError):
    """The Watts cloud could not be reached.

    Covers connection failures, DNS resolution failures and timeouts. Transient
    by assumption, so callers should expect it to clear on a later poll.
    """


class WattsVisionApiError(WattsVisionError):
    """The cloud returned a well-formed response reporting an error.

    Carries the code and message the cloud supplied, since this API is
    undocumented and the raw values are the only thing a user can report.
    """
