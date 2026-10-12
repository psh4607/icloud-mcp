"""Stateless CalDAV read operations.

TZ-aware handling that normalizes all-day ``date`` events against timed
``datetime`` events.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from .clients import CalendarClient
from .models import Calendar, Event


def _sort_key(dt, tz: ZoneInfo):
    if isinstance(dt, datetime):
        return dt.astimezone(tz)
    return datetime.combine(dt, time.min, tzinfo=tz)


def _to_iso(dt, tz: ZoneInfo) -> tuple[str, bool]:
    """Return (iso_string, is_all_day)."""
    if isinstance(dt, datetime):
        return dt.astimezone(tz).isoformat(), False
    if isinstance(dt, date):
        return dt.isoformat(), True
    return str(dt), False


def list_calendars(client: CalendarClient) -> list[Calendar]:
    principal = client.principal()
    return [Calendar(name=cal.get_display_name()) for cal in principal.calendars()]


def list_events(
    client: CalendarClient,
    start: datetime,
    end: datetime,
    tz: ZoneInfo,
) -> list[Event]:
    """List events across all calendars within [start, end], chronologically."""
    principal = client.principal()
    events: list[tuple[object, Event]] = []
    for cal in principal.calendars():
        try:
            found = cal.search(start=start, end=end, event=True, expand=True)
        except Exception:
            raise RuntimeError("Calendar query failed; no partial results returned.") from None
        cal_name = cal.get_display_name()
        for ev in found:
            comp = ev.icalendar_component
            dtstart = comp.get("dtstart").dt
            dtend_field = comp.get("dtend")
            start_iso, all_day = _to_iso(dtstart, tz)
            end_iso = _to_iso(dtend_field.dt, tz)[0] if dtend_field is not None else ""
            events.append(
                (
                    _sort_key(dtstart, tz),
                    Event(
                        uid=str(comp.get("uid", "")),
                        summary=str(comp.get("summary", "(no title)")),
                        start=start_iso,
                        end=end_iso,
                        all_day=all_day,
                        calendar=cal_name,
                    ),
                )
            )
    events.sort(key=lambda pair: pair[0])
    return [e for _, e in events]


def search_events(
    client: CalendarClient,
    text: str,
    start: datetime,
    end: datetime,
    tz: ZoneInfo,
) -> list[Event]:
    """Substring match on event summaries within the window."""
    needle = text.lower()
    return [e for e in list_events(client, start, end, tz) if needle in e.summary.lower()]
