"""Credential resolution.

The app-specific password is resolved in this order:

1. The OS keyring (macOS Keychain, Windows Credential Locker, Secret Service on
   Linux) under the configured service + username.
2. The ``ICLOUD_APP_PASSWORD`` environment variable (fallback).

The password is never read from a committed file. On macOS, seed the keyring
with::

    security add-generic-password -a "you@icloud.com" -s "icloud-mcp" -w "PASSWORD"

or use any ``keyring`` backend.
"""

from __future__ import annotations

import os
from functools import lru_cache

import keyring


class CredentialError(RuntimeError):
    """Raised when no app-specific password can be found."""


@lru_cache(maxsize=8)
def get_password(service: str, username: str) -> str:
    """Return the app-specific password for ``username``.

    Cached per (service, username) — the keyring lookup is a syscall, and the
    password does not change within a process lifetime.
    """
    stored = keyring.get_password(service, username)
    if stored:
        return stored

    env = os.getenv("ICLOUD_APP_PASSWORD")
    if env:
        return env

    raise CredentialError(
        f"No password found in keyring (service={service!r}, username={username!r}) "
        "and ICLOUD_APP_PASSWORD is not set. See the README for keyring setup."
    )
