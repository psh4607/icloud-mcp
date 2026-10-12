"""Calendar identity configuration. Endpoints and credential service are fixed."""
from __future__ import annotations
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

KEYRING_SERVICE = "icloud-calendar-readonly"

@dataclass(frozen=True)
class Settings:
    username: str
    keyring_service: str
    tz: ZoneInfo

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            username=os.getenv("ICLOUD_USERNAME", "").strip(),
            keyring_service=KEYRING_SERVICE,
            tz=ZoneInfo(os.getenv("ICLOUD_TZ", "UTC")),
        )
