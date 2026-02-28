"""Tests for Gmail message parser — converts raw Gmail API responses to ParsedMessage.

TDD RED phase — these tests are written before the implementation.
"""

from __future__ import annotations

import base64

from app.services.message_parser import ParsedMessage, parse_gmail_message


def _b64url(text: str) -> str:
    """Encode text to URL-safe base64 (no padding) matching Gmail API format."""
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


# ---------------------------------------------------------------------------
# Fixtures — reusable raw Gmail API message payloads
# ---------------------------------------------------------------------------


def _simple_text_message() -> dict:
    """A simple plain-text message with typical headers."""
    return {
        "id": "msg_abc123",
        "threadId": "thread_xyz",
        "internalDate": "1700000000000",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Message-ID", "value": "<abc123@mail.gmail.com>"},
                {"name": "In-Reply-To", "value": "<parent@mail.gmail.com>"},
                {"name": "References", "value": "<root@mail.gmail.com> <parent@mail.gmail.com>"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "From", "value": "Alice Smith <alice@example.com>"},
                {"name": "To", "value": "Bob Jones <bob@example.com>, carol@example.com"},
                {"name": "Cc", "value": "Dave <dave@example.com>"},
                {"name": "Date", "value": "Tue, 14 Nov 2023 15:33:20 +0000"},
                {"name": "DKIM-Signature", "value": "should-be-stripped"},
                {"name": "ARC-Authentication-Results", "value": "should-be-stripped"},
                {"name": "Received", "value": "from mx.google.com; should-be-stripped"},
                {"name": "Authentication-Results", "value": "should-be-stripped"},
                {"name": "X-Google-DKIM-Signature", "value": "should-be-stripped"},
                {"name": "Content-Type", "value": "text/plain; charset=UTF-8"},
            ],
            "body": {"data": _b64url("Hello, this is a test email.")},
        },
    }


def _html_only_message() -> dict:
    """A message with only HTML body."""
    return {
        "id": "msg_html_only",
        "threadId": "thread_html",
        "internalDate": "1700000000000",
        "payload": {
            "mimeType": "text/html",
            "headers": [
                {"name": "Message-ID", "value": "<html1@mail.gmail.com>"},
                {"name": "Subject", "value": "HTML Only"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Date", "value": "Tue, 14 Nov 2023 15:33:20 +0000"},
            ],
            "body": {"data": _b64url("<html><body><p>Hello HTML</p></body></html>")},
        },
    }


def _multipart_alternative_message() -> dict:
    """A typical multipart/alternative message with both text and HTML."""
    return {
        "id": "msg_multipart",
        "threadId": "thread_multi",
        "internalDate": "1700000000000",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "Message-ID", "value": "<multi@mail.gmail.com>"},
                {"name": "Subject", "value": "Multipart Message"},
                {"name": "From", "value": "Multi Sender <multi@example.com>"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Date", "value": "Tue, 14 Nov 2023 15:33:20 +0000"},
            ],
            "body": {"size": 0},
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": _b64url("Plain text version")},
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": _b64url("<p>HTML version</p>")},
                },
            ],
        },
    }


def _multipart_mixed_message() -> dict:
    """A multipart/mixed message with an attachment."""
    return {
        "id": "msg_mixed",
        "threadId": "thread_mixed",
        "internalDate": "1700000000000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "Message-ID", "value": "<mixed@mail.gmail.com>"},
                {"name": "Subject", "value": "Mixed Message"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Date", "value": "Tue, 14 Nov 2023 15:33:20 +0000"},
            ],
            "body": {"size": 0},
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "body": {"size": 0},
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": _b64url("Nested plain text")},
                        },
                        {
                            "mimeType": "text/html",
                            "body": {"data": _b64url("<p>Nested HTML</p>")},
                        },
                    ],
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "report.pdf",
                    "body": {"attachmentId": "att_123", "size": 1024},
                },
            ],
        },
    }


