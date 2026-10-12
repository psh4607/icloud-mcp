"""Read-only CalDAV access, restricted to Apple's calendar HTTPS endpoints."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import caldav
import niquests

from .auth import get_password
from .config import Settings

CALDAV_ROOT = 'https://caldav.icloud.com/'
_APPLE_CALDAV_HOST = re.compile(r'(?:caldav|p[0-9]+-caldav)\.icloud\.com', re.ASCII)
_READ_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS', 'PROPFIND', 'REPORT'})


def validate_apple_url(url: str) -> None:
    """Reject non-calendar hosts, plaintext, credentials and nonstandard ports."""
    # Never include the rejected URL in errors: it may contain credentials.
    if not isinstance(url, str) or any(ord(c) < 33 for c in url) or '\\' in url:
        raise ValueError('Blocked unsafe calendar URL.')
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == 'https'
            and _APPLE_CALDAV_HOST.fullmatch(parsed.hostname or '') is not None
            and parsed.port in (None, 443)
            and parsed.username is None and parsed.password is None
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('Only Apple CalDAV HTTPS endpoints on port 443 are allowed.')


class AppleCalendarSession(niquests.Session):
    """Enforce the boundary on every send, including redirect/discovery targets.

    Nonmultiplexed niquests follows redirects through self.send; this is covered
    by adapter-level tests against the locked niquests version. Environment
    proxies, .netrc and CA overrides are intentionally not inherited.
    """
    def __init__(self):
        # Disable alternate-port Alt-Svc upgrades and separate OCSP/CRL HTTP
        # clients. Certificate chain/hostname verification remains mandatory.
        super().__init__(multiplexed=False, disable_http2=True, disable_http3=True,
                         revocation_configuration=None)
        self.trust_env = False
        self.max_redirects = 5

    def request(self, method, url, *args, **kwargs):
        validate_apple_url(url)
        return super().request(method, url, *args, **kwargs)

    def send(self, request, **kwargs):
        validate_apple_url(request.url)
        if request.method not in _READ_METHODS:
            raise ValueError('Calendar transport is read-only.')
        if kwargs.get('verify', True) is not True or kwargs.get('proxies'):
            raise ValueError('TLS verification is required and proxies are disabled.')
        kwargs.update(verify=True, proxies={}, multiplexed=False)
        return super().send(request, **kwargs)

    def rebuild_auth(self, prepared_request, response):
        # iCloud redirects to pNN-caldav.icloud.com. Keep auth only after
        # validating BOTH endpoints; never forward it to general icloud hosts.
        validate_apple_url(response.request.url)
        validate_apple_url(prepared_request.url)


class CalendarClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._principal = None
        self._dav = None

    def principal(self):
        if self._principal is None:
            s = self._settings
            if not s.username:
                raise RuntimeError('Set ICLOUD_USERNAME before reading calendars.')
            self._dav = caldav.DAVClient(
                url=CALDAV_ROOT,
                username=s.username,
                password=get_password(s.keyring_service, s.username),
                auth_type='basic',
                timeout=20,
                ssl_verify_cert=True,
                enable_rfc6764=False,
            )
            self._dav.session.close()
            self._dav.session = AppleCalendarSession()
            try:
                self._principal = self._dav.principal()
            except Exception:
                self.close()
                raise RuntimeError('Could not read iCloud calendars; check credentials and connectivity.') from None
        return self._principal

    def close(self):
        if self._dav is not None:
            self._dav.close()
        self._dav = None
        self._principal = None
