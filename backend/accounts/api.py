"""내 프로필, 공개 회원 프로필, 회원 팔로우.

경로는 ``public_id``를 쓰고, 팔로우하는 사람은 항상 검증된 토큰에서 가져온다.
"""

from django.http import HttpResponse
from ninja import Query, Router

from accounts import social_service as service
from accounts.auth import current_user, optional_user
from accounts.schemas import MemberCard, MemberProfile, SocialSettings
from library import mypage_service
from library.diary_schemas import DiaryFeed
from library.mypage_schemas import ProfileOut, ProfileWrite

router = Router(tags=["accounts"])


def no_store(response):
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/me/profile", auth=current_user, response=ProfileOut)
def profile(request, response: HttpResponse):
    no_store(response)
    return mypage_service.get_profile(request.auth)


@router.put("/me/profile", auth=current_user, response=ProfileOut)
def save_profile(request, response: HttpResponse, body: ProfileWrite):
    no_store(response)
    return mypage_service.save_profile(request.auth, body)


@router.get("/me/social", auth=current_user, response=MemberProfile)
def my_social(request, response: HttpResponse):
    no_store(response)
    return service.profile(request.auth, request.auth)


@router.put("/me/social", auth=current_user, response=MemberProfile)
def save_social(request, response: HttpResponse, body: SocialSettings):
    no_store(response)
    return service.save_settings(request.auth, body)


@router.get("/users/{public_id}", auth=optional_user, response=MemberProfile)
def member_profile(request, response: HttpResponse, public_id: str):
    no_store(response)
    member = service.member(public_id)
    return service.profile(member, request.optional_user)


@router.get("/users/{public_id}/diary", response=DiaryFeed)
def member_diary(
    request,
    response: HttpResponse,
    public_id: str,
    limit: int = Query(12, ge=1, le=30),
    before_id: int | None = Query(None, gt=0),
):
    no_store(response)
    member = service.member(public_id)
    return service.public_diary(member, limit=limit, before_id=before_id)


@router.put("/users/{public_id}/follow", auth=current_user, response={204: None})
def follow_member(request, public_id: str):
    service.follow(request.auth, service.member(public_id), True)
    return 204, None


@router.delete("/users/{public_id}/follow", auth=current_user, response={204: None})
def unfollow_member(request, public_id: str):
    service.follow(request.auth, service.member(public_id), False)
    return 204, None


@router.get("/users/{public_id}/followers", auth=optional_user, response=list[MemberCard])
def member_followers(request, response: HttpResponse, public_id: str):
    no_store(response)
    member = service.member(public_id)
    return service.members(member, request.optional_user, followers=True)


@router.get("/users/{public_id}/following", auth=optional_user, response=list[MemberCard])
def member_following(request, response: HttpResponse, public_id: str):
    no_store(response)
    member = service.member(public_id)
    return service.members(member, request.optional_user, followers=False)