def _no_reply_to_message() -> dict:
    """A message with no In-Reply-To or References headers."""
    return {
        "id": "msg_no_reply",
        "threadId": "thread_no_reply",
        "internalDate": "1700000000000",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Message-ID", "value": "<noreply@mail.gmail.com>"},
                {"name": "Subject", "value": "No Reply-To"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Date", "value": "Tue, 14 Nov 2023 15:33:20 +0000"},
            ],
            "body": {"data": _b64url("Message body")},
        },
    }


# ---------------------------------------------------------------------------
# ParsedMessage dataclass
# ---------------------------------------------------------------------------


class TestParsedMessage:
    """Tests for the ParsedMessage dataclass."""

    def test_parsed_message_has_expected_fields(self) -> None:
        msg = ParsedMessage(
            gmail_id="msg1",
            thread_id="t1",
            message_id_header="<msg@example.com>",
            in_reply_to=None,
            references_header=None,
            subject="Test",
            sender_email="test@example.com",
            sender_name=None,
            recipients={"to": [], "cc": []},
            gmail_date="2023-11-14T15:33:20+00:00",
            body_text=None,
            body_html=None,
            raw_headers={},
            has_attachments=False,
        )
        assert msg.gmail_id == "msg1"
        assert msg.sender_email == "test@example.com"


# ---------------------------------------------------------------------------
# Header extraction
# ---------------------------------------------------------------------------


