"""Unit tests for mail parsing + stateless fetch, using fake IMAP clients.

No network, no keyring, no live account.
"""

import email as email_lib

from icloud_mcp import mail as mail_ops


def _msg(content_type: str, body: str, subject="Test", sender="a@b.com") -> bytes:
    return (
        f"From: {sender}\r\n"
        f"Subject: {subject}\r\n"
        f"Content-Type: {content_type}; charset=utf-8\r\n"
        f"\r\n{body}\r\n"
    ).encode()


def test_body_snippet_prefers_plain_text():
    raw = _msg("text/plain", "Plain body wins.")
    msg = email_lib.message_from_bytes(raw)
    assert mail_ops.body_snippet(msg).strip() == "Plain body wins."


def test_body_snippet_html_fallback_strips_tags_and_style():
    html = "<html><head><style>p{color:red}</style></head><body><p>Hello <b>world</b></p></body></html>"
    raw = _msg("text/html", html)
    msg = email_lib.message_from_bytes(raw)
    snippet = mail_ops.body_snippet(msg)
    assert "Hello" in snippet and "world" in snippet
    assert "color:red" not in snippet  # style content excluded
    assert "<" not in snippet  # tags stripped


def test_decode_header_handles_encoded_words():
    decoded = mail_ops.decode_header("=?utf-8?q?Caf=C3=A9?=")
    assert decoded == "Café"


class _FakeIMAP:
    """Minimal stand-in for imapclient.IMAPClient covering what mail_ops uses."""

    def __init__(self, bodies: dict[int, bytes]):
        self._bodies = bodies

    def select_folder(self, folder, readonly=True):
        pass

    def search(self, criteria):
        return list(self._bodies)

    def fetch(self, uids, parts):
        # Mirror imapclient: absent UIDs simply aren't in the result dict.
        return {uid: {b"BODY[]": self._bodies[uid]} for uid in uids if uid in self._bodies}


class _FakeMailClient:
    def __init__(self, bodies):
        self._imap = _FakeIMAP(bodies)

    def select(self, folder="INBOX"):
        return self._imap


def test_list_messages_parses_and_sorts_newest_first():
    bodies = {
        10: _msg("text/plain", "older", subject="Older"),
        20: _msg("text/html", "<p>newer</p>", subject="Newer"),
    }
    client = _FakeMailClient(bodies)
    messages = mail_ops.list_messages(client, limit=10)
    assert [m.uid for m in messages] == [20, 10]
    assert messages[0].subject == "Newer"
    assert messages[0].snippet == "newer"  # HTML fallback applied


def test_get_message_returns_full_body():
    bodies = {7: _msg("text/plain", "Full body here.", subject="Hi")}
    client = _FakeMailClient(bodies)
    full = mail_ops.get_message(client, 7)
    assert full is not None
    assert full.subject == "Hi"
    assert full.body.strip() == "Full body here."


def test_get_message_missing_uid_returns_none():
    client = _FakeMailClient({})
    assert mail_ops.get_message(client, 999) is None


def test_empty_subject_and_from_fall_back():
    # Present-but-empty headers, not absent — the real uid 93530 case.
    raw = b"From: \r\nSubject: \r\nContent-Type: text/plain; charset=utf-8\r\n\r\nbody\r\n"
    client = _FakeMailClient({5: raw})
    msg = mail_ops.list_messages(client)[0]
    assert msg.subject == "(no subject)"
    assert msg.sender == "(unknown)"

    full = mail_ops.get_message(client, 5)
    assert full.subject == "(no subject)"
    assert full.sender == "(unknown)"
