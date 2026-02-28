"""LLM service — Claude API integration for thread summarization and nugget extraction.

Provides two core functions:
- ``summarize_thread``: Generate a human-readable summary of a message thread.
- ``extract_nuggets``: Extract key facts, decisions, and knowledge nuggets from messages.
"""

from __future__ import annotations

import json
import re

import anthropic


def _format_messages(messages: list[dict]) -> str:
    """Format a list of message dicts into a readable prompt string."""
    parts: list[str] = []
    for msg in messages:
        sender = msg.get("sender_name", "Unknown")
        date = msg.get("gmail_date", "")
        body = msg.get("body_text", "")
        parts.append(f"[{date}] {sender}:\n{body}")
    return "\n\n".join(parts)


async def summarize_thread(
    messages: list[dict],
    model: str,
    api_key: str,
) -> str:
    """Summarize a thread of messages using Claude.

    Args:
        messages: List of message dicts with sender_name, body_text, gmail_date.
        model: The Claude model to use.
        api_key: The Anthropic API key.

    Returns:
        A summary string. Empty string if messages is empty.
    """
    if not messages:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": "Summarize an empty thread."}],
        )
        return response.content[0].text

    formatted = _format_messages(messages)
    prompt = (
        "Summarize the following email thread concisely. "
        "Focus on key decisions, action items, and important information.\n\n"
        f"{formatted}"
    )

    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _parse_json_response(text: str) -> list[dict]:
    """Parse a JSON array from the response, handling markdown code fences."""
    # Strip markdown code fences if present
    stripped = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    stripped = re.sub(r"\n?```\s*$", "", stripped)

    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return []

    if not isinstance(parsed, list):
        return []

    return parsed


async def extract_nuggets(
    messages: list[dict],
    model: str,
    api_key: str,
) -> list[dict]:
    """Extract knowledge nuggets from a thread of messages using Claude.

    Args:
        messages: List of message dicts with sender_name, body_text, gmail_date.
        model: The Claude model to use.
        api_key: The Anthropic API key.

    Returns:
        List of dicts with title, content, and tags keys.
        Returns empty list if messages is empty or extraction fails.
    """
    if not messages:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": "Extract nuggets from empty thread."}],
        )
        return _parse_json_response(response.content[0].text)

    formatted = _format_messages(messages)
    prompt = (
        "Extract key facts, decisions, and knowledge nuggets from the following "
        "email thread. Return a JSON array of objects, each with:\n"
        '- "title": short descriptive title\n'
        '- "content": detailed description of the nugget\n'
        '- "tags": list of relevant tag strings\n\n'
        "Return ONLY the JSON array, no other text.\n\n"
        f"{formatted}"
    )

    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json_response(response.content[0].text)
