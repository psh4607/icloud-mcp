"""Configuration for the iCloud MCP server.

Defaults target iCloud, but every endpoint is overridable via environment
variables, so the server also works against any standard IMAP/CalDAV provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional; env may be set another way
    pass


def _local_tz() -> ZoneInfo:
    name = os.getenv("ICLOUD_TZ")
    if name:
        return ZoneInfo(name)
    # Fall back to the system local timezone.
    try:
        return ZoneInfo(os.environ.get("TZ", "")) if os.environ.get("TZ") else ZoneInfo("UTC")
    except Exception:
        return ZoneInfo("UTC")


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    username: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    caldav_url: str
    carddav_url: str
    keyring_service: str
    tz: ZoneInfo
    enable_writes: bool

    @classmethod
    def from_env(cls) -> "Settings":
        username = os.getenv("ICLOUD_USERNAME")
        if not username:
            raise RuntimeError(
                "ICLOUD_USERNAME is not set. Set it in the environment or a .env file."
            )
        return cls(
            username=username,
            imap_host=os.getenv("ICLOUD_IMAP_HOST", "imap.mail.me.com"),
            imap_port=int(os.getenv("ICLOUD_IMAP_PORT", "993")),
            smtp_host=os.getenv("ICLOUD_SMTP_HOST", "smtp.mail.me.com"),
            smtp_port=int(os.getenv("ICLOUD_SMTP_PORT", "587")),
            caldav_url=os.getenv("ICLOUD_CALDAV_URL", "https://caldav.icloud.com/"),
            carddav_url=os.getenv("ICLOUD_CARDDAV_URL", "https://contacts.icloud.com/"),
            keyring_service=os.getenv("ICLOUD_KEYRING_SERVICE", "icloud-mcp"),
            tz=_local_tz(),
            enable_writes=_truthy(os.getenv("ICLOUD_ENABLE_WRITES")),
        )
