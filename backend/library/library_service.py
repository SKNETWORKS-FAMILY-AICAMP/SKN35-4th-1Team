"""View records and the "my library" calendar.

Days are app-time-zone (Asia/Seoul) dates; timestamps are stored as naive UTC
and returned with an explicit UTC offset.
"""

from datetime import UTC, date, datetime

from catalog import catalog_service
from config import timeutil
from library import activity_repository
from library.schemas import CalendarDay, ViewedArtwork


def record_view(
    *, user_id: int, artwork_id: int, now: datetime | None = None
) -> None:
    """``now`` is naive UTC; tests pass it to pin the day boundary."""

    catalog_service.ensure_artwork(artwork_id)
    now = now or timeutil.utcnow()
    activity_repository.record_view(
        user_id=user_id,
        artwork_id=artwork_id,
        viewed_on=timeutil.local_date(now),
        now=now,
    )


def calendar(*, user_id: int, month: str) -> list[CalendarDay]:
    start, end = timeutil.month_range(month)
    rows = activity_repository.calendar(user_id=user_id, start=start, end=end)
    latest = activity_repository.latest_view_by_day(
        user_id=user_id, start=start, end=end
    )
    return [
        CalendarDay(
            date=r.viewed_on,
            artwork_count=r.artwork_count,
            total_views=r.total_views,
            artwork=catalog_service.to_artwork_card(*latest[r.viewed_on])
            if r.viewed_on in latest
            else None,
        )
        for r in rows
    ]


def viewed_on_day(*, user_id: int, day: date) -> list[ViewedArtwork]:
    rows = activity_repository.viewed_on_day(user_id=user_id, day=day)
    return [
        catalog_service.to_artwork_card(
            r.artwork,
            r.artist_name,
            ViewedArtwork,
            view_count=r.view_count,
            last_viewed_at=r.last_viewed_at.replace(tzinfo=UTC),
        )
        for r in rows
    ]
