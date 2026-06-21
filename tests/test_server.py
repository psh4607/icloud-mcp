"""End-to-end MCP tool tests via the in-memory client/server session.

The lifespan's real iCloud clients are replaced with in-process fakes, so these
tests exercise the full tool dispatch path without any network or credentials.
"""

import email as email_lib

import pytest

import icloud_mcp.server as server


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeIMAP:
    def __init__(self, bodies):
        self._bodies = bodies

    def select_folder(self, folder, readonly=True):
        pass

    def search(self, criteria):
        return list(self._bodies)

    def fetch(self, uids, parts):
        return {uid: {b"BODY[]": self._bodies[uid]} for uid in uids}


class _FakeMailClient:
    def __init__(self, bodies):
        self._imap = _FakeIMAP(bodies)

    def select(self, folder="INBOX"):
        return self._imap

    def close(self):
        pass


class _FakeCalendarClient:
    def principal(self):
        class _P:
            def calendars(self):
                return []

        return _P()

    def close(self):
        pass


class _FakeContactsClient:
    def fetch_vcards(self):
        return []

    def close(self):
        pass


def _install_fakes(monkeypatch, enable_writes=False):
    body = (
        b"From: bank@example.com\r\nSubject: Statement ready\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\nYour statement is ready.\r\n"
    )
    fake_settings = type(
        "S", (), {"username": "x", "keyring_service": "x", "enable_writes": enable_writes}
    )()
    monkeypatch.setattr(server.Settings, "from_env", classmethod(lambda cls: fake_settings))
    monkeypatch.setattr(server, "MailClient", lambda s: _FakeMailClient({42: body}))
    monkeypatch.setattr(server, "CalendarClient", lambda s: _FakeCalendarClient())
    monkeypatch.setattr(server, "ContactsClient", lambda s: _FakeContactsClient())
    return fake_settings


@pytest.fixture
def patched_clients(monkeypatch):
    _install_fakes(monkeypatch, enable_writes=False)


@pytest.fixture
def patched_clients_writable(monkeypatch):
    """Writes enabled, with the write ops stubbed so nothing leaves the process."""
    _install_fakes(monkeypatch, enable_writes=True)
    calls = {}

    def fake_send(settings, to, subject, body, cc=""):
        calls["sent"] = (to, subject)
        return f"Sent to {to}."

    def fake_create(client, title, start, end, calendar="", location=""):
        calls["event"] = (title, start, end)
        return f"Created “{title}”."

    monkeypatch.setattr(server.write_ops, "send_message", fake_send)
    monkeypatch.setattr(server.write_ops, "create_event", fake_create)
    return calls


def _accept_cb(action):
    """Build an elicitation callback that always returns `action`."""
    from mcp.types import ElicitResult

    async def cb(context, params):
        return ElicitResult(action=action, content={"confirm": action == "accept"})

    return cb


@pytest.mark.anyio
async def test_search_mail_tool(patched_clients):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        result = await client.call_tool("search_mail", {"query": "statement"})
        assert not result.isError
        assert any("Statement ready" in str(c.text) for c in result.content)


@pytest.mark.anyio
async def test_list_mail_tool(patched_clients):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        result = await client.call_tool("list_mail", {"since_date": "2026-06-20"})
        assert not result.isError
        assert any("Statement ready" in str(c.text) for c in result.content)


@pytest.mark.anyio
async def test_list_calendars_tool_empty(patched_clients):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        result = await client.call_tool("list_calendars", {})
        assert not result.isError


@pytest.mark.anyio
async def test_send_mail_blocked_when_writes_disabled(patched_clients):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        result = await client.call_tool(
            "send_mail", {"to": "x@y.com", "subject": "Hi", "body": "yo"}
        )
        assert result.isError
        assert any("ICLOUD_ENABLE_WRITES" in str(c.text) for c in result.content)


@pytest.mark.anyio
async def test_send_mail_declined_does_not_send(patched_clients_writable):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(
        server.mcp._mcp_server, elicitation_callback=_accept_cb("decline")
    ) as client:
        result = await client.call_tool(
            "send_mail", {"to": "x@y.com", "subject": "Hi", "body": "yo"}
        )
        assert not result.isError
        assert any("Cancelled" in str(c.text) for c in result.content)
        assert "sent" not in patched_clients_writable


@pytest.mark.anyio
async def test_send_mail_accepted_sends(patched_clients_writable):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(
        server.mcp._mcp_server, elicitation_callback=_accept_cb("accept")
    ) as client:
        result = await client.call_tool(
            "send_mail", {"to": "x@y.com", "subject": "Hi", "body": "yo"}
        )
        assert not result.isError
        assert patched_clients_writable["sent"] == ("x@y.com", "Hi")


@pytest.mark.anyio
async def test_create_event_accepted_creates(patched_clients_writable):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(
        server.mcp._mcp_server, elicitation_callback=_accept_cb("accept")
    ) as client:
        result = await client.call_tool(
            "create_event",
            {"title": "Sync", "start": "2026-06-21T14:00:00", "end": "2026-06-21T15:00:00"},
        )
        assert not result.isError
        assert "event" in patched_clients_writable
