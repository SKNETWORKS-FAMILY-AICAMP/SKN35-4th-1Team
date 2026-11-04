"""Artwork likes. Like and unlike are idempotent."""

from catalog import catalog_service
from catalog.schemas import ArtworkCard
from library import activity_repository


def like(*, user_id: int, artwork_id: int) -> None:
    catalog_service.ensure_artwork(artwork_id)
    activity_repository.add_like(user_id=user_id, artwork_id=artwork_id)


def unlike(*, user_id: int, artwork_id: int) -> None:
    """No existence check: removing a like that is not there is still a success."""

    activity_repository.remove_like(user_id=user_id, artwork_id=artwork_id)


def list_liked(*, user_id: int) -> list[ArtworkCard]:
    rows = activity_repository.list_liked_artworks(user_id=user_id)
    return [catalog_service.to_artwork_card(artwork, name) for artwork, name in rows]
