"""Tests for Gmail API client — wraps Gmail REST API via httpx.

TDD RED phase — these tests are written before the implementation.
All external HTTP calls are mocked via AsyncMock on httpx.AsyncClient.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.gmail import (
    GmailAPIError,
    GmailAuthError,
    GmailClient,
    GmailRateLimitError,
)

ACCESS_TOKEN = "ya29.test-access-token"
_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(
    *,
    status_code: int = 200,
    json_data: dict | None = None,
) -> MagicMock:
    """Create a MagicMock that behaves like an httpx.Response.

    Uses MagicMock (not AsyncMock) because httpx.Response methods are sync.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# GmailClient instantiation
# ---------------------------------------------------------------------------


class TestGmailClientInit:
    """Tests for GmailClient construction."""

    def test_stores_access_token(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        assert client._access_token == ACCESS_TOKEN

    def test_accepts_injected_client(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        assert client._client is mock_client


# ---------------------------------------------------------------------------
# list_messages
# ---------------------------------------------------------------------------


class TestListMessages:
    """Tests for GmailClient.list_messages()."""

    async def test_returns_messages_and_next_page_token(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        response_data = {
            "messages": [{"id": "msg1", "threadId": "t1"}, {"id": "msg2", "threadId": "t2"}],
            "nextPageToken": "page2token",
        }
        mock_client.get.return_value = _make_mock_response(json_data=response_data)

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        messages, next_token = await client.list_messages("list:group@googlegroups.com")

        assert len(messages) == 2
        assert messages[0]["id"] == "msg1"
        assert next_token == "page2token"

    async def test_returns_none_token_when_no_more_pages(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        response_data = {
            "messages": [{"id": "msg1", "threadId": "t1"}],
        }
        mock_client.get.return_value = _make_mock_response(json_data=response_data)

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        messages, next_token = await client.list_messages("list:group@googlegroups.com")

        assert len(messages) == 1
        assert next_token is None

    async def test_returns_empty_list_when_no_messages(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        response_data: dict = {"resultSizeEstimate": 0}
        mock_client.get.return_value = _make_mock_response(json_data=response_data)

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        messages, next_token = await client.list_messages("list:nonexistent@googlegroups.com")

        assert messages == []
        assert next_token is None

    async def test_passes_query_parameter(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(
            json_data={"messages": [], "resultSizeEstimate": 0}
        )

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.list_messages("list:group@googlegroups.com")

        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["q"] == "list:group@googlegroups.com"

    async def test_passes_page_token_when_provided(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(
            json_data={"messages": [], "resultSizeEstimate": 0}
        )

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.list_messages("list:group@googlegroups.com", page_token="page2")

        call_kwargs = mock_client.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["pageToken"] == "page2"

    async def test_does_not_include_page_token_when_none(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(
            json_data={"messages": [], "resultSizeEstimate": 0}
        )

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.list_messages("list:group@googlegroups.com")

        call_kwargs = mock_client.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert "pageToken" not in params

    async def test_sends_authorization_header(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(
            json_data={"messages": [], "resultSizeEstimate": 0}
        )

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.list_messages("list:group@googlegroups.com")

        call_kwargs = mock_client.get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"

    async def test_calls_correct_url(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(
            json_data={"messages": [], "resultSizeEstimate": 0}
        )

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.list_messages("list:group@googlegroups.com")

        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert url == f"{_BASE_URL}/messages"


# ---------------------------------------------------------------------------
# get_message
# ---------------------------------------------------------------------------


class TestGetMessage:
    """Tests for GmailClient.get_message()."""

    async def test_returns_full_message(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        message_data = {
            "id": "msg1",
            "threadId": "t1",
            "payload": {
                "headers": [{"name": "Subject", "value": "Test"}],
                "body": {"data": "dGVzdA=="},
            },
        }
        mock_client.get.return_value = _make_mock_response(json_data=message_data)

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        result = await client.get_message("msg1")

        assert result["id"] == "msg1"
        assert result["payload"]["headers"][0]["name"] == "Subject"

    async def test_calls_correct_url_with_format_full(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(json_data={"id": "msg1"})

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.get_message("msg1")

        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert url == f"{_BASE_URL}/messages/msg1"
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        assert params["format"] == "full"

    async def test_sends_authorization_header(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(json_data={"id": "msg1"})

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.get_message("msg1")

        call_kwargs = mock_client.get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"


# ---------------------------------------------------------------------------
# batch_get_messages
# ---------------------------------------------------------------------------


class TestBatchGetMessages:
    """Tests for GmailClient.batch_get_messages()."""

    async def test_returns_all_messages(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        # Each call to get returns a different message
        responses = [
            _make_mock_response(json_data={"id": f"msg{i}"}) for i in range(3)
        ]
        mock_client.get.side_effect = responses

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        result = await client.batch_get_messages(["msg0", "msg1", "msg2"])

        assert len(result) == 3
        ids = {msg["id"] for msg in result}
        assert ids == {"msg0", "msg1", "msg2"}

    async def test_returns_empty_list_for_empty_input(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        result = await client.batch_get_messages([])
        assert result == []

    async def test_respects_concurrency_limit(self) -> None:
        """Verify that at most 10 requests run concurrently."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        concurrent_count = 0
        max_concurrent = 0

        async def _mock_get(*args: object, **kwargs: object) -> MagicMock:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.01)
            concurrent_count -= 1
            return _make_mock_response(json_data={"id": "msg"})

        mock_client.get = _mock_get  # type: ignore[assignment]

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        message_ids = [f"msg{i}" for i in range(20)]
        await client.batch_get_messages(message_ids)

        assert max_concurrent <= 10


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    """Tests for GmailClient.get_history()."""

    async def test_returns_history_and_latest_id(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        response_data = {
            "history": [
                {"id": "12345", "messagesAdded": [{"message": {"id": "msg1"}}]},
                {"id": "12346", "messagesAdded": [{"message": {"id": "msg2"}}]},
            ],
            "historyId": "12347",
        }
        mock_client.get.return_value = _make_mock_response(json_data=response_data)

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        history_records, latest_id = await client.get_history("12344")

        assert len(history_records) == 2
        assert latest_id == "12347"

    async def test_returns_empty_when_no_history(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        response_data = {"historyId": "12344"}
        mock_client.get.return_value = _make_mock_response(json_data=response_data)

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        history_records, latest_id = await client.get_history("12344")

        assert history_records == []
        assert latest_id == "12344"

    async def test_passes_start_history_id(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(
            json_data={"historyId": "12344"}
        )

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.get_history("12344")

        call_kwargs = mock_client.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["startHistoryId"] == "12344"

    async def test_passes_label_id_when_provided(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(
            json_data={"historyId": "12344"}
        )

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.get_history("12344", label_id="INBOX")

        call_kwargs = mock_client.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["labelId"] == "INBOX"

    async def test_does_not_include_label_id_when_none(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(
            json_data={"historyId": "12344"}
        )

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.get_history("12344")

        call_kwargs = mock_client.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert "labelId" not in params

    async def test_calls_correct_url(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(
            json_data={"historyId": "12344"}
        )

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.get_history("12344")

        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert url == f"{_BASE_URL}/history"

    async def test_sends_authorization_header(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(
            json_data={"historyId": "12344"}
        )

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.get_history("12344")

        call_kwargs = mock_client.get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestGmailClientErrors:
    """Tests for GmailClient error handling."""

    async def test_raises_rate_limit_error_on_429(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=429)
        resp.headers = {"Retry-After": "30"}
        mock_client.get.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailRateLimitError) as exc_info:
            await client.list_messages("test query")

        assert exc_info.value.retry_after == 30

    async def test_rate_limit_error_defaults_retry_after_when_missing(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=429)
        resp.headers = {}
        mock_client.get.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailRateLimitError) as exc_info:
            await client.list_messages("test query")

        assert exc_info.value.retry_after == 60

    async def test_raises_auth_error_on_401(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=401)
        mock_client.get.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailAuthError):
            await client.list_messages("test query")

    async def test_raises_api_error_on_other_errors(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=500)
        mock_client.get.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailAPIError) as exc_info:
            await client.list_messages("test query")

        assert exc_info.value.status_code == 500

    async def test_api_error_contains_message(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=503)
        mock_client.get.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailAPIError) as exc_info:
            await client.get_message("msg1")

        assert "503" in str(exc_info.value)

    async def test_get_message_raises_auth_error_on_401(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=401)
        mock_client.get.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailAuthError):
            await client.get_message("msg1")

    async def test_get_message_raises_rate_limit_on_429(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=429)
        resp.headers = {"Retry-After": "10"}
        mock_client.get.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailRateLimitError):
            await client.get_message("msg1")

    async def test_get_history_raises_auth_error_on_401(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=401)
        mock_client.get.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailAuthError):
            await client.get_history("12344")

    async def test_get_history_raises_rate_limit_on_429(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=429)
        resp.headers = {"Retry-After": "5"}
        mock_client.get.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailRateLimitError):
            await client.get_history("12344")

    async def test_get_history_raises_api_error_on_500(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=500)
        mock_client.get.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailAPIError):
            await client.get_history("12344")


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Tests for the Gmail exception class hierarchy."""

    def test_gmail_api_error_is_base(self) -> None:
        err = GmailAPIError(status_code=500, message="Internal error")
        assert isinstance(err, Exception)
        assert err.status_code == 500
        assert err.message == "Internal error"

    def test_gmail_auth_error_inherits_from_api_error(self) -> None:
        err = GmailAuthError()
        assert isinstance(err, GmailAPIError)

    def test_gmail_rate_limit_error_inherits_from_api_error(self) -> None:
        err = GmailRateLimitError(retry_after=30)
        assert isinstance(err, GmailAPIError)
        assert err.retry_after == 30

    def test_gmail_rate_limit_error_str_includes_retry_after(self) -> None:
        err = GmailRateLimitError(retry_after=42)
        assert "42" in str(err)

    def test_gmail_api_error_str_includes_status_and_message(self) -> None:
        err = GmailAPIError(status_code=404, message="Not found")
        assert "404" in str(err)
        assert "Not found" in str(err)

    def test_gmail_auth_error_has_401_status(self) -> None:
        err = GmailAuthError()
        assert err.status_code == 401


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------


class TestSendMessage:
    """Tests for GmailClient.send_message()."""

    async def test_sends_raw_message_and_returns_response(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        response_data = {"id": "sent-msg-id", "threadId": "thread-id", "labelIds": ["SENT"]}
        mock_client.post.return_value = _make_mock_response(json_data=response_data)

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        result = await client.send_message("raw-rfc2822-message-content")

        assert result["id"] == "sent-msg-id"
        assert result["threadId"] == "thread-id"

    async def test_calls_correct_url(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response(json_data={"id": "sent"})

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.send_message("raw-message")

        call_args = mock_client.post.call_args
        url = call_args[0][0]
        assert url == f"{_BASE_URL}/messages/send"

    async def test_sends_base64url_encoded_body(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response(json_data={"id": "sent"})

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.send_message("From: test@example.com\r\nSubject: Test\r\n\r\nBody")

        call_args = mock_client.post.call_args
        json_body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "raw" in json_body
        # The raw value should be a base64url-encoded string
        import base64
        decoded = base64.urlsafe_b64decode(json_body["raw"] + "==").decode("utf-8")
        assert "From: test@example.com" in decoded

    async def test_sends_authorization_header(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response(json_data={"id": "sent"})

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        await client.send_message("raw-message")

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"

    async def test_raises_auth_error_on_401(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=401)
        mock_client.post.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailAuthError):
            await client.send_message("raw-message")

    async def test_raises_rate_limit_error_on_429(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=429)
        resp.headers = {"Retry-After": "15"}
        mock_client.post.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailRateLimitError):
            await client.send_message("raw-message")

    async def test_raises_api_error_on_500(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_mock_response(status_code=500)
        mock_client.post.return_value = resp

        client = GmailClient(ACCESS_TOKEN, client=mock_client)
        with pytest.raises(GmailAPIError):
            await client.send_message("raw-message")
