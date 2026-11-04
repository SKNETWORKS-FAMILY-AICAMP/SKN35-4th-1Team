"""Owner-scoped diary reads and bounded, public-only cursor pagination."""

from datetime import date

from django.utils import timezone

from library.models import DiaryEntry


def entries():
    return DiaryEntry.objects.select_related("user", "artwork__artist")


def to_row(entry: DiaryEntry):
    """``(entry, nickname, artwork, artist_name, public_id)``"""

    artwork = entry.artwork
    artist_name = artwork.artist.name if artwork else None
    return entry, entry.user.nickname, artwork, artist_name, entry.user.public_id


def own(user_id: int, entry_id: int):
    entry = entries().filter(user_id=user_id, id=entry_id).first()
    return to_row(entry) if entry else None


def for_artwork(user_id: int, artwork_id: int):
    entry = entries().filter(user_id=user_id, artwork_id=artwork_id).first()
    return to_row(entry) if entry else None


def month(user_id: int, start: date, end: date):
    rows = (
        entries()
        .filter(user_id=user_id, entry_date__gte=start, entry_date__lt=end)
        .order_by("-entry_date", "-id")
    )
    return [to_row(entry) for entry in rows]


def feed(
    *,
    limit: int,
    before_id: int | None,
    artwork_id: int | None,
    author_id: int | None = None,
):
    rows = entries().filter(is_public=True)
    if author_id is not None:
        rows = rows.filter(user_id=author_id)
    if before_id is not None:
        rows = rows.filter(id__lt=before_id)
    if artwork_id is not None:
        rows = rows.filter(artwork_id=artwork_id)
    return [to_row(entry) for entry in rows.order_by("-id")[: limit + 1]]


def create(
    *,
    user_id: int,
    day: date,
    content: str,
    is_public: bool,
    artwork_id: int | None,
) -> int:
    entry = DiaryEntry.objects.create(
        user_id=user_id,
        entry_date=day,
        content=content,
        is_public=is_public,
        artwork_id=artwork_id,
    )
    return entry.id


def update(
    *,
    user_id: int,
    entry_id: int,
    content: str,
    is_public: bool,
    artwork_id: int | None,
) -> int:
    """Returns the number of the owner's rows changed (0 when not found)."""
    return DiaryEntry.objects.filter(user_id=user_id, id=entry_id).update(
        content=content,
        is_public=is_public,
        artwork_id=artwork_id,
        updated_at=timezone.now(),
    )


def remove(user_id: int, entry_id: int):
    DiaryEntry.objects.filter(user_id=user_id, id=entry_id).delete()
