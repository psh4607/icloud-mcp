"""Resolve an Apple app-specific password exclusively from the OS keyring."""
from functools import lru_cache
import keyring

class CredentialError(RuntimeError):
    """The configured account's keyring credential is unavailable."""

@lru_cache(maxsize=8)
def get_password(service: str, username: str) -> str:
    try:
        stored = keyring.get_password(service, username)
    except Exception:
        raise CredentialError("Unable to read the iCloud credential from the OS keyring.") from None
    if stored:
        return stored
    raise CredentialError("No iCloud app-specific password found in the OS keyring. See README setup.")
