"""Structured output models for tool/resource responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Event(BaseModel):
    uid: str = ""
    summary: str = "(no title)"
    start: str = Field("", description="ISO-8601 start, or date for all-day events")
    end: str = ""
    all_day: bool = False
    calendar: str = ""


class Calendar(BaseModel):
    name: str
