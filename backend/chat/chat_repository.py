"""Saved docent conversations: one session per user and artwork."""

from datetime import UTC, datetime
from typing import Any, NamedTuple

from django.db.models import OuterRef, Subquery

from catalog.models import Artwork
from chat.models import ChatMessage, ChatRole, ChatSession


class ChatSummaryRow(NamedTuple):
    artwork: Artwork
    artist_name: str
    last_message: str
    updated_at: datetime


def get_session_id(*, user_id: int, artwork_id: int) -> int | None:
    return (
        ChatSession.objects.filter(user_id=user_id, artwork_id=artwork_id)
        .values_list("id", flat=True)
        .first()
    )


def get_or_create_session_id(
    *, user_id: int, artwork_id: int, now: datetime
) -> int:
    """``INSERT IGNORE`` so two first questions at once still share one session."""

    ChatSession.objects.bulk_create(
        [ChatSession(user_id=user_id, artwork_id=artwork_id)], ignore_conflicts=True
    )
    session_id = get_session_id(user_id=user_id, artwork_id=artwork_id)
    assert session_id is not None
    return session_id


def add_message(
    *,
    session_id: int,
    role: ChatRole,
    content: str,
    refused: bool,
    sources: list[dict[str, Any]] | None,
    now: datetime,
) -> None:
    ChatMessage.objects.create(
        session_id=session_id,
        role=role.value,
        content=content,
        refused=refused,
        sources=sources,
    )


def touch_session(*, session_id: int, now: datetime) -> None:
    # ``now`` is naive UTC; Django would read a naive value as Asia/Seoul.
    ChatSession.objects.filter(id=session_id).update(updated_at=now.replace(tzinfo=UTC))


def list_messages(*, session_id: int) -> list[ChatMessage]:
    """Oldest first; ids grow with insertion order."""

    return list(ChatMessage.objects.filter(session_id=session_id).order_by("id"))


def delete_session(*, session_id: int) -> None:
    # Messages first instead of relying on the FK cascade.
    ChatMessage.objects.filter(session_id=session_id).delete()
    ChatSession.objects.filter(id=session_id).delete()


def list_summaries(*, user_id: int) -> list[ChatSummaryRow]:
    """Sessions that have messages, most recently updated first."""

    latest = ChatMessage.objects.filter(session_id=OuterRef("id")).order_by("-id")
    sessions = (
        ChatSession.objects.filter(user_id=user_id)
        .annotate(last_message=Subquery(latest.values("content")[:1]))
        .filter(last_message__isnull=False)
        .select_related("artwork__artist")
        .order_by("-updated_at", "-id")
    )
    return [
        ChatSummaryRow(s.artwork, s.artwork.artist.name, s.last_message, s.updated_at)
        for s in sessions
    ]
