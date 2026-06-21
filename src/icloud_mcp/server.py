"""The iCloud MCP server.

Read-only v1: tools and resources that list/search/read mail and calendar.
Synchronous IMAP/CalDAV calls are dispatched to a thread pool so they never
block the asyncio event loop.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from mcp.server.fastmcp import Context, FastMCP

from . import calendar as cal_ops
from . import mail as mail_ops
from .clients import CalendarClient, MailClient
from .config import Settings
from .models import Calendar, Event, Folder, FullMessage, Message

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="icloud-io")
_CALL_TIMEOUT = 30  # seconds


async def _run_blocking(fn, *args):
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, fn, *args), timeout=_CALL_TIMEOUT
    )


@dataclass
class AppContext:
    settings: Settings
    mail: MailClient
    calendar: CalendarClient


@asynccontextmanager
async def lifespan(_server: FastMCP):
    settings = Settings.from_env()
    mail = MailClient(settings)
    calendar = CalendarClient(settings)
    try:
        yield AppContext(settings=settings, mail=mail, calendar=calendar)
    finally:
        mail.close()
        calendar.close()


mcp = FastMCP("icloud", lifespan=lifespan)


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context


def _window(app: AppContext, days_ahead: int) -> tuple[datetime, datetime]:
    today = datetime.now(app.settings.tz).date()
    start = datetime.combine(today, time.min, tzinfo=app.settings.tz)
    end = datetime.combine(today + timedelta(days=days_ahead), time.max, tzinfo=app.settings.tz)
    return start, end


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@mcp.tool()
async def list_mail(
    ctx: Context, folder: str = "INBOX", since_date: str = "", limit: int = 50
) -> list[Message]:
    """List messages in a folder (default INBOX), newest first.

    `since_date` is an optional YYYY-MM-DD; when set, only messages on/after that
    date are returned (server-side IMAP SINCE, which is date-granular and evaluated
    in the server's timezone).
    """
    app = _ctx(ctx)
    since = date.fromisoformat(since_date) if since_date else None
    return await _run_blocking(mail_ops.list_messages, app.mail, folder, since, limit)


@mcp.tool()
async def search_mail(
    ctx: Context, query: str, folder: str = "INBOX", limit: int = 50
) -> list[Message]:
    """Full-text search mail in a folder (default INBOX). Returns newest first."""
    app = _ctx(ctx)
    return await _run_blocking(mail_ops.search_messages, app.mail, query, folder, limit)


@mcp.tool()
async def list_folders(ctx: Context) -> list[Folder]:
    """List the IMAP mailbox folder names (e.g. INBOX, Sent Messages, Archive)."""
    app = _ctx(ctx)
    return await _run_blocking(mail_ops.list_folders, app.mail)


@mcp.tool()
async def get_message(ctx: Context, uid: int, folder: str = "INBOX") -> FullMessage | None:
    """Fetch a single message by UID, including its full text body."""
    app = _ctx(ctx)
    return await _run_blocking(mail_ops.get_message, app.mail, uid, folder)


@mcp.tool()
async def list_events(ctx: Context, days_ahead: int = 1) -> list[Event]:
    """List calendar events from today through `days_ahead` days out."""
    app = _ctx(ctx)
    start, end = _window(app, days_ahead)
    return await _run_blocking(cal_ops.list_events, app.calendar, start, end, app.settings.tz)


@mcp.tool()
async def search_events(ctx: Context, text: str, days_ahead: int = 30) -> list[Event]:
    """Find events whose title matches `text` within the next `days_ahead` days."""
    app = _ctx(ctx)
    start, end = _window(app, days_ahead)
    return await _run_blocking(
        cal_ops.search_events, app.calendar, text, start, end, app.settings.tz
    )


@mcp.tool()
async def list_calendars(ctx: Context) -> list[Calendar]:
    """List the names of all available calendars."""
    app = _ctx(ctx)
    return await _run_blocking(cal_ops.list_calendars, app.calendar)


# --------------------------------------------------------------------------
# Resources (passive context)
# --------------------------------------------------------------------------

@mcp.resource("icloud://mail/inbox/recent")
async def recent_inbox() -> list[Message]:
    """The most recent inbox messages."""
    app: AppContext = mcp.get_context().request_context.lifespan_context
    return await _run_blocking(mail_ops.list_messages, app.mail, "INBOX", None, 25)


@mcp.resource("icloud://calendar/today")
async def calendar_today() -> list[Event]:
    """Today + tomorrow's calendar events."""
    app: AppContext = mcp.get_context().request_context.lifespan_context
    start, end = _window(app, 1)
    return await _run_blocking(cal_ops.list_events, app.calendar, start, end, app.settings.tz)


# --------------------------------------------------------------------------
# Phase 2 (not implemented): mutating tools.
#
# send_mail / create_event / update_event / delete_event would go here, each
# gated behind ctx.elicit(...) for explicit user confirmation and backed by a
# SEPARATE SMTP/write credential + connection, so the read path above can never
# acquire write capability. Deliberately omitted from v1.
# --------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
