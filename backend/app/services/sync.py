"""Sync service — fetches messages from Gmail and stores them in the database.

Supports both full sync (first time) and incremental sync (using history_id).
Handles authentication errors with automatic token refresh, rate limit errors,
and general failures with appropriate status updates.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import decrypt, encrypt
from app.db.models import Group, GroupSyncStatus, Message, User
from app.services import google_auth
from app.services.gmail import GmailAuthError, GmailClient, GmailRateLimitError
from app.services.message_parser import parse_gmail_message


async def sync_group(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
    encryption_key: str,
    client_id: str,
    client_secret: str,
) -> None:
    """Sync messages from Gmail for a group.

    Steps:
        1. Load group and user from DB.
        2. Decrypt user's access token.
        3. Create GmailClient.
        4. If group has gmail_history_id, do incremental sync. Otherwise full sync.
        5. Fetch messages in batches.
        6. Parse and upsert messages (dedup by gmail_id).
        7. Update progress.
        8. On success: set idle, update history_id.
        9. On error: set error status with message.

    Args:
        group_id: The group to sync.
        user_id: The user who owns the group (for token access).
        session: Database session.
        encryption_key: For decrypting/encrypting tokens.
        client_id: Google OAuth client ID.
        client_secret: Google OAuth client secret.

    Raises:
        ValueError: If group or user not found.
    """
    # 1. Load group
    result = await session.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise ValueError(f"Group not found: {group_id}")

    # 2. Load user
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User not found: {user_id}")

    # 3. Decrypt access token
    access_token = decrypt(user.encrypted_access_token, encryption_key)

    # 4. Create client and attempt sync
    gmail = GmailClient(access_token)

    try:
        await _do_sync(gmail, group, session)
    except GmailAuthError:
        # Attempt token refresh and retry once
        try:
            access_token = await _refresh_token(
                user, session, encryption_key, client_id, client_secret
            )
            gmail = GmailClient(access_token)
            try:
                await _do_sync(gmail, group, session)
            except GmailAuthError:
                group.sync_status = GroupSyncStatus.error
                group.sync_error_message = "Authentication failed after token refresh"
                await session.commit()
                return
        except Exception:
            group.sync_status = GroupSyncStatus.error
            group.sync_error_message = "Failed to refresh authentication token"
            await session.commit()
            return
    except GmailRateLimitError as exc:
        group.sync_status = GroupSyncStatus.error
        group.sync_error_message = f"Rate limited. Retry after {exc.retry_after} seconds"
        await session.commit()
        return
    except Exception as exc:
        group.sync_status = GroupSyncStatus.error
        group.sync_error_message = str(exc)
        await session.commit()
        return

    # Success
    group.sync_status = GroupSyncStatus.idle
    await session.commit()


async def _do_sync(
    gmail: GmailClient,
    group: Group,
    session: AsyncSession,
) -> None:
    """Execute the sync, either full or incremental.

    Args:
        gmail: Authenticated Gmail client.
        group: The group to sync.
        session: Database session.
    """
    if group.gmail_history_id is not None:
        await _incremental_sync(gmail, group, session)
    else:
        await _full_sync(gmail, group, session)


async def _full_sync(
    gmail: GmailClient,
    group: Group,
    session: AsyncSession,
) -> None:
    """Full sync — list all messages matching the group email and fetch them.

    Args:
        gmail: Authenticated Gmail client.
        group: The group to sync.
        session: Database session.
    """
    query = f"list:{group.google_group_email}"
    all_message_ids: list[str] = []
    page_token: str | None = None

    # Collect all message IDs
    while True:
        messages, next_token = await gmail.list_messages(query, page_token)
        all_message_ids.extend(m["id"] for m in messages)

        group.sync_progress_total = len(all_message_ids)
        group.sync_progress_current = 0

        if next_token is None:
            break
        page_token = next_token

        # Fetch and store this batch
        if messages:
            raw_messages = await gmail.batch_get_messages([m["id"] for m in messages])
            await _store_messages(raw_messages, group, session)
            group.sync_progress_current = len(all_message_ids)
            await session.commit()

    # Fetch any remaining messages from the last page
    # (the last page messages haven't been fetched yet if loop ended normally)
    if all_message_ids:
        # Fetch all messages from the last page (not yet fetched in the loop)
        if page_token is None and all_message_ids:
            raw_messages = await gmail.batch_get_messages(all_message_ids)
            await _store_messages(raw_messages, group, session)
            group.sync_progress_current = len(all_message_ids)
            await session.commit()


async def _incremental_sync(
    gmail: GmailClient,
    group: Group,
    session: AsyncSession,
) -> None:
    """Incremental sync — use history API to get new messages since last sync.

    Args:
        gmail: Authenticated Gmail client.
        group: The group to sync.
        session: Database session.
    """
    history_records, latest_history_id = await gmail.get_history(
        group.gmail_history_id, label_id=None
    )

    # Extract new message IDs from history
    new_message_ids: list[str] = []
    for record in history_records:
        for added in record.get("messagesAdded", []):
            msg_id = added.get("message", {}).get("id")
            if msg_id:
                new_message_ids.append(msg_id)

    if new_message_ids:
        group.sync_progress_total = len(new_message_ids)
        group.sync_progress_current = 0

        raw_messages = await gmail.batch_get_messages(new_message_ids)
        await _store_messages(raw_messages, group, session)
        group.sync_progress_current = len(new_message_ids)

    # Update history ID
    if latest_history_id is not None:
        group.gmail_history_id = latest_history_id

    await session.commit()


async def _store_messages(
    raw_messages: list[dict],
    group: Group,
    session: AsyncSession,
) -> None:
    """Parse and store messages, deduplicating by gmail_id.

    Args:
        raw_messages: Raw Gmail API message dicts.
        group: The group to associate messages with.
        session: Database session.
    """
    for raw in raw_messages:
        parsed = parse_gmail_message(raw)

        # Dedup check
        existing = await session.execute(
            select(Message).where(Message.gmail_id == parsed.gmail_id)
        )
        if existing.scalar_one_or_none() is not None:
            continue

        message = Message(
            group_id=group.id,
            gmail_id=parsed.gmail_id,
            message_id_header=parsed.message_id_header,
            in_reply_to=parsed.in_reply_to,
            references_header=parsed.references_header,
            subject=parsed.subject,
            sender_email=parsed.sender_email,
            sender_name=parsed.sender_name,
            recipients=parsed.recipients,
            date=(
                datetime.fromisoformat(parsed.gmail_date)
                if parsed.gmail_date
                else datetime.now(tz=UTC)
            ),
            body_text=parsed.body_text,
            body_html=parsed.body_html,
            raw_headers=parsed.raw_headers,
            has_attachments=parsed.has_attachments,
        )
        session.add(message)


async def _refresh_token(
    user: User,
    session: AsyncSession,
    encryption_key: str,
    client_id: str,
    client_secret: str,
) -> str:
    """Refresh the user's Google access token.

    Args:
        user: The user whose token to refresh.
        session: Database session.
        encryption_key: For decrypting/encrypting tokens.
        client_id: Google OAuth client ID.
        client_secret: Google OAuth client secret.

    Returns:
        The new access token (plaintext).
    """
    refresh_token = decrypt(user.encrypted_refresh_token, encryption_key)
    new_tokens = await google_auth.refresh_access_token(
        refresh_token, client_id, client_secret
    )

    new_access_token = new_tokens["access_token"]
    user.encrypted_access_token = encrypt(new_access_token, encryption_key)
    user.token_expires_at = datetime.now(tz=UTC) + timedelta(
        seconds=new_tokens.get("expires_in", 3600)
    )

    if "refresh_token" in new_tokens:
        user.encrypted_refresh_token = encrypt(new_tokens["refresh_token"], encryption_key)

    await session.commit()
    return new_access_token
