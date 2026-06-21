"""Mutating operations — the *only* module in the package that can change state.

Kept deliberately separate from the read path: mail is sent over a fresh SMTP
connection (the read-only IMAP ``MailClient`` has no send capability), and every
caller is expected to be gated by ``Settings.enable_writes`` + an interactive
confirmation in ``server.py`` before reaching here.
"""

from __future__ import annotations

import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage

from .auth import get_password
from .clients import CalendarClient
from .config import Settings


class WriteError(RuntimeError):
    """A user-facing failure from a mutating operation (no credential leakage)."""


def send_message(settings: Settings, to: str, subject: str, body: str, cc: str = "") -> str:
    """Send a plain-text email over a fresh, authenticated SMTP+STARTTLS connection."""
    msg = EmailMessage()
    msg["From"] = settings.username
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg.set_content(body)

    password = get_password(settings.keyring_service, settings.username)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(settings.username, password)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise WriteError(
            "SMTP authentication failed — check the app-specific password in the keyring."
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise WriteError(f"Failed to send mail: {type(exc).__name__}") from exc
    return f"Sent to {to}."


def _ical(title: str, start_iso: str, end_iso: str, location: str) -> str:
    """Build a minimal VEVENT. Start/end are ISO-8601 strings (date or datetime)."""
    def fmt(value: str) -> str:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y%m%dT%H%M%S")

    uid = f"{uuid.uuid4()}@icloud-mcp"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//icloud-mcp//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{fmt(start_iso)}",
        f"DTEND:{fmt(end_iso)}",
        f"SUMMARY:{title}",
    ]
    if location:
        lines.append(f"LOCATION:{location}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines)


def create_event(
    client: CalendarClient,
    title: str,
    start_iso: str,
    end_iso: str,
    calendar_name: str = "",
    location: str = "",
) -> str:
    """Create a calendar event. Targets `calendar_name` if given, else the first."""
    try:
        ical = _ical(title, start_iso, end_iso, location)
    except ValueError as exc:
        raise WriteError(f"Invalid date/time: {exc}") from exc

    principal = client.principal()
    calendars = principal.calendars()
    if not calendars:
        raise WriteError("No calendars available to write to.")

    target = calendars[0]
    if calendar_name:
        for cal in calendars:
            if cal.get_display_name() == calendar_name:
                target = cal
                break

    try:
        target.save_event(ical)
    except Exception as exc:  # caldav raises a variety of transport errors
        raise WriteError(f"Failed to create event: {type(exc).__name__}") from exc
    return f"Created “{title}” on {target.get_display_name()}."
