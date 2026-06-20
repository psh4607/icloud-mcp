"""Structured output models for tool/resource responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Message(BaseModel):
    uid: int
    date: str = Field("", description="Raw Date header from the message")
    sender: str = Field("", description="Decoded From header", alias="from")
    subject: str = ""
    snippet: str = Field("", description="Plain-text preview (HTML stripped if needed)")

    model_config = {"populate_by_name": True}


class FullMessage(Message):
    body: str = Field("", description="Full decoded text body")


class Event(BaseModel):
    uid: str = ""
    summary: str = "(no title)"
    start: str = Field("", description="ISO-8601 start, or date for all-day events")
    end: str = ""
    all_day: bool = False
    calendar: str = ""


class Calendar(BaseModel):
    name: str
