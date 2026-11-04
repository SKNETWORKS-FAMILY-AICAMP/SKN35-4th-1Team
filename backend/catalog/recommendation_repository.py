"""Candidates for recommendations. Queries D–G in ``docs/db/02_queries.sql``.

Vector SQL (``VEC_COSINE_DISTANCE``) is TiDB-only and lives only here. Results
carry ids and distances, never the embedding column. Picking (one per artist,
fallbacks) is the service's job.

Recommendations only return artworks that have an image, so cards never show
an empty frame.
"""

from typing import NamedTuple

from django.db import connection
from django.db.models import Max

from catalog import catalog_repository
from catalog.models import Artwork, ArtworkEmbedding
from library.models import ArtistFollow, ArtworkLike, ArtworkView

ArtworkRow = tuple[Artwork, str]

_HAS_IMAGE = "a.image_url IS NOT NULL AND a.image_url <> ''"


def _with_image():
    return (
        catalog_repository.with_artist()
        .exclude(image_url__isnull=True)
        .exclude(image_url="")
    )


class Candidate(NamedTuple):
    artwork_id: int
    artist_id: int
    # The seed this candidate is closest to; recommendation reasons name it.
    seed_id: int
    distance: float


def has_embedding(artwork_id: int) -> bool:
    return ArtworkEmbedding.objects.filter(artwork_id=artwork_id).exists()


_SIMILAR = f"""
    SELECT knn.artwork_id, knn.distance
    FROM (
        SELECT e.artwork_id,
               VEC_COSINE_DISTANCE(
                   e.embedding,
                   (SELECT s.embedding FROM artwork_embeddings AS s
                    WHERE s.artwork_id = %(artwork_id)s)
               ) AS distance
        FROM artwork_embeddings AS e
        ORDER BY distance
        LIMIT %(knn)s
    ) AS knn
    JOIN artworks AS a ON a.id = knn.artwork_id
    WHERE knn.artwork_id <> %(artwork_id)s
      AND {_HAS_IMAGE}
    ORDER BY knn.distance, knn.artwork_id
    LIMIT %(limit)s
    """


def similar_artwork_ids(*, artwork_id: int, limit: int) -> list[int]:
    """Nearest artworks to one artwork, closest first. Empty if it has no vector."""

    if not has_embedding(artwork_id):
        return []
    # The pure KNN inner query also returns the artwork itself and may hit
    # imageless artworks; take a few extra.
    with connection.cursor() as cursor:
        cursor.execute(
            _SIMILAR, {"artwork_id": artwork_id, "knn": limit + 4, "limit": limit}
        )
        return [row[0] for row in cursor.fetchall()]


_CANDIDATES = f"""
    SELECT artwork_id, artist_id, seed_id, distance
    FROM (
        SELECT cand.artwork_id,
               a.artist_id,
               seed.artwork_id AS seed_id,
               VEC_COSINE_DISTANCE(cand.embedding, seed.embedding) AS distance,
               ROW_NUMBER() OVER (
                   PARTITION BY cand.artwork_id
                   ORDER BY VEC_COSINE_DISTANCE(cand.embedding, seed.embedding),
                            seed.artwork_id
               ) AS nearest
        FROM artwork_embeddings AS seed
        JOIN artwork_embeddings AS cand ON cand.artwork_id <> seed.artwork_id
        JOIN artworks AS a ON a.id = cand.artwork_id
        WHERE seed.artwork_id IN ({{seeds}})
          AND cand.artwork_id NOT IN ({{excluded}})
          AND {_HAS_IMAGE}
    ) AS ranked
    WHERE nearest = 1
    ORDER BY distance, artwork_id
    LIMIT %s
    """


def candidates(
    *, seed_ids: list[int], exclude_ids: set[int], limit: int = 30
) -> list[Candidate]:
    """Artworks closest to any seed (min distance over seeds), closest first.

    Seeds themselves are always excluded.
    """

    if not seed_ids:
        return []
    exclude = sorted(set(exclude_ids) | set(seed_ids))
    sql = _CANDIDATES.format(
        seeds=", ".join(["%s"] * len(seed_ids)),
        excluded=", ".join(["%s"] * len(exclude)),
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [*seed_ids, *exclude, limit])
        rows = cursor.fetchall()
    return [Candidate(int(a), int(r), int(s), float(d)) for a, r, s, d in rows]


# --- seeds and fallbacks ----------------------------------------------------


def liked_artwork_ids(*, user_id: int) -> list[int]:
    """Most recent first."""

    return list(
        ArtworkLike.objects.filter(user_id=user_id)
        .order_by("-created_at", "-artwork_id")
        .values_list("artwork_id", flat=True)
    )


def recent_viewed_artwork_ids(*, user_id: int, limit: int) -> list[int]:
    return list(
        ArtworkView.objects.filter(user_id=user_id)
        .values("artwork_id")
        .annotate(last_viewed=Max("last_viewed_at"))
        .order_by("-last_viewed", "-artwork_id")
        .values_list("artwork_id", flat=True)[:limit]
    )


def followed_artist_ids(*, user_id: int) -> list[int]:
    """Most recent first."""

    return list(
        ArtistFollow.objects.filter(user_id=user_id)
        .order_by("-created_at", "-artist_id")
        .values_list("artist_id", flat=True)
    )


def artworks_by_artists(*, artist_ids: list[int]) -> list[ArtworkRow]:
    """Curated first, then by year."""

    if not artist_ids:
        return []
    artworks = (
        _with_image()
        .filter(artist_id__in=artist_ids)
        .order_by("-is_featured", "year_start", "id")
    )
    return [catalog_repository.to_row(a) for a in artworks]


def fallback_artworks() -> list[ArtworkRow]:
    """Every artwork with an image, by id. The service shuffles them (curated first)."""

    return [catalog_repository.to_row(a) for a in _with_image().order_by("id")]
