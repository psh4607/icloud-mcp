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


@pytest.fixture
def patched_clients(monkeypatch):
    body = (
        b"From: bank@example.com\r\nSubject: Statement ready\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\nYour statement is ready.\r\n"
    )
    fake_settings = type("S", (), {"username": "x", "keyring_service": "x"})()

    monkeypatch.setattr(server.Settings, "from_env", classmethod(lambda cls: fake_settings))
    monkeypatch.setattr(server, "MailClient", lambda s: _FakeMailClient({42: body}))
    monkeypatch.setattr(server, "CalendarClient", lambda s: _FakeCalendarClient())


@pytest.mark.anyio
async def test_search_mail_tool(patched_clients):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        result = await client.call_tool("search_mail", {"query": "statement"})
        assert not result.isError
        assert any("Statement ready" in str(c.text) for c in result.content)


@pytest.mark.anyio
async def test_list_calendars_tool_empty(patched_clients):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        result = await client.call_tool("list_calendars", {})
        assert not result.isError
