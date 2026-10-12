"""Read-only iCloud calendar MCP. Synchronous I/O runs in a bounded thread pool."""
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Annotated
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field
from . import calendar as cal_ops
from .clients import CalendarClient
from .config import Settings
from .models import Calendar, Event

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="icloud-calendar-io")
_CALL_TIMEOUT = 30
DaysAhead = Annotated[int, Field(ge=0, le=366)]
_READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)

async def _run_blocking(fn, *args):
    try:
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(loop.run_in_executor(_executor, fn, *args), timeout=_CALL_TIMEOUT)
    except Exception:
        raise RuntimeError("iCloud calendar query failed. Check account setup and Apple connectivity; no partial results returned.") from None

@dataclass
class AppContext:
    settings: Settings
    calendar: CalendarClient

@asynccontextmanager
async def lifespan(_server: FastMCP):
    settings = Settings.from_env()
    calendar = CalendarClient(settings)
    try:
        yield AppContext(settings=settings, calendar=calendar)
    finally:
        calendar.close()

mcp = FastMCP("icloud-calendar-readonly", lifespan=lifespan)

def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context

def _window(app: AppContext, days_ahead: int) -> tuple[datetime, datetime]:
    if not 0 <= days_ahead <= 366:
        raise ValueError("days_ahead must be between 0 and 366")
    today = datetime.now(app.settings.tz).date()
    start = datetime.combine(today, time.min, tzinfo=app.settings.tz)
    end = datetime.combine(today + timedelta(days=days_ahead), time.max, tzinfo=app.settings.tz)
    return start, end

@mcp.tool(annotations=_READ_ONLY)
async def list_events(ctx: Context, days_ahead: DaysAhead = 1) -> list[Event]:
    """List events from today through days_ahead days out (0–366)."""
    app = _ctx(ctx)
    start, end = _window(app, days_ahead)
    return await _run_blocking(cal_ops.list_events, app.calendar, start, end, app.settings.tz)

@mcp.tool(annotations=_READ_ONLY)
async def search_events(ctx: Context, text: str, days_ahead: DaysAhead = 30) -> list[Event]:
    """Find events with titles containing text within 0–366 days from today."""
    app = _ctx(ctx)
    start, end = _window(app, days_ahead)
    return await _run_blocking(cal_ops.search_events, app.calendar, text, start, end, app.settings.tz)

@mcp.tool(annotations=_READ_ONLY)
async def list_calendars(ctx: Context) -> list[Calendar]:
    """List available iCloud calendar names."""
    return await _run_blocking(cal_ops.list_calendars, _ctx(ctx).calendar)

@mcp.resource("icloud://calendar/today")
async def calendar_today() -> list[Event]:
    """Today's calendar events in the configured timezone."""
    app = _ctx(mcp.get_context())
    start, end = _window(app, 0)
    return await _run_blocking(cal_ops.list_events, app.calendar, start, end, app.settings.tz)

def main() -> None:
    mcp.run()

if __name__ == "__main__":
    main()
