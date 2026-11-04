"""좋아요, 팔로우, 서재, 일기, 컬렉션, 추천.

날짜는 서버에서 `APP_TIMEZONE`(Asia/Seoul) 기준으로 계산한다.
"""

from datetime import date

from django.http import HttpResponse
from ninja import Path, Query, Router

from accounts.auth import current_user
from catalog import recommendation_service
from catalog.recommendation_schemas import RecommendedArtist, RecommendedArtwork
from catalog.schemas import ArtistCard, ArtworkCard
from config.exceptions import HTTPException
from library import (
    auto_collections,
    collection_assistant,
    diary_repository,
    diary_service,
    follow_service,
    library_service,
    like_service,
    theme_collections,
)
from library import mypage_service as service
from library.diary_schemas import DiaryCreate, DiaryEntry, DiaryFeed, DiaryWrite
from library.mypage_schemas import (
    ActivityOut,
    ArtworkPage,
    AutoCollectionDetail,
    AutoCollectionOut,
    CollectionChatReply,
    CollectionChatRequest,
    CollectionCreate,
    CollectionOut,
    CollectionWrite,
    CritiquePage,
    TasteOut,
    ThemeCollectionsOut,
)
from library.schemas import CalendarDay, ViewedArtwork

router = Router(tags=["library"])

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def private(response):
    response.headers["Cache-Control"] = "private, no-store"


# 좋아요
@router.put("/artworks/{artwork_id}/like", auth=current_user, response={204: None})
def like_artwork(request, artwork_id: int):
    """좋아요. 여러 번 호출해도 결과가 같다. 없는 작품이면 404."""
    like_service.like(user_id=request.auth.id, artwork_id=artwork_id)
    return 204, None


@router.delete("/artworks/{artwork_id}/like", auth=current_user, response={204: None})
def unlike_artwork(request, artwork_id: int):
    """좋아요 취소. 좋아요가 없어도 204."""
    like_service.unlike(user_id=request.auth.id, artwork_id=artwork_id)
    return 204, None


@router.get("/me/likes", auth=current_user, response=list[ArtworkCard])
def list_my_likes(request):
    """내가 좋아요한 작품 (최근순)."""
    return like_service.list_liked(user_id=request.auth.id)


# 작가 팔로우
@router.put("/artists/{artist_id}/follow", auth=current_user, response={204: None})
def follow_artist(request, artist_id: int):
    """팔로우. 여러 번 호출해도 결과가 같다. 없는 작가면 404."""
    follow_service.follow(user_id=request.auth.id, artist_id=artist_id)
    return 204, None


@router.delete("/artists/{artist_id}/follow", auth=current_user, response={204: None})
def unfollow_artist(request, artist_id: int):
    """팔로우 취소. 팔로우가 없어도 204."""
    follow_service.unfollow(user_id=request.auth.id, artist_id=artist_id)
    return 204, None


@router.get("/me/follows", auth=current_user, response=list[ArtistCard])
def list_my_follows(request):
    """내가 팔로우한 작가 (최근순)."""
    return follow_service.list_followed(user_id=request.auth.id)


# 열람 기록과 서재 캘린더
@router.post("/artworks/{artwork_id}/views", auth=current_user, response={204: None})
def record_view(request, artwork_id: int):
    """작품 열람 기록. 같은 날 다시 보면 `view_count`만 증가. 없는 작품이면 404."""
    library_service.record_view(user_id=request.auth.id, artwork_id=artwork_id)
    return 204, None


@router.get("/me/library/calendar", auth=current_user, response=list[CalendarDay])
def get_calendar(request, month: str = Query(..., pattern=MONTH_PATTERN)):
    """월별 감상 기록. 본 날만 날짜순으로 담는다."""
    return library_service.calendar(user_id=request.auth.id, month=month)


@router.get("/me/library/days/{day}", auth=current_user, response=list[ViewedArtwork])
def get_day(request, day: date):
    """그날 본 작품 목록 (마지막으로 본 순)."""
    return library_service.viewed_on_day(user_id=request.auth.id, day=day)


# 일기
@router.get("/diary/feed", response=DiaryFeed)
def feed(
    request,
    response: HttpResponse,
    limit: int = Query(12, ge=1, le=30),
    before_id: int | None = Query(None, gt=0),
    artwork_id: int | None = Query(None, gt=0),
):
    response.headers["Cache-Control"] = "no-store"
    return diary_service.get_feed(
        limit=limit, before_id=before_id, artwork_id=artwork_id
    )


@router.get("/me/diary", auth=current_user, response=list[DiaryEntry])
def diary_month(request, response: HttpResponse, month: str = Query(..., pattern=MONTH_PATTERN)):
    private(response)
    try:
        return diary_service.get_month(request.auth.id, month)
    except ValueError:
        raise HTTPException(422, "올바른 연월을 입력해 주세요.") from None


@router.get("/me/diary/artworks/{artwork_id}", auth=current_user, response=DiaryEntry | None)
def diary_artwork_entry(request, response: HttpResponse, artwork_id: int = Path(..., gt=0)):
    """이 작품에 남긴 내 감상. 작품당 하나."""
    private(response)
    return diary_service.get_for_artwork(request.auth.id, artwork_id)


@router.post("/me/diary", auth=current_user, response={201: DiaryEntry})
def diary_create(request, response: HttpResponse, body: DiaryCreate):
    private(response)
    return 201, diary_service.create(request.auth.id, body)


