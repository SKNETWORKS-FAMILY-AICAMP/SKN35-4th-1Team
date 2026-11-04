"""사조, 작가, 작품과 비슷한 작품. 모두 공개."""

from ninja import Router

from catalog import catalog_service, recommendation_service
from catalog.schemas import (
    ArtistCard,
    ArtistDetail,
    ArtworkCard,
    ArtworkDetail,
    Movement,
)

router = Router(tags=["catalog"])


@router.get("/movements", response=list[Movement])
def list_movements(request):
    """사조 목록."""
    return catalog_service.list_movements()


@router.get("/artists", response=list[ArtistCard])
def list_artists(request, movement_id: int | None = None):
    """작가 목록. `movement_id`로 사조별 필터."""
    return catalog_service.list_artists(movement_id=movement_id)


@router.get("/artists/{artist_id}", response=ArtistDetail)
def get_artist(request, artist_id: int):
    """작가 상세. 없으면 404."""
    return catalog_service.get_artist(artist_id)


@router.get("/artworks", response=list[ArtworkCard])
def list_artworks(request, artist_id: int | None = None, movement_id: int | None = None):
    """작품 목록. `artist_id`, `movement_id`로 필터."""
    return catalog_service.list_artworks(
        artist_id=artist_id, movement_id=movement_id
    )


@router.get("/artworks/{artwork_id}", response=ArtworkDetail)
def get_artwork(request, artwork_id: int):
    """작품 상세. 없으면 404."""
    return catalog_service.get_artwork(artwork_id)


@router.get("/artworks/{artwork_id}/similar", response=list[ArtworkCard])
def similar_artworks(request, artwork_id: int):
    """이 작품과 비슷한 작품 3개 (가까운 순). 작품 벡터가 없으면 빈 배열."""
    return recommendation_service.similar(artwork_id=artwork_id)
