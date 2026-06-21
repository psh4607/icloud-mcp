"""Stateless CardDAV read operations.

vCards are fetched in bulk by ``ContactsClient`` and parsed here with ``vobject``.
Read-only: there is no create/update/delete path.
"""

from __future__ import annotations

import vobject

from .clients import ContactsClient
from .models import Contact


def _values(card, attr: str) -> list[str]:
    """All values for a possibly-repeated vCard property (e.g. EMAIL, TEL)."""
    items = getattr(card, f"{attr}_list", None)
    if not items:
        return []
    out = []
    for item in items:
        val = (item.value or "").strip()
        if val:
            out.append(val)
    return out


def parse_vcard(text: str) -> Contact | None:
    """Parse one vCard into a Contact, or None if it can't be read."""
    try:
        card = vobject.readOne(text)
    except Exception:
        return None

    fn = getattr(card, "fn", None)
    full_name = (fn.value.strip() if fn and fn.value else "") or "(no name)"

    org = ""
    org_field = getattr(card, "org", None)
    if org_field and org_field.value:
        parts = org_field.value if isinstance(org_field.value, list) else [org_field.value]
        org = " ".join(p.strip() for p in parts if p and p.strip())

    uid_field = getattr(card, "uid", None)
    uid = (uid_field.value.strip() if uid_field and uid_field.value else "")

    return Contact(
        uid=uid,
        full_name=full_name,
        emails=_values(card, "email"),
        phones=_values(card, "tel"),
        org=org,
    )


def build_vcard(
    uid: str, full_name: str, emails: list[str], phones: list[str], org: str = ""
) -> str:
    """Serialize a new vCard (v3.0) from structured fields."""
    card = vobject.vCard()
    card.add("uid").value = uid
    card.add("fn").value = full_name or "(no name)"
    # vCard requires N; derive a minimal structured name from the full name.
    n = card.add("n")
    parts = (full_name or "").split()
    n.value = vobject.vcard.Name(
        family=parts[-1] if len(parts) > 1 else "", given=parts[0] if parts else ""
    )
    for email in emails:
        card.add("email").value = email
    for phone in phones:
        card.add("tel").value = phone
    if org:
        card.add("org").value = [org]
    return card.serialize()


def list_contacts(client: ContactsClient, limit: int = 200) -> list[Contact]:
    """List contacts (parsed from all addressbooks), capped at ``limit``."""
    out: list[Contact] = []
    for text in client.fetch_vcards():
        contact = parse_vcard(text)
        if contact is not None:
            out.append(contact)
            if len(out) >= limit:
                break
    return out


def search_contacts(client: ContactsClient, query: str, limit: int = 50) -> list[Contact]:
    """Substring match (case-insensitive) over name, org, and email addresses."""
    needle = query.lower()
    out: list[Contact] = []
    for text in client.fetch_vcards():
        contact = parse_vcard(text)
        if contact is None:
            continue
        haystack = " ".join([contact.full_name, contact.org, *contact.emails]).lower()
        if needle in haystack:
            out.append(contact)
            if len(out) >= limit:
                break
    return out