@router.put("/me/diary/{entry_id}", auth=current_user, response=DiaryEntry)
def diary_update(request, response: HttpResponse, body: DiaryWrite, entry_id: int = Path(..., gt=0)):
    private(response)
    return diary_service.update(request.auth.id, entry_id, body)


@router.delete("/me/diary/{entry_id}", auth=current_user, response={204: None})
def diary_remove(request, entry_id: int = Path(..., gt=0)):
    diary_repository.remove(request.auth.id, entry_id)
    return 204, None


# 컬렉션. Django는 먼저 맞은 경로에서 끝나므로 고정 경로를 {collection_id}보다 앞에 둔다.
@router.get("/me/collections", auth=current_user, response=list[CollectionOut])
def collections(request, response: HttpResponse):
    private(response)
    return service.collections(request.auth.id)


@router.post("/me/collections", auth=current_user, response={201: CollectionOut})
def collection_create(request, response: HttpResponse, body: CollectionCreate):
    private(response)
    return 201, service.save_collection(request.auth.id, body)


@router.get("/me/collections/auto", auth=current_user, response=list[AutoCollectionOut])
def auto_list(request, response: HttpResponse):
    """열람 기록으로 계산한 자동 컬렉션."""
    private(response)
    return auto_collections.collections(request.auth.id)


@router.get("/me/collections/auto/{key}", auth=current_user, response=AutoCollectionDetail)
def auto_detail(request, response: HttpResponse, key: str):
    private(response)
    if key.startswith("theme-"):
        return theme_collections.detail(request.auth.id, key)
    summary, works = auto_collections.collection(request.auth.id, key)
    return AutoCollectionDetail(collection=summary, items=works)


@router.post("/me/collections/themes/refresh", auth=current_user, response=ThemeCollectionsOut)
def refresh_themes(request, response: HttpResponse):
    """개인 AI 컬렉션을 준비한다. 반복 호출은 캐시된 결과를 돌려준다."""
    private(response)
    return theme_collections.refresh(request.auth.id)


@router.post("/me/collections/chat", auth=current_user, response=CollectionChatReply)
def collection_chat(request, response: HttpResponse, body: CollectionChatRequest):
    private(response)
    return collection_assistant.propose(request.auth.id, body)


@router.put("/me/collections/{collection_id}", auth=current_user, response=CollectionOut)
def collection_update(request, response: HttpResponse, collection_id: int, body: CollectionWrite):
    private(response)
    return service.save_collection(request.auth.id, body, collection_id)


@router.delete("/me/collections/{collection_id}", auth=current_user, response={204: None})
def collection_remove(request, collection_id: int):
    service.delete_collection(request.auth.id, collection_id)
    return 204, None


@router.get("/me/collections/{collection_id}/items", auth=current_user, response=ArtworkPage)
def collection_artworks(
    request,
    response: HttpResponse,
    collection_id: int,
    limit: int = Query(12, ge=1, le=30),
    before_id: int | None = Query(None, gt=0),
):
    private(response)
    return service.collection_page(request.auth.id, collection_id, limit, before_id)


@router.put("/me/collections/{collection_id}/items/{artwork_id}", auth=current_user, response=CollectionOut)
def collection_add(request, response: HttpResponse, collection_id: int, artwork_id: int):
    private(response)
    return service.add_artwork(request.auth.id, collection_id, artwork_id)


@router.delete("/me/collections/{collection_id}/items/{artwork_id}", auth=current_user, response={204: None})
def collection_remove_artwork(request, collection_id: int, artwork_id: int):
    service.remove_artwork(request.auth.id, collection_id, artwork_id)
    return 204, None


# 마이페이지 활동과 취향
@router.get("/me/critiques", auth=current_user, response=CritiquePage)
def critiques(
    request,
    response: HttpResponse,
    limit: int = Query(12, ge=1, le=30),
    before_id: int | None = Query(None, gt=0),
):
    private(response)
    return service.critiques(request.auth.id, limit, before_id)


@router.get("/me/activity", auth=current_user, response=list[ActivityOut])
def activity(
    request,
    response: HttpResponse,
    limit: int = Query(20, ge=1, le=30),
    offset: int = Query(0, ge=0, le=10000),
):
    private(response)
    return service.activity(request.auth.id, limit, offset)


@router.get("/me/taste", auth=current_user, response=TasteOut)
def taste(request, response: HttpResponse):
    private(response)
    return service.get_taste(request.auth.id)


@router.post("/me/taste", auth=current_user, response=TasteOut)
def generate_taste(request, response: HttpResponse):
    private(response)
    return collection_assistant.make_taste(request.auth.id)


# 맞춤 추천
@router.get("/me/recommendations/artworks", auth=current_user, response=list[RecommendedArtwork])
def recommend_artworks(request):
    """좋아요 기반 맞춤 작품 3개 (작가당 1개). 좋아요가 없으면 대체 추천."""
    return recommendation_service.recommend_artworks(user_id=request.auth.id)


@router.get("/me/recommendations/artists", auth=current_user, response=list[RecommendedArtist])
def recommend_artists(request):
    """추천 작가 3명. 팔로우한 작가는 제외."""
    return recommendation_service.recommend_artists(user_id=request.auth.id)
