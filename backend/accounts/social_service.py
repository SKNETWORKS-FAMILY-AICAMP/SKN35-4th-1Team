"""Member profiles, member follows and follow-list visibility."""

from accounts.models import User, UserFollow, UserPreference
from accounts.schemas import MemberCard, MemberProfile, SocialSettings
from config.exceptions import HTTPException
from library import diary_service
from library.diary_schemas import DiaryFeed

LIST_LIMIT = 200


def member(public_id: str) -> User:
    row = User.objects.filter(public_id=public_id).first()
    if row is None:
        raise HTTPException(404, "이용자를 찾을 수 없어요.")
    return row


def profile(target: User, viewer: User | None) -> MemberProfile:
    me = viewer is not None and viewer.id == target.id
    visible = me or target.follow_list_public
    pref = UserPreference.objects.filter(user_id=target.id).first()
    return MemberProfile(
        id=target.public_id,
        nickname=target.nickname,
        intro=pref.taste_summary if pref else None,
        follower_count=UserFollow.objects.filter(followee_id=target.id).count()
        if visible
        else None,
        following_count=UserFollow.objects.filter(follower_id=target.id).count()
        if visible
        else None,
        follow_list_public=target.follow_list_public,
        is_following=viewer is not None
        and not me
        and UserFollow.objects.filter(
            follower_id=viewer.id, followee_id=target.id
        ).exists(),
        is_me=me,
    )


def public_diary(target: User, *, limit: int, before_id: int | None) -> DiaryFeed:
    return diary_service.get_feed(
        limit=limit, before_id=before_id, artwork_id=None, author_id=target.id
    )


def follow(viewer: User, target: User, enable: bool) -> None:
    if viewer.id == target.id:
        raise HTTPException(400, "자기 자신은 팔로우할 수 없어요.")
    if not enable:
        UserFollow.objects.filter(follower_id=viewer.id, followee_id=target.id).delete()
        return
    # A concurrent identical follow may already have created the row.
    UserFollow.objects.bulk_create(
        [UserFollow(follower_id=viewer.id, followee_id=target.id)],
        ignore_conflicts=True,
    )


def members(
    target: User, viewer: User | None, *, followers: bool
) -> list[MemberCard]:
    if not target.follow_list_public and (viewer is None or viewer.id != target.id):
        raise HTTPException(403, "팔로우 목록을 공개하지 않은 이용자예요.")
    other, own = ("follower", "followee") if followers else ("followee", "follower")
    rows = (
        UserFollow.objects.filter(**{f"{own}_id": target.id})
        .select_related(other)
        .order_by("-created_at", f"-{other}_id")[:LIST_LIMIT]
    )
    users = [getattr(row, other) for row in rows]
    return [MemberCard(id=u.public_id, nickname=u.nickname) for u in users]


def save_settings(user: User, body: SocialSettings) -> MemberProfile:
    user.follow_list_public = body.follow_list_public
    user.save(update_fields=["follow_list_public", "updated_at"])
    return profile(user, user)
