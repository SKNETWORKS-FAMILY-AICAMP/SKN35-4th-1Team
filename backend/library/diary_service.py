"""Journal and public impressions share one source of truth.

A member may write any number of impressions a day but only one per artwork.
"""

from datetime import UTC

from django.db import IntegrityError

from catalog.catalog_service import ensure_artwork, to_artwork_card
from config.exceptions import HTTPException
from config.timeutil import month_range
from library import diary_repository as repo
from library.diary_schemas import DiaryCreate, DiaryEntry, DiaryFeed, DiaryWrite


def serialize(row) -> DiaryEntry:
    entry, nickname, artwork, artist_name, public_id = row
    return DiaryEntry(
        id=entry.id,
        author_id=public_id,
        entry_date=entry.entry_date,
        content=entry.content,
        is_public=entry.is_public,
        author_name=nickname or "감상가",
        artwork=to_artwork_card(artwork, artist_name) if artwork else None,
        created_at=entry.created_at.replace(tzinfo=UTC),
        updated_at=entry.updated_at.replace(tzinfo=UTC),
    )


DUPLICATE_ARTWORK = "이 작품에는 이미 감상평을 남겼어요. 남긴 감상평을 수정해 주세요."


def get_for_artwork(user_id: int, artwork_id: int) -> DiaryEntry | None:
    row = repo.for_artwork(user_id, artwork_id)
    return serialize(row) if row else None


def get_month(user_id: int, month: str) -> list[DiaryEntry]:
    start, end = month_range(month)
    return [serialize(row) for row in repo.month(user_id, start, end)]


def _check_artwork(
    user_id: int, artwork_id: int | None, entry_id: int | None = None
) -> None:
    if artwork_id is None:
        return
    ensure_artwork(artwork_id)
    taken = repo.for_artwork(user_id, artwork_id)
    if taken is not None and taken[0].id != entry_id:
        raise HTTPException(409, DUPLICATE_ARTWORK)


def _unique(write):
    try:
        return write()
    except IntegrityError:
        # Two requests for the same artwork raced past the check above.
        raise HTTPException(409, DUPLICATE_ARTWORK) from None


def create(user_id: int, body: DiaryCreate) -> DiaryEntry:
    _check_artwork(user_id, body.artwork_id)
    entry_id = _unique(
        lambda: repo.create(
            user_id=user_id,
            day=body.entry_date,
            **body.model_dump(exclude={"entry_date"}),
        )
    )
    return serialize(repo.own(user_id, entry_id))


def update(user_id: int, entry_id: int, body: DiaryWrite) -> DiaryEntry:
    if repo.own(user_id, entry_id) is None:
        raise HTTPException(404, "감상평을 찾을 수 없어요.")
    _check_artwork(user_id, body.artwork_id, entry_id)
    _unique(
        lambda: repo.update(user_id=user_id, entry_id=entry_id, **body.model_dump())
    )
    return serialize(repo.own(user_id, entry_id))


def get_feed(
    *,
    limit: int,
    before_id: int | None,
    artwork_id: int | None,
    author_id: int | None = None,
) -> DiaryFeed:
    rows = repo.feed(
        limit=limit,
        before_id=before_id,
        artwork_id=artwork_id,
        author_id=author_id,
    )
    return DiaryFeed(
        items=[serialize(row) for row in rows[:limit]],
        next_cursor=rows[limit - 1][0].id if len(rows) > limit else None,
    )
