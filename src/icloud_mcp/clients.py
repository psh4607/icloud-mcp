"""Connection-holding clients for IMAP and CalDAV.

The MCP server is a long-lived process, so each client lazily connects once and
reuses the connection across tool calls, rather than reconnecting every time.

IMAP is opened read-only and message bodies are fetched with ``BODY.PEEK[]``
(see ``mail.py``), so this client cannot mark messages read or mutate the
mailbox — a structural guarantee for the read-only v1.
"""

from __future__ import annotations

import caldav
import imapclient

from .auth import get_password
from .config import Settings


class MailClient:
    """Holds a logged-in, read-only IMAP connection."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: imapclient.IMAPClient | None = None

    def connection(self) -> imapclient.IMAPClient:
        if self._client is None:
            s = self._settings
            client = imapclient.IMAPClient(s.imap_host, ssl=True, port=s.imap_port, use_uid=True)
            client.login(s.username, get_password(s.keyring_service, s.username))
            self._client = client
        return self._client

    def select(self, folder: str = "INBOX") -> imapclient.IMAPClient:
        client = self.connection()
        client.select_folder(folder, readonly=True)
        return client

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.logout()
            finally:
                self._client = None


class CalendarClient:
    """Holds a CalDAV principal for the process lifetime."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._principal = None

    def principal(self):
        if self._principal is None:
            s = self._settings
            dav = caldav.DAVClient(
                url=s.caldav_url,
                username=s.username,
                password=get_password(s.keyring_service, s.username),
            )
            self._principal = dav.principal()
        return self._principal

    def close(self) -> None:
        self._principal = None
