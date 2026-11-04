"""Reads for movements, artists and artworks.

Artwork queries return ``(Artwork, artist_name)`` rows so cards can show the
artist without a second request.
"""

from catalog.models import Artist, ArtMovement, Artwork

ArtworkRow = tuple[Artwork, str]


def list_movements() -> list[ArtMovement]:
    return list(ArtMovement.objects.order_by("id"))


def list_artists(*, movement_id: int | None = None) -> list[Artist]:
    artists = Artist.objects.order_by("birth_year", "id")
    if movement_id is not None:
        artists = artists.filter(movement_id=movement_id)
    return list(artists)


def get_artist(artist_id: int) -> Artist | None:
    return Artist.objects.filter(id=artist_id).first()


def with_artist():
    return Artwork.objects.select_related("artist")


def to_row(artwork: Artwork) -> ArtworkRow:
    return artwork, artwork.artist.name


def list_artworks(
    *, artist_id: int | None = None, movement_id: int | None = None
) -> list[ArtworkRow]:
    artworks = with_artist().order_by("artist_id", "year_start", "id")
    if artist_id is not None:
        artworks = artworks.filter(artist_id=artist_id)
    if movement_id is not None:
        artworks = artworks.filter(movement_id=movement_id)
    return [to_row(artwork) for artwork in artworks]


def get_artwork(artwork_id: int) -> ArtworkRow | None:
    artwork = with_artist().filter(id=artwork_id).first()
    return to_row(artwork) if artwork else None


def get_artworks(artwork_ids: list[int]) -> dict[int, ArtworkRow]:
    if not artwork_ids:
        return {}
    return {a.id: to_row(a) for a in with_artist().filter(id__in=artwork_ids)}


def get_artists(artist_ids: list[int]) -> dict[int, Artist]:
    if not artist_ids:
        return {}
    return {a.id: a for a in Artist.objects.filter(id__in=artist_ids)}


def artwork_exists(artwork_id: int) -> bool:
    return Artwork.objects.filter(id=artwork_id).exists()


def artist_exists(artist_id: int) -> bool:
    return Artist.objects.filter(id=artist_id).exists()
