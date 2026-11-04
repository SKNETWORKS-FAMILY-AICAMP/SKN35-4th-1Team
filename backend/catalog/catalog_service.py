"""Movement, artist and artwork lists and details."""

from typing import Any

from catalog import catalog_repository
from catalog.schemas import (
    ArtistCard,
    ArtistDetail,
    ArtworkCard,
    ArtworkDetail,
    Movement,
)
from config.exceptions import NotFoundError


def to_artwork_card[CardT: ArtworkCard](
    artwork: Any, artist_name: str, model: type[CardT] = ArtworkCard, **extra: Any
) -> CardT:
    """Build an artwork card (or a subclass) from a row; ``extra`` fills subclass fields."""

    columns = {n: getattr(artwork, n) for n in model.model_fields if hasattr(artwork, n)}
    return model.model_validate({**columns, "artist_name": artist_name, **extra})


def list_movements() -> list[Movement]:
    return [Movement.model_validate(m) for m in catalog_repository.list_movements()]


def list_artists(*, movement_id: int | None = None) -> list[ArtistCard]:
    artists = catalog_repository.list_artists(movement_id=movement_id)
    return [ArtistCard.model_validate(a) for a in artists]


def get_artist(artist_id: int) -> ArtistDetail:
    artist = catalog_repository.get_artist(artist_id)
    if artist is None:
        raise NotFoundError("작가를 찾을 수 없습니다.")
    return ArtistDetail.model_validate(artist)


def list_artworks(
    *, artist_id: int | None = None, movement_id: int | None = None
) -> list[ArtworkCard]:
    rows = catalog_repository.list_artworks(
        artist_id=artist_id, movement_id=movement_id
    )
    return [to_artwork_card(artwork, name) for artwork, name in rows]


def get_artwork(artwork_id: int) -> ArtworkDetail:
    row = catalog_repository.get_artwork(artwork_id)
    if row is None:
        raise NotFoundError("작품을 찾을 수 없습니다.")
    artwork, name = row
    return to_artwork_card(artwork, name, ArtworkDetail)


def ensure_artwork(artwork_id: int) -> None:
    if not catalog_repository.artwork_exists(artwork_id):
        raise NotFoundError("작품을 찾을 수 없습니다.")


def ensure_artist(artist_id: int) -> None:
    if not catalog_repository.artist_exists(artist_id):
        raise NotFoundError("작가를 찾을 수 없습니다.")
