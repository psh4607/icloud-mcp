import pytest
import icloud_mcp.server as server

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_discovery_is_calendar_only_without_credentials(monkeypatch):
    monkeypatch.setenv("ICLOUD_USERNAME", "test@example.com")
    tools = await server.mcp.list_tools()
    assert {t.name for t in tools} == {"list_calendars", "list_events", "search_events"}
    assert all(t.annotations.readOnlyHint for t in tools)
    resources = await server.mcp.list_resources()
    assert {str(r.uri) for r in resources} == {"icloud://calendar/today"}

@pytest.mark.parametrize("days", [-1, 367])
def test_window_rejects_unbounded_days(days):
    from zoneinfo import ZoneInfo
    from types import SimpleNamespace
    app = SimpleNamespace(settings=SimpleNamespace(tz=ZoneInfo("UTC")))
    with pytest.raises(ValueError, match="0.*366"):
        server._window(app, days)

@pytest.mark.anyio
async def test_protocol_discovery_and_invalid_range_without_credentials(monkeypatch):
    from mcp.shared.memory import create_connected_server_and_client_session
    monkeypatch.delenv("ICLOUD_USERNAME", raising=False)
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        tools = (await client.list_tools()).tools
        assert len(tools) == 3
        result = await client.call_tool('list_events', {'days_ahead': 367})
        assert result.isError
        assert '366' in result.content[0].text

@pytest.mark.anyio
async def test_tool_error_never_exposes_upstream_secret(monkeypatch):
    from mcp.shared.memory import create_connected_server_and_client_session
    def fail(*args):
        raise RuntimeError('secret-password https://evil.example')
    monkeypatch.setattr(server.cal_ops, 'list_calendars', fail)
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        result = await client.call_tool('list_calendars', {})
        assert result.isError
        assert 'secret-password' not in result.content[0].text
        assert 'evil.example' not in result.content[0].text
