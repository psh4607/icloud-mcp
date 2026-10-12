from dataclasses import fields
from icloud_mcp.config import Settings

def test_settings_only_calendar_identity(monkeypatch):
    monkeypatch.setenv('ICLOUD_USERNAME', 'x@example.com')
    monkeypatch.setenv('ICLOUD_KEYRING_SERVICE', 'malicious')
    settings = Settings.from_env()
    assert {f.name for f in fields(settings)} == {'username', 'keyring_service', 'tz'}
    assert settings.keyring_service == 'icloud-calendar-readonly'

def test_discovery_settings_without_username(monkeypatch):
    monkeypatch.delenv('ICLOUD_USERNAME', raising=False)
    assert Settings.from_env().username == ''
