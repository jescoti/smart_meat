"""Gmail message parser — converts raw Gmail API responses to structured data.

Parses a Gmail API message resource (``format=full``) into a ``ParsedMessage``
dataclass whose fields map directly to the ``Message`` ORM model columns.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from email.utils import (
    parseaddr,
    parsedate_to_datetime,
)

# Headers whose names start with these prefixes (case-insensitive) are stripped
# from raw_headers because they contain authentication/routing metadata.
_STRIPPED_PREFIXES = ("DKIM-", "ARC-", "X-GOOGLE-DKIM")
_STRIPPED_EXACT = ("RECEIVED", "AUTHENTICATION-RESULTS")


@dataclass
class ParsedMessage:
    """Structured representation of a parsed Gmail message.

    Field names match the ``Message`` ORM model columns.
    """

    gmail_id: str
    thread_id: str
    message_id_header: str
    in_reply_to: str | None
    references_header: list[str] | None
    subject: str
    sender_email: str
    sender_name: str | None
    recipients: dict[str, list[dict[str, str | None]]]
    gmail_date: str
    body_text: str | None
    body_html: str | None
    raw_headers: dict[str, str]
    has_attachments: bool


def parse_gmail_message(raw_message: dict) -> ParsedMessage:
    """Parse a Gmail API message response into a ``ParsedMessage``.

    Parameters
    ----------
    raw_message:
        A Gmail API message resource as returned by ``messages.get(format=full)``.

    Returns
    -------
    ParsedMessage
        A structured dataclass with all extracted fields.
    """
    payload = raw_message["payload"]
    headers_list: list[dict[str, str]] = payload.get("headers", [])

    # Build a lookup for quick header access
    header_map: dict[str, str] = {}
    for h in headers_list:
        header_map[h["name"]] = h["value"]

    # -- Header extraction --
    message_id_header = header_map.get("Message-ID", "")
    in_reply_to = header_map.get("In-Reply-To")
    references_raw = header_map.get("References")
    references_header = _parse_references(references_raw) if references_raw else None
    subject = header_map.get("Subject", "")
    from_header = header_map.get("From", "")
    to_header = header_map.get("To", "")
    cc_header = header_map.get("Cc", "")
    date_header = header_map.get("Date", "")

    # -- Sender parsing --
    sender_name, sender_email = _parse_address(from_header)

    # -- Recipient parsing --
    to_recipients = _parse_address_list(to_header) if to_header else []
    cc_recipients = _parse_address_list(cc_header) if cc_header else []
    recipients = {"to": to_recipients, "cc": cc_recipients}

    # -- Date parsing --
    gmail_date = _parse_date(date_header)

    # -- Body extraction --
    body_text, body_html = _extract_body(payload)

    # -- Attachment detection --
    has_attachments = _detect_attachments(payload)

    # -- Raw headers (stripped of auth headers) --
    raw_headers = _build_raw_headers(headers_list)

    return ParsedMessage(
        gmail_id=raw_message["id"],
        thread_id=raw_message["threadId"],
        message_id_header=message_id_header,
        in_reply_to=in_reply_to,
        references_header=references_header,
        subject=subject,
        sender_email=sender_email,
        sender_name=sender_name,
        recipients=recipients,
        gmail_date=gmail_date,
        body_text=body_text,
        body_html=body_html,
        raw_headers=raw_headers,
        has_attachments=has_attachments,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_references(raw: str) -> list[str]:
    """Split a References header value into individual message IDs."""
    # References header is space-separated message IDs like "<a@b> <c@d>"
    return re.findall(r"<[^>]+>", raw)


def _parse_address(raw: str) -> tuple[str | None, str]:
    """Parse a single email address from a From header value.

    Returns (name, email).  Name is None if not present.
    """
    name, email = parseaddr(raw)
    if not email:
        # Fallback for bare addresses
        email = raw.strip().strip("<>")
    name = name.strip('"').strip() if name else None
    return name if name else None, email


def _parse_address_list(raw: str) -> list[dict[str, str | None]]:
    """Parse a comma-separated list of addresses into a list of dicts."""
    result: list[dict[str, str | None]] = []
    # Split on commas, but respect quoted names
    parts = _split_addresses(raw)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        name, email = _parse_address(part)
        result.append({"email": email, "name": name})
    return result


def _split_addresses(raw: str) -> list[str]:
    """Split a header value on commas, respecting quoted strings."""
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    in_angle = False
    for ch in raw:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == "<" and not in_quotes:
            in_angle = True
        elif ch == ">" and not in_quotes:
            in_angle = False
        elif ch == "," and not in_quotes and not in_angle:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _parse_date(date_header: str) -> str:
    """Parse an RFC 2822 date string into ISO 8601 format."""
    if not date_header:
        return ""
    try:
        dt = parsedate_to_datetime(date_header)
        return dt.isoformat()
    except (ValueError, TypeError):
        return date_header


def _decode_body_data(data: str) -> str | None:
    """Decode a base64url-encoded body part from the Gmail API."""
    if not data:
        return None
    # Gmail uses URL-safe base64 without padding
    # Add padding if needed
    padded = data + "=" * (4 - len(data) % 4) if len(data) % 4 else data
    decoded_bytes = base64.urlsafe_b64decode(padded)
    return decoded_bytes.decode("utf-8")


def _extract_body(payload: dict) -> tuple[str | None, str | None]:
    """Extract body_text and body_html from the message payload.

    Handles:
    - Simple text/plain or text/html payload
    - multipart/alternative with text and html parts
    - multipart/mixed with nested multipart/alternative
    """
    mime_type = payload.get("mimeType", "")
    body_text: str | None = None
    body_html: str | None = None

    # Simple single-part message
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        body_text = _decode_body_data(data)
        return body_text, None

    if mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        body_html = _decode_body_data(data)
        return None, body_html

    # Multipart message — recurse into parts
    parts = payload.get("parts", [])
    for part in parts:
        part_mime = part.get("mimeType", "")

        if part_mime == "text/plain" and body_text is None:
            data = part.get("body", {}).get("data", "")
            body_text = _decode_body_data(data)

        elif part_mime == "text/html" and body_html is None:
            data = part.get("body", {}).get("data", "")
            body_html = _decode_body_data(data)

        elif part_mime.startswith("multipart/"):
            # Recurse into nested multipart
            nested_text, nested_html = _extract_body(part)
            if nested_text is not None and body_text is None:
                body_text = nested_text
            if nested_html is not None and body_html is None:
                body_html = nested_html

    return body_text, body_html


def _detect_attachments(payload: dict) -> bool:
    """Check if the message has any attachments."""
    parts = payload.get("parts", [])
    for part in parts:
        if part.get("filename"):
            return True
        if part.get("mimeType", "").startswith("multipart/"):
            if _detect_attachments(part):
                return True
    return False


def _should_strip_header(name: str) -> bool:
    """Check if a header should be stripped from raw_headers."""
    upper = name.upper()
    for prefix in _STRIPPED_PREFIXES:
        if upper.startswith(prefix):
            return True
    return upper in _STRIPPED_EXACT


def _build_raw_headers(headers_list: list[dict[str, str]]) -> dict[str, str]:
    """Build raw_headers dict, stripping auth/routing headers."""
    result: dict[str, str] = {}
    for h in headers_list:
        name = h["name"]
        if not _should_strip_header(name):
            result[name] = h["value"]
    return result
