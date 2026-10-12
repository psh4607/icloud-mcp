import pytest
from icloud_mcp import auth

def test_environment_password_is_never_used(monkeypatch):
    auth.get_password.cache_clear()
    monkeypatch.setenv('ICLOUD_APP_PASSWORD', 'secret-env')
    monkeypatch.setattr(auth.keyring, 'get_password', lambda *args: None)
    with pytest.raises(auth.CredentialError):
        auth.get_password('icloud-calendar-readonly', 'x@example.com')

def test_keyring_errors_are_sanitized(monkeypatch):
    auth.get_password.cache_clear()
    def fail(*args):
        raise RuntimeError('secret-password')
    monkeypatch.setattr(auth.keyring, 'get_password', fail)
    with pytest.raises(auth.CredentialError) as error:
        auth.get_password('icloud-calendar-readonly', 'x@example.com')
    assert 'secret-password' not in str(error.value)
