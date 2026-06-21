"""Unit tests for vCard parsing and contact search. No network."""

from icloud_mcp import contacts as contacts_ops

_VCARD_FULL = (
    "BEGIN:VCARD\r\n"
    "VERSION:3.0\r\n"
    "FN:Ada Lovelace\r\n"
    "ORG:Analytical Engines;R&D\r\n"
    "EMAIL;type=HOME:ada@example.com\r\n"
    "EMAIL;type=WORK:ada@engines.test\r\n"
    "item1.TEL;type=pref:+1-555-0100\r\n"
    "TEL;type=CELL:+1-555-0199\r\n"
    "END:VCARD\r\n"
)

_VCARD_MINIMAL = "BEGIN:VCARD\r\nVERSION:3.0\r\nFN:No Org Person\r\nEND:VCARD\r\n"
_VCARD_NAMELESS = "BEGIN:VCARD\r\nVERSION:3.0\r\nEMAIL:ghost@example.com\r\nEND:VCARD\r\n"


class _FakeContactsClient:
    def __init__(self, vcards):
        self._vcards = vcards

    def fetch_vcards(self):
        return list(self._vcards)


def test_parse_vcard_extracts_all_fields():
    c = contacts_ops.parse_vcard(_VCARD_FULL)
    assert c.full_name == "Ada Lovelace"
    assert c.emails == ["ada@example.com", "ada@engines.test"]
    assert c.phones == ["+1-555-0100", "+1-555-0199"]
    assert "Analytical Engines" in c.org


def test_parse_vcard_missing_org_and_contacts():
    c = contacts_ops.parse_vcard(_VCARD_MINIMAL)
    assert c.full_name == "No Org Person"
    assert c.emails == []
    assert c.phones == []
    assert c.org == ""


def test_parse_vcard_nameless_falls_back():
    c = contacts_ops.parse_vcard(_VCARD_NAMELESS)
    assert c.full_name == "(no name)"
    assert c.emails == ["ghost@example.com"]


def test_parse_vcard_garbage_returns_none():
    assert contacts_ops.parse_vcard("not a vcard at all") is None


def test_parse_vcard_reads_uid():
    text = "BEGIN:VCARD\r\nVERSION:3.0\r\nUID:ABC-123\r\nFN:Has UID\r\nEND:VCARD\r\n"
    assert contacts_ops.parse_vcard(text).uid == "ABC-123"


def test_build_vcard_round_trips():
    text = contacts_ops.build_vcard(
        "U-1", "Grace Hopper", ["grace@navy.mil", "g@x.com"], ["+1-555-7"], "US Navy"
    )
    back = contacts_ops.parse_vcard(text)
    assert back.uid == "U-1"
    assert back.full_name == "Grace Hopper"
    assert back.emails == ["grace@navy.mil", "g@x.com"]
    assert back.phones == ["+1-555-7"]
    assert back.org == "US Navy"


def test_list_contacts_skips_unparseable_and_caps_limit():
    client = _FakeContactsClient([_VCARD_FULL, "junk", _VCARD_MINIMAL])
    result = contacts_ops.list_contacts(client, limit=10)
    assert [c.full_name for c in result] == ["Ada Lovelace", "No Org Person"]
    assert contacts_ops.list_contacts(client, limit=1) == result[:1]


def test_search_contacts_matches_name_org_and_email():
    client = _FakeContactsClient([_VCARD_FULL, _VCARD_MINIMAL])
    assert [c.full_name for c in contacts_ops.search_contacts(client, "ada")] == ["Ada Lovelace"]
    assert [c.full_name for c in contacts_ops.search_contacts(client, "engines.test")] == [
        "Ada Lovelace"
    ]
    assert [c.full_name for c in contacts_ops.search_contacts(client, "analytical")] == [
        "Ada Lovelace"
    ]
    assert contacts_ops.search_contacts(client, "nonexistent") == []
