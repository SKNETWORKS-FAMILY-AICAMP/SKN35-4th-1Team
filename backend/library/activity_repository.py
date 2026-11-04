"""Likes, follows and daily views.

Writes are idempotent at the SQL level: likes and follows use ``INSERT IGNORE``,
views use ``ON DUPLICATE KEY UPDATE``.
"""

from datetime import date, datetime
from typing import NamedTuple

from django.db import connection
from django.db.models import Count, Sum

from catalog.models import Artist, Artwork
from library.models import ArtistFollow, ArtworkLike, ArtworkView


class CalendarRow(NamedTuple):
    viewed_on: date
    artwork_count: int
    total_views: int


class ViewedRow(NamedTuple):
    artwork: Artwork
    artist_name: str
    view_count: int
    last_viewed_at: datetime


# --- likes ------------------------------------------------------------------


def add_like(*, user_id: int, artwork_id: int) -> None:
    ArtworkLike.objects.bulk_create(
        [ArtworkLike(user_id=user_id, artwork_id=artwork_id)], ignore_conflicts=True
    )


def remove_like(*, user_id: int, artwork_id: int) -> None:
    ArtworkLike.objects.filter(user_id=user_id, artwork_id=artwork_id).delete()


def list_liked_artworks(*, user_id: int) -> list[tuple[Artwork, str]]:
    likes = (
        ArtworkLike.objects.filter(user_id=user_id)
        .select_related("artwork__artist")
        .order_by("-created_at", "-artwork_id")
    )
    return [(like.artwork, like.artwork.artist.name) for like in likes]


# --- follows ----------------------------------------------------------------


def add_follow(*, user_id: int, artist_id: int) -> None:
    ArtistFollow.objects.bulk_create(
        [ArtistFollow(user_id=user_id, artist_id=artist_id)], ignore_conflicts=True
    )


def remove_follow(*, user_id: int, artist_id: int) -> None:
    ArtistFollow.objects.filter(user_id=user_id, artist_id=artist_id).delete()


def list_followed_artists(*, user_id: int) -> list[Artist]:
    follows = (
        ArtistFollow.objects.filter(user_id=user_id)
        .select_related("artist")
        .order_by("-created_at", "-artist_id")
    )
    return [follow.artist for follow in follows]


# --- views ------------------------------------------------------------------


def record_view(
    *, user_id: int, artwork_id: int, viewed_on: date, now: datetime
) -> None:
    """One row per user, day and artwork; a repeat view bumps ``view_count``.

    Raw SQL keeps the increment atomic; the ORM has no ``ON DUPLICATE KEY UPDATE``
    with an expression.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO artwork_views "
            "(user_id, artwork_id, viewed_on, view_count, first_viewed_at, last_viewed_at) "
            "VALUES (%s, %s, %s, 1, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "view_count = view_count + 1, last_viewed_at = VALUES(last_viewed_at)",
            [user_id, artwork_id, viewed_on, now, now],
        )


def _views(user_id: int):
    return ArtworkView.objects.filter(user_id=user_id)


def calendar(*, user_id: int, start: date, end: date) -> list[CalendarRow]:
    """Days in ``[start, end)`` with at least one view, oldest first."""

    rows = (
        _views(user_id)
        .filter(viewed_on__gte=start, viewed_on__lt=end)
        .values("viewed_on")
        .annotate(artwork_count=Count("*"), total_views=Sum("view_count"))
        .order_by("viewed_on")
    )
    return [
        CalendarRow(r["viewed_on"], int(r["artwork_count"]), int(r["total_views"]))
        for r in rows
    ]


def viewed_on_day(*, user_id: int, day: date) -> list[ViewedRow]:
    """Artworks viewed on ``day``, most recently viewed first."""

    views = (
        _views(user_id)
        .filter(viewed_on=day)
        .select_related("artwork__artist")
        .order_by("-last_viewed_at", "-artwork_id")
    )
    return [
        ViewedRow(v.artwork, v.artwork.artist.name, v.view_count, v.last_viewed_at)
        for v in views
    ]


def latest_view_by_day(
    *, user_id: int, start: date, end: date
) -> dict[date, tuple[Artwork, str]]:
    """The most recently viewed artwork for each day in ``[start, end)``."""

    views = (
        _views(user_id)
        .filter(viewed_on__gte=start, viewed_on__lt=end)
        .select_related("artwork__artist")
        .order_by("-last_viewed_at", "-artwork_id")
    )
    latest: dict[date, tuple[Artwork, str]] = {}
    for view in views:
        latest.setdefault(view.viewed_on, (view.artwork, view.artwork.artist.name))
    return latest
