"""Gmail API client — thin wrapper over Gmail REST API via httpx.

All API calls go to ``https://gmail.googleapis.com/gmail/v1/users/me/``.
An optional *client* parameter on the constructor allows tests to inject
a mock ``httpx.AsyncClient``.
"""

from __future__ import annotations

import asyncio

import httpx

_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"

# Maximum concurrent requests for batch operations.
_MAX_CONCURRENCY = 10


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class GmailAPIError(Exception):
    """Base error for all Gmail API failures."""

    def __init__(self, *, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Gmail API error {status_code}: {message}")


class GmailAuthError(GmailAPIError):
    """Raised on 401 Unauthorized — caller should refresh the access token."""

    def __init__(self) -> None:
        super().__init__(status_code=401, message="Unauthorized")


class GmailRateLimitError(GmailAPIError):
    """Raised on 429 Too Many Requests — caller should back off and retry."""

    def __init__(self, *, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(
            status_code=429,
            message=f"Rate limited, retry after {retry_after}s",
        )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GmailClient:
    """Async Gmail API client using httpx.

    Parameters
    ----------
    access_token:
        A valid Google OAuth access token with Gmail read scopes.
    client:
        Optional httpx.AsyncClient for dependency injection (testing).
    """

    def __init__(
        self,
        access_token: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._access_token = access_token
        self._client = client

    # -- helpers --

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _handle_error(self, response: httpx.Response) -> None:
        """Inspect the response status and raise the appropriate error.

        Called after every API request.  Successful responses (2xx) are ignored.
        """
        status = response.status_code
        if status < 400:
            return

        if status == 401:
            raise GmailAuthError()

        if status == 429:
            retry_after_raw = response.headers.get("Retry-After")
            retry_after = int(retry_after_raw) if retry_after_raw else 60
            raise GmailRateLimitError(retry_after=retry_after)

        raise GmailAPIError(status_code=status, message=f"HTTP {status}")

    async def _get(self, path: str, params: dict[str, str]) -> dict:
        """Perform a GET request to the Gmail API and return the JSON body."""
        url = f"{_BASE_URL}/{path}"
        if self._client is not None:
            resp = await self._client.get(url, headers=self._headers(), params=params)
        else:
            async with httpx.AsyncClient() as http_client:  # pragma: no cover
                resp = await http_client.get(url, headers=self._headers(), params=params)

        self._handle_error(resp)
        return resp.json()  # type: ignore[no-any-return]

    # -- public API --

    async def list_messages(
        self,
        query: str,
        page_token: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """List messages matching *query*.

        Parameters
        ----------
        query:
            Gmail search query, e.g. ``list:group@googlegroups.com``.
        page_token:
            Pagination token for subsequent pages.

        Returns
        -------
        tuple
            ``(messages, next_page_token)`` where *messages* is a list of
            ``{id, threadId}`` dicts and *next_page_token* is ``None`` when
            there are no more pages.
        """
        params: dict[str, str] = {"q": query}
        if page_token is not None:
            params["pageToken"] = page_token

        data = await self._get("messages", params)
        messages: list[dict] = data.get("messages", [])
        next_token: str | None = data.get("nextPageToken")
        return messages, next_token

    async def get_message(self, message_id: str) -> dict:
        """Fetch a single message by ID in ``full`` format.

        Parameters
        ----------
        message_id:
            The Gmail message ID.

        Returns
        -------
        dict
            The full Gmail message resource.
        """
        return await self._get(f"messages/{message_id}", {"format": "full"})

    async def batch_get_messages(self, message_ids: list[str]) -> list[dict]:
        """Fetch multiple messages concurrently (max 10 at a time).

        Parameters
        ----------
        message_ids:
            List of Gmail message IDs to fetch (up to 100).

        Returns
        -------
        list[dict]
            List of full Gmail message resources.
        """
        if not message_ids:
            return []

        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

        async def _fetch(mid: str) -> dict:
            async with semaphore:
                return await self.get_message(mid)

        results = await asyncio.gather(*[_fetch(mid) for mid in message_ids])
        return list(results)

    async def get_history(
        self,
        history_id: str,
        label_id: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """Get history records since *history_id*.

        Parameters
        ----------
        history_id:
            The starting history ID (exclusive).
        label_id:
            Optional label filter.

        Returns
        -------
        tuple
            ``(history_records, latest_history_id)`` where *history_records*
            is a list of history record dicts.
        """
        params: dict[str, str] = {"startHistoryId": history_id}
        if label_id is not None:
            params["labelId"] = label_id

        data = await self._get("history", params)
        history_records: list[dict] = data.get("history", [])
        latest_id: str | None = data.get("historyId")
        return history_records, latest_id
