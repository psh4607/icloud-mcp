"""Stateless IMAP read operations.

Functions take a connected ``MailClient`` and never persist any cursor/state —
the caller supplies ``since`` if it wants incremental results. Bodies are
fetched with ``BODY.PEEK[]`` so messages are never marked read.
"""

from __future__ import annotations

import email as email_lib
import re
from datetime import date
from email.header import decode_header as _decode_header
from email.message import Message as EmailMessage
from html.parser import HTMLParser

from .clients import MailClient
from .models import Folder, FullMessage, Message


# --------------------------------------------------------------------------
# Header + body decoding (ported from Talos mail_capture.py)
# --------------------------------------------------------------------------

def decode_header(raw: str) -> str:
    parts = _decode_header(raw or "")
    out = []
    for part, charset in parts:
        if isinstance(part, bytes):
            out.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(part)
    return " ".join(out).strip()


class _HTMLTextExtractor(HTMLParser):
    """Strips tags and discards style/script/head text, keeping visible text."""

    _SKIP_TAGS = {"style", "script", "head"}

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


# Some senders (e.g. USPS Informed Delivery) double-wrap the body: the decoded
# text/plain part itself begins with a redundant MIME header block terminated by a
# blank line. Detect that and strip it so headers don't leak into the body/snippet.
_MIME_HEADER_START = re.compile(
    r"^(Content-Type|Content-Transfer-Encoding|Content-Disposition|MIME-Version)\s*:",
    re.IGNORECASE,
)
_HEADER_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9-]*\s*:|\s)")  # field or continuation


def _strip_leading_mime_headers(text: str) -> str:
    """Drop a redundant leading MIME header block some senders embed in the body."""
    lines = text.splitlines(keepends=True)
    if not lines or not _MIME_HEADER_START.match(lines[0]):
        return text
    for i, line in enumerate(lines):
        if line.strip() == "":  # blank line ends the header block
            return "".join(lines[i + 1:])
        if not _HEADER_LINE.match(line):  # not header-shaped -> not a real block
            return text
    return text


def _find_part_text(msg: EmailMessage, content_type: str) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == content_type:
                raw = part.get_payload(decode=True)
                if raw:
                    decoded = raw.decode(part.get_content_charset() or "utf-8", errors="replace")
                    return _strip_leading_mime_headers(decoded)
    elif msg.get_content_type() == content_type:
        raw = msg.get_payload(decode=True)
        if raw:
            decoded = raw.decode(msg.get_content_charset() or "utf-8", errors="replace")
            return _strip_leading_mime_headers(decoded)
    return ""


def body_text(msg: EmailMessage) -> str:
    """Full text body — prefers text/plain, falls back to HTML-stripped text."""
    plain = _find_part_text(msg, "text/plain")
    if plain:
        return plain
    html = _find_part_text(msg, "text/html")
    if html:
        return html_to_text(html)
    return ""


def body_snippet(msg: EmailMessage, max_chars: int = 200) -> str:
    return body_text(msg)[:max_chars]


# --------------------------------------------------------------------------
# Stateless fetch operations
# --------------------------------------------------------------------------

def _summary_fields(uid: int, msg: EmailMessage) -> dict:
    """Common Message fields, with fallbacks for absent *or* empty headers."""
    return {
        "uid": uid,
        "date": msg.get("Date", ""),
        "from": decode_header(msg.get("From", "")) or "(unknown)",
        "subject": decode_header(msg.get("Subject", "")) or "(no subject)",
        "snippet": " ".join(body_snippet(msg).split()),
    }


def _search_uids(imap, since: int | date | None, limit: int) -> list[int]:
    if isinstance(since, int) and since > 0:
        uids = imap.search(["UID", f"{since + 1}:*"])
    elif isinstance(since, date):
        uids = imap.search(["SINCE", since])
    else:
        uids = imap.search(["ALL"])
    # Newest first, capped.
    return sorted(uids, reverse=True)[:limit]


def list_messages(
    client: MailClient,
    folder: str = "INBOX",
    since: int | date | None = None,
    limit: int = 50,
) -> list[Message]:
    """List messages, newest first.

    ``since`` may be a UID (int, exclusive) or a date (inclusive). When omitted,
    returns the most recent ``limit`` messages in the folder.
    """
    imap = client.select(folder)
    uids = _search_uids(imap, since, limit)
    if not uids:
        return []
    out: list[Message] = []
    for uid, data in imap.fetch(uids, ["BODY.PEEK[]"]).items():
        raw = data.get(b"BODY[]")
        if not raw:
            continue
        msg = email_lib.message_from_bytes(raw)
        out.append(Message(**_summary_fields(uid, msg)))
    out.sort(key=lambda m: m.uid, reverse=True)
    return out


def search_messages(
    client: MailClient,
    query: str,
    folder: str = "INBOX",
    limit: int = 50,
) -> list[Message]:
    """Full-text search across common headers + body (server-side IMAP TEXT)."""
    imap = client.select(folder)
    uids = imap.search(["TEXT", query])
    uids = sorted(uids, reverse=True)[:limit]
    if not uids:
        return []
    out: list[Message] = []
    for uid, data in imap.fetch(uids, ["BODY.PEEK[]"]).items():
        raw = data.get(b"BODY[]")
        if not raw:
            continue
        msg = email_lib.message_from_bytes(raw)
        out.append(Message(**_summary_fields(uid, msg)))
    out.sort(key=lambda m: m.uid, reverse=True)
    return out


def list_folders(client: MailClient) -> list[Folder]:
    """List the mailbox folder names available over IMAP."""
    conn = client.connection()
    return [Folder(name=name) for _flags, _delim, name in conn.list_folders()]


def get_message(client: MailClient, uid: int, folder: str = "INBOX") -> FullMessage | None:
    """Fetch a single message with its full text body."""
    imap = client.select(folder)
    fetched = imap.fetch([uid], ["BODY.PEEK[]"])
    data = fetched.get(uid)
    if not data:
        return None
    raw = data.get(b"BODY[]")
    if not raw:
        return None
    msg = email_lib.message_from_bytes(raw)
    return FullMessage(**_summary_fields(uid, msg), body=body_text(msg))
