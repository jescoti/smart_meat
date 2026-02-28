"""Tests for the LLM service — summarize_thread and extract_nuggets.

TDD RED phase -- these tests are written before the implementation.
All Anthropic API calls are mocked via unittest.mock.AsyncMock.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm import extract_nuggets, summarize_thread

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

MESSAGES = [
    {
        "sender_name": "Alice",
        "body_text": "Let's move the deadline to next Friday.",
        "gmail_date": "2024-06-10T10:00:00Z",
    },
    {
        "sender_name": "Bob",
        "body_text": "Sounds good. I'll update the project plan.",
        "gmail_date": "2024-06-10T11:00:00Z",
    },
]

MODEL = "claude-sonnet-4-5-20250514"
API_KEY = "test-anthropic-key"


# ---------------------------------------------------------------------------
# Helper to build mock Anthropic client
# ---------------------------------------------------------------------------


def _mock_anthropic_client(response_text: str) -> MagicMock:
    """Build a mock anthropic.AsyncAnthropic with a canned response."""
    mock_message = MagicMock()
    mock_content_block = MagicMock()
    mock_content_block.text = response_text
    mock_message.content = [mock_content_block]

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)
    return mock_client


# ---------------------------------------------------------------------------
# summarize_thread tests
# ---------------------------------------------------------------------------


class TestSummarizeThread:
    """Tests for summarize_thread."""

    async def test_returns_summary_string(self) -> None:
        mock_client = _mock_anthropic_client("Here is a summary of the thread.")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await summarize_thread(MESSAGES, MODEL, API_KEY)
        assert result == "Here is a summary of the thread."

    async def test_passes_model_to_api(self) -> None:
        mock_client = _mock_anthropic_client("Summary")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            await summarize_thread(MESSAGES, MODEL, API_KEY)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == MODEL

    async def test_passes_api_key_to_client(self) -> None:
        mock_client = _mock_anthropic_client("Summary")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client) as mock_cls:
            await summarize_thread(MESSAGES, MODEL, API_KEY)
        mock_cls.assert_called_once_with(api_key=API_KEY)

    async def test_includes_messages_in_prompt(self) -> None:
        mock_client = _mock_anthropic_client("Summary")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            await summarize_thread(MESSAGES, MODEL, API_KEY)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_message = call_kwargs["messages"][0]["content"]
        assert "Alice" in user_message
        assert "Bob" in user_message
        assert "deadline" in user_message

    async def test_sets_max_tokens(self) -> None:
        mock_client = _mock_anthropic_client("Summary")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            await summarize_thread(MESSAGES, MODEL, API_KEY)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "max_tokens" in call_kwargs
        assert call_kwargs["max_tokens"] > 0

    async def test_empty_messages_returns_empty_string(self) -> None:
        mock_client = _mock_anthropic_client("")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await summarize_thread([], MODEL, API_KEY)
        assert result == ""

    async def test_propagates_api_error(self) -> None:
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API error"))
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            with pytest.raises(RuntimeError, match="API error"):
                await summarize_thread(MESSAGES, MODEL, API_KEY)


# ---------------------------------------------------------------------------
# extract_nuggets tests
# ---------------------------------------------------------------------------


class TestExtractNuggets:
    """Tests for extract_nuggets."""

    async def test_returns_list_of_nugget_dicts(self) -> None:
        nuggets_json = json.dumps([
            {"title": "Deadline moved", "content": "Deadline moved to next Friday.", "tags": ["deadline"]},
        ])
        mock_client = _mock_anthropic_client(nuggets_json)
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await extract_nuggets(MESSAGES, MODEL, API_KEY)
        assert len(result) == 1
        assert result[0]["title"] == "Deadline moved"
        assert result[0]["content"] == "Deadline moved to next Friday."
        assert result[0]["tags"] == ["deadline"]

    async def test_returns_multiple_nuggets(self) -> None:
        nuggets_json = json.dumps([
            {"title": "Deadline moved", "content": "To next Friday.", "tags": ["deadline"]},
            {"title": "Plan update", "content": "Bob will update plan.", "tags": ["planning"]},
        ])
        mock_client = _mock_anthropic_client(nuggets_json)
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await extract_nuggets(MESSAGES, MODEL, API_KEY)
        assert len(result) == 2

    async def test_passes_model_to_api(self) -> None:
        mock_client = _mock_anthropic_client("[]")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            await extract_nuggets(MESSAGES, MODEL, API_KEY)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == MODEL

    async def test_passes_api_key_to_client(self) -> None:
        mock_client = _mock_anthropic_client("[]")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client) as mock_cls:
            await extract_nuggets(MESSAGES, MODEL, API_KEY)
        mock_cls.assert_called_once_with(api_key=API_KEY)

    async def test_includes_messages_in_prompt(self) -> None:
        mock_client = _mock_anthropic_client("[]")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            await extract_nuggets(MESSAGES, MODEL, API_KEY)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_message = call_kwargs["messages"][0]["content"]
        assert "Alice" in user_message
        assert "deadline" in user_message

    async def test_empty_messages_returns_empty_list(self) -> None:
        mock_client = _mock_anthropic_client("[]")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await extract_nuggets([], MODEL, API_KEY)
        assert result == []

    async def test_handles_json_wrapped_in_markdown(self) -> None:
        response = '```json\n[{"title": "T", "content": "C", "tags": []}]\n```'
        mock_client = _mock_anthropic_client(response)
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await extract_nuggets(MESSAGES, MODEL, API_KEY)
        assert len(result) == 1
        assert result[0]["title"] == "T"

    async def test_propagates_api_error(self) -> None:
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API error"))
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            with pytest.raises(RuntimeError, match="API error"):
                await extract_nuggets(MESSAGES, MODEL, API_KEY)

    async def test_returns_empty_list_on_invalid_json(self) -> None:
        mock_client = _mock_anthropic_client("not valid json")
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await extract_nuggets(MESSAGES, MODEL, API_KEY)
        assert result == []

    async def test_returns_empty_list_when_json_is_not_array(self) -> None:
        mock_client = _mock_anthropic_client('{"title": "not an array"}')
        with patch("app.services.llm.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await extract_nuggets(MESSAGES, MODEL, API_KEY)
        assert result == []