class TestHeaderExtraction:
    """Tests for extracting specific headers from the Gmail message payload."""

    def test_extracts_message_id(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert result.message_id_header == "<abc123@mail.gmail.com>"

    def test_extracts_in_reply_to(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert result.in_reply_to == "<parent@mail.gmail.com>"

    def test_extracts_references_as_list(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert result.references_header == ["<root@mail.gmail.com>", "<parent@mail.gmail.com>"]

    def test_subject(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert result.subject == "Test Subject"

    def test_gmail_id(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert result.gmail_id == "msg_abc123"

    def test_thread_id(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert result.thread_id == "thread_xyz"

    def test_in_reply_to_is_none_when_missing(self) -> None:
        result = parse_gmail_message(_no_reply_to_message())
        assert result.in_reply_to is None

    def test_references_is_none_when_missing(self) -> None:
        result = parse_gmail_message(_no_reply_to_message())
        assert result.references_header is None

    def test_gmail_date_from_date_header(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        # Should be an ISO format datetime string
        assert "2023-11-14" in result.gmail_date


# ---------------------------------------------------------------------------
# Auth header stripping
# ---------------------------------------------------------------------------


class TestAuthHeaderStripping:
    """Tests that authentication/routing headers are stripped from raw_headers."""

    def test_dkim_headers_stripped(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        for key in result.raw_headers:
            assert not key.upper().startswith("DKIM-")

    def test_arc_headers_stripped(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        for key in result.raw_headers:
            assert not key.upper().startswith("ARC-")

    def test_received_headers_stripped(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        for key in result.raw_headers:
            assert key.upper() != "RECEIVED"

    def test_authentication_results_stripped(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        for key in result.raw_headers:
            assert key.upper() != "AUTHENTICATION-RESULTS"

    def test_x_google_dkim_stripped(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        for key in result.raw_headers:
            assert not key.upper().startswith("X-GOOGLE-DKIM")

    def test_non_auth_headers_preserved(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert "Content-Type" in result.raw_headers
        assert "Subject" in result.raw_headers

    def test_raw_headers_is_dict(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert isinstance(result.raw_headers, dict)


# ---------------------------------------------------------------------------
# Sender parsing
# ---------------------------------------------------------------------------


class TestSenderParsing:
    """Tests for parsing the From header into sender_email and sender_name."""

    def test_name_and_email_format(self) -> None:
        """Parse 'Name <email>' format."""
        result = parse_gmail_message(_simple_text_message())
        assert result.sender_email == "alice@example.com"
        assert result.sender_name == "Alice Smith"

    def test_email_only_format(self) -> None:
        """Parse bare 'email' format."""
        result = parse_gmail_message(_no_reply_to_message())
        assert result.sender_email == "sender@example.com"
        assert result.sender_name is None

    def test_angle_bracket_email_only(self) -> None:
        """Parse '<email>' format with no name."""
        msg = _simple_text_message()
        # Replace From header
        for h in msg["payload"]["headers"]:
            if h["name"] == "From":
                h["value"] = "<anon@example.com>"
        result = parse_gmail_message(msg)
        assert result.sender_email == "anon@example.com"
        assert result.sender_name is None

    def test_quoted_name_format(self) -> None:
        """Parse '"Quoted Name" <email>' format."""
        msg = _simple_text_message()
        for h in msg["payload"]["headers"]:
            if h["name"] == "From":
                h["value"] = '"Quoted Name" <quoted@example.com>'
        result = parse_gmail_message(msg)
        assert result.sender_email == "quoted@example.com"
        assert result.sender_name == "Quoted Name"


# ---------------------------------------------------------------------------
# Recipient parsing
# ---------------------------------------------------------------------------


class TestRecipientParsing:
    """Tests for parsing To and Cc into the recipients structure."""

    def test_to_recipients_parsed(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        to_list = result.recipients["to"]
        emails = [r["email"] for r in to_list]
        assert "bob@example.com" in emails
        assert "carol@example.com" in emails

    def test_cc_recipients_parsed(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        cc_list = result.recipients["cc"]
        emails = [r["email"] for r in cc_list]
        assert "dave@example.com" in emails

    def test_to_name_parsed(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        to_list = result.recipients["to"]
        bob = next(r for r in to_list if r["email"] == "bob@example.com")
        assert bob["name"] == "Bob Jones"

    def test_to_name_none_when_missing(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        to_list = result.recipients["to"]
        carol = next(r for r in to_list if r["email"] == "carol@example.com")
        assert carol["name"] is None

    def test_no_bcc_in_recipients(self) -> None:
        """BCC should never appear — Gmail API doesn't include it for received messages."""
        result = parse_gmail_message(_simple_text_message())
        assert "bcc" not in result.recipients

    def test_empty_cc_when_no_cc_header(self) -> None:
        result = parse_gmail_message(_no_reply_to_message())
        assert result.recipients["cc"] == []


# ---------------------------------------------------------------------------
# Body extraction
# ---------------------------------------------------------------------------


class TestBodyExtraction:
    """Tests for extracting body_text and body_html from message parts."""

    def test_plain_text_body_extracted(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert result.body_text == "Hello, this is a test email."
        assert result.body_html is None

    def test_html_only_body_extracted(self) -> None:
        result = parse_gmail_message(_html_only_message())
        assert result.body_html is not None
        assert "<p>Hello HTML</p>" in result.body_html
        assert result.body_text is None

    def test_multipart_alternative_both_extracted(self) -> None:
        result = parse_gmail_message(_multipart_alternative_message())
        assert result.body_text == "Plain text version"
        assert result.body_html == "<p>HTML version</p>"

    def test_nested_multipart_mixed_body_extracted(self) -> None:
        result = parse_gmail_message(_multipart_mixed_message())
        assert result.body_text == "Nested plain text"
        assert result.body_html == "<p>Nested HTML</p>"


# ---------------------------------------------------------------------------
# Base64url decoding
# ---------------------------------------------------------------------------


class TestBase64UrlDecoding:
    """Tests that body data is correctly decoded from Gmail's URL-safe base64."""

    def test_standard_ascii_decoded(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert result.body_text == "Hello, this is a test email."

    def test_unicode_decoded(self) -> None:
        msg = _simple_text_message()
        msg["payload"]["body"]["data"] = _b64url("Unicode: \u00e9\u00e0\u00fc\u00f1")
        result = parse_gmail_message(msg)
        assert result.body_text == "Unicode: \u00e9\u00e0\u00fc\u00f1"

    def test_padding_handled(self) -> None:
        """Gmail strips base64 padding — parser must handle this."""
        # "a" encodes to "YQ" without padding (normally "YQ==")
        msg = _simple_text_message()
        msg["payload"]["body"]["data"] = "YQ"
        result = parse_gmail_message(msg)
        assert result.body_text == "a"

    def test_empty_body_data(self) -> None:
        """When body data is empty string, body_text should be None."""
        msg = _simple_text_message()
        msg["payload"]["body"]["data"] = ""
        result = parse_gmail_message(msg)
        assert result.body_text is None


# ---------------------------------------------------------------------------
# Attachment detection
# ---------------------------------------------------------------------------


class TestAttachmentDetection:
    """Tests for detecting attachments."""

    def test_no_attachment_flag(self) -> None:
        result = parse_gmail_message(_simple_text_message())
        assert result.has_attachments is False

    def test_has_attachment_when_present(self) -> None:
        result = parse_gmail_message(_multipart_mixed_message())
        assert result.has_attachments is True

    def test_multipart_alternative_no_attachment(self) -> None:
        result = parse_gmail_message(_multipart_alternative_message())
        assert result.has_attachments is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge case handling."""

    def test_missing_body_key_in_payload(self) -> None:
        """When there's no body data at all, body_text should be None."""
        msg = _simple_text_message()
        msg["payload"]["body"] = {"size": 0}
        result = parse_gmail_message(msg)
        assert result.body_text is None

    def test_empty_parts_list(self) -> None:
        """When parts list is empty, body should be None."""
        msg = _multipart_alternative_message()
        msg["payload"]["parts"] = []
        result = parse_gmail_message(msg)
        assert result.body_text is None
        assert result.body_html is None

    def test_missing_headers_list(self) -> None:
        """When headers list is empty, should use sensible defaults."""
        msg: dict = {
            "id": "msg_no_headers",
            "threadId": "thread_no_headers",
            "internalDate": "1700000000000",
            "payload": {
                "mimeType": "text/plain",
                "headers": [],
                "body": {"data": _b64url("body")},
            },
        }
        result = parse_gmail_message(msg)
        assert result.message_id_header == ""
        assert result.subject == ""
        assert result.sender_email == ""
        assert result.sender_name is None
        assert result.raw_headers == {}

    def test_trailing_comma_in_to_header_produces_no_empty_entry(self) -> None:
        """Trailing commas should not produce empty recipient entries."""
        msg = _simple_text_message()
        for h in msg["payload"]["headers"]:
            if h["name"] == "To":
                h["value"] = "bob@example.com, , "
        result = parse_gmail_message(msg)
        # Should have only one recipient (empty parts skipped)
        assert len(result.recipients["to"]) == 1
        assert result.recipients["to"][0]["email"] == "bob@example.com"

    def test_quoted_comma_in_name_not_split(self) -> None:
        """Commas inside quoted names should not split the address."""
        msg = _simple_text_message()
        for h in msg["payload"]["headers"]:
            if h["name"] == "To":
                h["value"] = '"Last, First" <quoted@example.com>'
        result = parse_gmail_message(msg)
        assert len(result.recipients["to"]) == 1
        assert result.recipients["to"][0]["email"] == "quoted@example.com"
        assert result.recipients["to"][0]["name"] == "Last, First"

    def test_invalid_date_header_returns_raw_value(self) -> None:
        """When date cannot be parsed, return the raw value."""
        msg = _simple_text_message()
        for h in msg["payload"]["headers"]:
            if h["name"] == "Date":
                h["value"] = "not-a-valid-date"
        result = parse_gmail_message(msg)
        assert result.gmail_date == "not-a-valid-date"

    def test_nested_multipart_with_attachment_detected(self) -> None:
        """Attachments nested inside multipart/mixed > multipart/related."""
        msg: dict = {
            "id": "msg_nested_attach",
            "threadId": "thread_nested",
            "internalDate": "1700000000000",
            "payload": {
                "mimeType": "multipart/mixed",
                "headers": [
                    {"name": "Message-ID", "value": "<nested@example.com>"},
                    {"name": "Subject", "value": "Nested Attach"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Date", "value": "Tue, 14 Nov 2023 15:33:20 +0000"},
                ],
                "body": {"size": 0},
                "parts": [
                    {
                        "mimeType": "multipart/related",
                        "body": {"size": 0},
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "body": {"data": _b64url("text")},
                            },
                            {
                                "mimeType": "image/png",
                                "filename": "image.png",
                                "body": {"attachmentId": "att_1", "size": 512},
                            },
                        ],
                    },
                ],
            },
        }
        result = parse_gmail_message(msg)
        assert result.has_attachments is True
