"""Unit tests for the mutating ops — SMTP send + CalDAV event creation. No network."""

import pytest

from icloud_mcp import writes


class _FakeSMTP:
    """Captures what would be sent, mirroring smtplib.SMTP's context-manager API."""

    last = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.started_tls = False
        self.logged_in = None
        self.sent = None
        _FakeSMTP.last = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, msg):
        self.sent = msg


def _settings():
    return type(
        "S",
        (),
        {
            "username": "me@icloud.com",
            "smtp_host": "smtp.test",
            "smtp_port": 587,
            "keyring_service": "svc",
        },
    )()


def test_send_message_builds_and_sends(monkeypatch):
    monkeypatch.setattr(writes.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(writes, "get_password", lambda svc, user: "app-pw")

    result = writes.send_message(
        _settings(), to="you@example.com", subject="Hi", body="Hello there.", cc="c@example.com"
    )
    sent = _FakeSMTP.last
    assert sent.started_tls and sent.logged_in == ("me@icloud.com", "app-pw")
    assert sent.sent["To"] == "you@example.com"
    assert sent.sent["Cc"] == "c@example.com"
    assert sent.sent["From"] == "me@icloud.com"
    assert sent.sent["Subject"] == "Hi"
    assert sent.sent.get_content().strip() == "Hello there."
    assert result == "Sent to you@example.com."


def test_send_message_auth_error_is_wrapped(monkeypatch):
    import smtplib

    class _AuthFailSMTP(_FakeSMTP):
        def login(self, user, password):
            raise smtplib.SMTPAuthenticationError(535, b"nope")

    monkeypatch.setattr(writes.smtplib, "SMTP", _AuthFailSMTP)
    monkeypatch.setattr(writes, "get_password", lambda svc, user: "app-pw")

    with pytest.raises(writes.WriteError, match="authentication failed"):
        writes.send_message(_settings(), "you@example.com", "Hi", "Body")


class _FakeCal:
    def __init__(self, name):
        self._name = name
        self.saved = None

    def get_display_name(self):
        return self._name

    def save_event(self, ical):
        self.saved = ical


class _FakePrincipal:
    def __init__(self, cals):
        self._cals = cals

    def calendars(self):
        return self._cals


class _FakeCalClient:
    def __init__(self, cals):
        self._principal = _FakePrincipal(cals)

    def principal(self):
        return self._principal


def test_create_event_builds_vevent_on_default_calendar():
    home, work = _FakeCal("Home"), _FakeCal("Work")
    client = _FakeCalClient([home, work])
    msg = writes.create_event(
        client, "Dentist", "2026-06-21T14:00:00", "2026-06-21T15:00:00"
    )
    assert home.saved is not None and work.saved is None  # defaults to first
    assert "SUMMARY:Dentist" in home.saved
    assert "DTSTART:20260621T140000" in home.saved
    assert "DTEND:20260621T150000" in home.saved
    assert "Home" in msg


def test_create_event_targets_named_calendar_with_location():
    home, work = _FakeCal("Home"), _FakeCal("Work")
    client = _FakeCalClient([home, work])
    writes.create_event(
        client, "Standup", "2026-06-22T09:00:00", "2026-06-22T09:15:00",
        calendar_name="Work", location="Room 4",
    )
    assert work.saved is not None and home.saved is None
    assert "LOCATION:Room 4" in work.saved


def test_create_event_bad_date_is_wrapped():
    client = _FakeCalClient([_FakeCal("Home")])
    with pytest.raises(writes.WriteError, match="Invalid date"):
        writes.create_event(client, "X", "not-a-date", "also-bad")


def test_create_event_no_calendars():
    client = _FakeCalClient([])
    with pytest.raises(writes.WriteError, match="No calendars"):
        writes.create_event(client, "X", "2026-06-21T14:00:00", "2026-06-21T15:00:00")
