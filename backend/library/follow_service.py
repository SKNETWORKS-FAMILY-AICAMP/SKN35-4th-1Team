"""Artist follows. Follow and unfollow are idempotent."""

from catalog import catalog_service
from catalog.schemas import ArtistCard
from library import activity_repository


def follow(*, user_id: int, artist_id: int) -> None:
    catalog_service.ensure_artist(artist_id)
    activity_repository.add_follow(user_id=user_id, artist_id=artist_id)


def unfollow(*, user_id: int, artist_id: int) -> None:
    """No existence check: removing a follow that is not there is still a success."""

    activity_repository.remove_follow(user_id=user_id, artist_id=artist_id)


def list_followed(*, user_id: int) -> list[ArtistCard]:
    artists = activity_repository.list_followed_artists(user_id=user_id)
    return [ArtistCard.model_validate(a) for a in artists]
