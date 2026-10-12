"""Unit tests for calendar fetch logic, using fake CalDAV principals."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from icloud_mcp import calendar as cal_ops

TZ = ZoneInfo("America/New_York")


class _Field:
    def __init__(self, dt):
        self.dt = dt


class _Comp:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class _Event:
    def __init__(self, comp_data):
        self.icalendar_component = _Comp(comp_data)


class _Calendar:
    def __init__(self, name, events):
        self._name = name
        self._events = events

    def get_display_name(self):
        return self._name

    def search(self, start, end, event=True, expand=True):
        return self._events


class _Principal:
    def __init__(self, calendars):
        self._calendars = calendars

    def calendars(self):
        return self._calendars


class _FakeCalendarClient:
    def __init__(self, calendars):
        self._principal = _Principal(calendars)

    def principal(self):
        return self._principal


def _timed(hour, summary, uid):
    dt = datetime.combine(date(2026, 6, 20), time(hour, 0), tzinfo=TZ)
    return _Event({"uid": uid, "summary": summary, "dtstart": _Field(dt)})


def _all_day(summary, uid):
    return _Event({"uid": uid, "summary": summary, "dtstart": _Field(date(2026, 6, 20))})


def test_list_events_sorted_and_typed():
    cal = _Calendar("Home", [_timed(14, "Afternoon", "u2"), _timed(9, "Morning", "u1"), _all_day("Holiday", "u3")])
    client = _FakeCalendarClient([cal])
    start = datetime.combine(date(2026, 6, 20), time.min, tzinfo=TZ)
    end = datetime.combine(date(2026, 6, 21), time.max, tzinfo=TZ)
    events = cal_ops.list_events(client, start, end, TZ)

    # All-day (sorts at midnight) first, then 9am, then 2pm.
    assert [e.summary for e in events] == ["Holiday", "Morning", "Afternoon"]
    holiday = next(e for e in events if e.summary == "Holiday")
    assert holiday.all_day is True
    morning = next(e for e in events if e.summary == "Morning")
    assert morning.all_day is False


def test_search_events_matches_substring_case_insensitive():
    cal = _Calendar("Work", [_timed(10, "Dentist appointment", "u1"), _timed(11, "Standup", "u2")])
    client = _FakeCalendarClient([cal])
    start = datetime.combine(date(2026, 6, 20), time.min, tzinfo=TZ)
    end = datetime.combine(date(2026, 6, 21), time.max, tzinfo=TZ)
    results = cal_ops.search_events(client, "DENTIST", start, end, TZ)
    assert len(results) == 1 and results[0].summary == "Dentist appointment"


def test_list_calendars():
    client = _FakeCalendarClient([_Calendar("Home", []), _Calendar("Work", [])])
    names = [c.name for c in cal_ops.list_calendars(client)]
    assert names == ["Home", "Work"]


def test_failing_calendar_is_visible_and_sanitized():
    class _Boom(_Calendar):
        def search(self, *a, **k):
            raise RuntimeError("secret-password")

    good = _Calendar("Good", [_timed(9, "Ok", "u1")])
    client = _FakeCalendarClient([_Boom("Bad", []), good])
    start = datetime.combine(date(2026, 6, 20), time.min, tzinfo=TZ)
    end = datetime.combine(date(2026, 6, 21), time.max, tzinfo=TZ)
    import pytest
    with pytest.raises(RuntimeError, match="Calendar query failed") as error:
        cal_ops.list_events(client, start, end, TZ)
    assert "secret-password" not in str(error.value)
