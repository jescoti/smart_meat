"""Reply API endpoint — compose and send replies to mailing list threads.

Provides a POST /api/threads/{thread_id}/reply endpoint that constructs
an RFC 5322 email, sends it via Gmail API, and stores the sent message
locally.  Uses the same factory-router pattern as other routers for testability.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import decrypt
from app.db.models import AuditLog, Group, Message, Thread, ThreadMessage, User
from app.services.gmail import GmailAPIError, GmailClient

ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")


class ReplyRequest(BaseModel):
    """Request body for the reply endpoint."""

    parent_message_id: str
    body_text: str

    @field_validator("body_text")
    @classmethod
    def body_text_not_empty(cls, v: str) -> str:
        """Validate that body_text is not empty or whitespace-only."""
        if not v.strip():
            msg = "body_text must not be empty"
            raise ValueError(msg)
        return v


async def _get_session_dependency() -> AsyncSession:  # pragma: no cover
    """Placeholder dependency -- overridden in tests and by the real app."""
    raise NotImplementedError("Must override _get_session_dependency")


def _get_user_id(
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> str | None:
    """Extract user_id from request state (auth middleware) or X-User-Id header (testing)."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        return str(user_id)
    return x_user_id


def _build_reply_subject(thread_subject: str) -> str:
    """Build the reply subject, adding 'Re: ' prefix if not already present."""
    if thread_subject.lower().startswith("re: "):
        return thread_subject
    return f"Re: {thread_subject}"


def _build_rfc5322_message(
    *,
    from_email: str,
    to_email: str,
    subject: str,
    body_text: str,
    in_reply_to: str,
    references: list[str],
    message_id: str,
) -> str:
    """Build a complete RFC 5322 email message as a string.

    Parameters
    ----------
    from_email:
        The sender's email address.
    to_email:
        The recipient email address (group email).
    subject:
        The reply subject line.
    body_text:
        The plain text body of the reply.
    in_reply_to:
        The Message-ID of the parent message.
    references:
        List of Message-IDs forming the reference chain.
    message_id:
        The Message-ID for this reply.

    Returns
    -------
    str
        A complete RFC 5322 formatted message.
    """
    references_str = " ".join(references)
    lines = [
        f"From: {from_email}",
        f"To: {to_email}",
        f"Subject: {subject}",
        f"Message-ID: {message_id}",
        f"In-Reply-To: {in_reply_to}",
        f"References: {references_str}",
        "MIME-Version: 1.0",
        'Content-Type: text/plain; charset="UTF-8"',
        "",
        body_text,
    ]
    return "\r\n".join(lines)


def create_reply_router() -> APIRouter:
    """Create an APIRouter with the reply endpoint.

    Returns:
        A configured FastAPI APIRouter.
    """
    router = APIRouter(tags=["reply"])

    _session_dep = Depends(_get_session_dependency)

    @router.post("/api/threads/{thread_id}/reply")
    async def send_reply(
        thread_id: uuid.UUID,
        body: ReplyRequest,
        session: AsyncSession = _session_dep,
        user_id: str | None = Depends(_get_user_id),
    ) -> JSONResponse:
        """Compose and send a reply to a thread via Gmail."""
        # 1. Authenticate
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing user ID"},
            )

        # 2. Load the parent message
        parent_msg_result = await session.execute(
            select(Message).where(Message.id == uuid.UUID(body.parent_message_id))
        )
        parent_msg = parent_msg_result.scalar_one_or_none()
        if parent_msg is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": "Parent message not found"},
            )

        # 3. Load the thread
        thread_result = await session.execute(
            select(Thread).where(Thread.id == thread_id)
        )
        thread = thread_result.scalar_one_or_none()
        if thread is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": "Thread not found"},
            )

        # 4. Verify group ownership
        group_result = await session.execute(
            select(Group).where(
                Group.id == thread.group_id,
                Group.owner_id == uuid.UUID(user_id),
            )
        )
        group = group_result.scalar_one_or_none()
        if group is None:
            return JSONResponse(
                status_code=403,
                content={"error": "forbidden", "message": "Not authorized for this group"},
            )

        # 5. Load user (for email and access token)
        user_result = await session.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "User not found"},
            )

        # 6. Construct RFC 5322 email
        new_message_id = f"<{uuid.uuid4()}@smartmeat.app>"
        reply_subject = _build_reply_subject(thread.subject)

        parent_refs: list[str] = parent_msg.references_header or []
        references = parent_refs + [parent_msg.message_id_header]

        raw_message = _build_rfc5322_message(
            from_email=user.email,
            to_email=group.google_group_email,
            subject=reply_subject,
            body_text=body.body_text,
            in_reply_to=parent_msg.message_id_header,
            references=references,
            message_id=new_message_id,
        )

        # 7. Send via Gmail
        access_token = decrypt(user.encrypted_access_token, ENCRYPTION_KEY)
        gmail_client = GmailClient(access_token)
        try:
            send_result = await gmail_client.send_message(raw_message)
        except GmailAPIError:
            return JSONResponse(
                status_code=502,
                content={"error": "gmail_error", "message": "Failed to send message via Gmail"},
            )

        # 8. Store the sent message locally
        now = datetime.now(UTC)
        new_msg = Message(
            group_id=group.id,
            gmail_id=send_result["id"],
            message_id_header=new_message_id,
            in_reply_to=parent_msg.message_id_header,
            references_header=references,
            subject=reply_subject,
            sender_email=user.email,
            sender_name=user.display_name if hasattr(user, "display_name") else None,
            body_text=body.body_text,
            date=now,
        )
        session.add(new_msg)
        await session.flush()

        # 9. Create ThreadMessage linking to the thread
        # Determine position: max position + 1
        position = thread.message_count  # 0-indexed, so current count = next position
        thread_msg = ThreadMessage(
            thread_id=thread_id,
            message_id=new_msg.id,
            parent_message_id=parent_msg.id,
            position=position,
            depth=0,  # Simplified — flat depth for sent replies
        )
        session.add(thread_msg)

        # 10. Update thread counters
        thread.message_count = thread.message_count + 1
        thread.last_message_at = now

        # Update participant count by counting distinct senders
        participant_result = await session.execute(
            select(func.count(func.distinct(Message.sender_email)))
            .join(ThreadMessage, ThreadMessage.message_id == Message.id)
            .where(ThreadMessage.thread_id == thread_id)
        )
        thread.participant_count = participant_result.scalar_one()

        # 11. Record audit log
        audit_log = AuditLog(
            user_id=uuid.UUID(user_id),
            action="reply_send",
            resource_type="thread",
            resource_id=str(thread_id),
            audit_metadata={"parent_message_id": body.parent_message_id},
        )
        session.add(audit_log)

        await session.commit()

        # 12. Return 201 with new message data
        return JSONResponse(
            status_code=201,
            content={
                "message": {
                    "id": str(new_msg.id),
                    "sender_email": user.email,
                    "body_text": body.body_text,
                    "subject": reply_subject,
                    "message_id_header": new_message_id,
                    "gmail_id": send_result["id"],
                    "created_at": now.isoformat(),
                },
            },
        )

    return router
