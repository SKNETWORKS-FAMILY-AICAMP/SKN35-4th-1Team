"""Saved docent conversations for logged-in users.

Answering is the RAG side's job. Once ``POST /artworks/{id}/chat`` produces a
``ChatResponse``, the route stores it for a logged-in user with::

    if user is not None:
        chat_service.save_exchange(
            user_id=user.id, artwork_id=artwork_id,
            question=body.question, response=response,
        )

Timestamps are stored as naive UTC and returned with an explicit UTC offset.
"""

from datetime import UTC, datetime

from django.db import transaction

from catalog import catalog_service
from chat import chat_repository
from chat.models import ChatRole
from chat.schemas import ChatMessageOut, ChatResponse, ChatSummary
from config import timeutil


def save_exchange(
    *,
    user_id: int,
    artwork_id: int,
    question: str,
    response: ChatResponse,
    now: datetime | None = None,
) -> None:
    """Store one question and its answer in the user's session for this artwork."""

    now = now or timeutil.utcnow()
    with transaction.atomic():
        session_id = chat_repository.get_or_create_session_id(
            user_id=user_id, artwork_id=artwork_id, now=now
        )
        chat_repository.add_message(
            session_id=session_id,
            role=ChatRole.USER,
            content=question,
            refused=False,
            sources=None,
            now=now,
        )
        chat_repository.add_message(
            session_id=session_id,
            role=ChatRole.ASSISTANT,
            content=response.answer,
            refused=response.refused,
            sources=[s.model_dump(mode="json") for s in response.sources],
            now=now,
        )
        chat_repository.touch_session(session_id=session_id, now=now)


def list_messages(
    *, user_id: int, artwork_id: int
) -> list[ChatMessageOut]:
    """Empty when the user never asked about this artwork."""

    session_id = chat_repository.get_session_id(
        user_id=user_id, artwork_id=artwork_id
    )
    if session_id is None:
        return []
    return [
        ChatMessageOut(
            id=m.id,
            role=ChatRole(m.role).value,
            content=m.content,
            refused=m.refused,
            sources=m.sources or [],
            created_at=m.created_at.replace(tzinfo=UTC),
        )
        for m in chat_repository.list_messages(session_id=session_id)
    ]


def reset(*, user_id: int, artwork_id: int) -> None:
    """Idempotent: resetting a conversation that does not exist is a success."""

    session_id = chat_repository.get_session_id(
        user_id=user_id, artwork_id=artwork_id
    )
    if session_id is not None:
        with transaction.atomic():
            chat_repository.delete_session(session_id=session_id)


def list_chats(*, user_id: int) -> list[ChatSummary]:
    return [
        ChatSummary(
            artwork=catalog_service.to_artwork_card(row.artwork, row.artist_name),
            last_message=row.last_message,
            updated_at=row.updated_at.replace(tzinfo=UTC),
        )
        for row in chat_repository.list_summaries(user_id=user_id)
    ]
