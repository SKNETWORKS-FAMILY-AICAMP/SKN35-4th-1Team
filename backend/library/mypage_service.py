"""Owner filtering is shared by HTTP, the collection assistant and MCP tools."""

import json
from datetime import UTC, date, timedelta
from hashlib import sha256

from django.db import IntegrityError, transaction
from django.db.models import (
    BigIntegerField,
    CharField,
    Count,
    DateField,
    F,
    Q,
    Value,
    Window,
)
from django.db.models.functions import RowNumber
from django.utils import timezone

from accounts.models import User, UserPreference
from catalog import catalog_repository, catalog_service
from catalog.models import Artist, Artwork
from config.exceptions import HTTPException
from library import diary_repository, diary_service
from library.collection_limits import MAX_COLLECTION_ARTWORKS, MAX_SAVED_COLLECTIONS
from library.models import (
    ArtworkLike,
    ArtworkView,
    Collection,
    CollectionItem,
    DiaryEntry,
)
from library.mypage_schemas import (
    ActivityOut,
    ArtworkPage,
    CollectionOut,
    CollectionWrite,
    CritiquePage,
    ProfileOut,
    ProfileWrite,
    TasteOut,
)


def preference(user_id: int) -> UserPreference | None:
    return UserPreference.objects.filter(user_id=user_id).first()


def get_profile(user) -> ProfileOut:
    p = preference(user.id)
    defaults = ProfileWrite(onboarding_completed=False)
    return ProfileOut(
        nickname=user.nickname,
        **{
            key: getattr(p, key)
            if p is not None and getattr(p, key) is not None
            else value
            for key, value in defaults.model_dump(exclude={"nickname"}).items()
        },
    )


def _apply_profile(user, p: UserPreference, body: ProfileWrite) -> None:
    # nickname lives on users (shown in the public feed); omitted means unchanged.
    if body.nickname is not None:
        user.nickname = body.nickname
    for key, value in body.model_dump(exclude={"nickname"}).items():
        setattr(p, key, value)
    p.birth_year = body.birth_date.year if body.birth_date else None
    p.tone = body.conversation_style
    p.explanation_level = (
        "deep" if body.conversation_style == "professional" else "easy"
    )


def _write_profile(user, body: ProfileWrite) -> None:
    p = preference(user.id) or UserPreference(user_id=user.id)
    _apply_profile(user, p, body)
    with transaction.atomic():
        user.save(update_fields=["nickname", "updated_at"])
        p.save()


def save_profile(user, body: ProfileWrite) -> ProfileOut:
    try:
        _write_profile(user, body)
    except IntegrityError:
        # Concurrent first-time onboarding: retry the owner row once.
        _write_profile(user, body)
    return get_profile(user)


def own_collection(user_id, collection_id):
    row = Collection.objects.filter(id=collection_id, user_id=user_id).first()
    if row is None:
        raise HTTPException(404, "컬렉션을 찾을 수 없어요.")
    return row


def card_rows(artworks):
    """Cards for artworks that were loaded with their artist."""
    return [catalog_service.to_artwork_card(a, a.artist.name) for a in artworks]


def collection_cards(collection_id, limit=3, before_id=None):
    artworks = catalog_repository.with_artist().filter(
        collectionitem__collection_id=collection_id
    )
    if before_id is not None:
        artworks = artworks.filter(id__lt=before_id)
    return card_rows(artworks.order_by("-id")[:limit])


def collection_previews(collection_id, limit=3):
    """Earliest added first: the first preview is the collection cover."""
    items = (
        CollectionItem.objects.filter(collection_id=collection_id)
        .select_related("artwork__artist")
        .order_by("created_at", "artwork_id")[:limit]
    )
    return card_rows(item.artwork for item in items)


def serialize_collection(row):
    return CollectionOut(
        id=row.id,
        name=row.name,
        description=row.description,
        artwork_count=CollectionItem.objects.filter(collection_id=row.id).count(),
        previews=collection_previews(row.id),
    )


def collections(user_id):
    # Keep collections saved under the previous quota visible.
    rows = list(
        Collection.objects.filter(user_id=user_id).order_by("-updated_at", "-id")[:50]
    )
    if not rows:
        return []
    ids = [r.id for r in rows]
    items = CollectionItem.objects.filter(collection_id__in=ids)
    counts = dict(
        items.values_list("collection_id").annotate(total=Count("*")).order_by()
    )
    ranked = (
        items.select_related("artwork__artist")
        .annotate(
            rank=Window(
                RowNumber(),
                partition_by="collection_id",
                order_by=["created_at", "artwork_id"],
            )
        )
        .filter(rank__lte=3)
        .order_by("collection_id", "rank")
    )
    previews = {i: [] for i in ids}
    for item in ranked:
        art = item.artwork
        previews[item.collection_id].append(
            catalog_service.to_artwork_card(art, art.artist.name)
        )
    return [
        CollectionOut(
            id=r.id,
            name=r.name,
            description=r.description,
            artwork_count=counts.get(r.id, 0),
            previews=previews[r.id],
        )
        for r in rows
    ]


def save_collection(user_id, body: CollectionWrite, collection_id=None):
    initial = getattr(body, "artwork_ids", []) if collection_id is None else []
    if len(set(initial)) > MAX_COLLECTION_ARTWORKS:
        raise HTTPException(
            409, f"컬렉션에는 작품을 {MAX_COLLECTION_ARTWORKS}점까지 담을 수 있어요."
        )
    row = (
        own_collection(user_id, collection_id)
        if collection_id is not None
        else None
    )
    try:
        with transaction.atomic():
            if row is None:
                # Concurrent creates wait on the user row; the locking read then sees
                # rows they committed (a plain COUNT reuses the snapshot and allows 11).
                list(User.objects.select_for_update().filter(id=user_id).values_list("id"))
                count = len(
                    Collection.objects.select_for_update()
                    .filter(user_id=user_id)
                    .values_list("id")
                )
                if count >= MAX_SAVED_COLLECTIONS:
                    raise HTTPException(
                        409, f"컬렉션은 {MAX_SAVED_COLLECTIONS}개까지 만들 수 있어요."
                    )
                row = Collection(user_id=user_id)
            row.name, row.description = body.name, body.description
            row.save()
            _add_initial_artworks(row, initial)
    except IntegrityError:
        raise HTTPException(409, "같은 이름의 컬렉션이 있어요.") from None
    return serialize_collection(row)


def _add_initial_artworks(row, artwork_ids):
    """Fill a new collection in the given order (chat or MCP proposals)."""
    ids = list(dict.fromkeys(artwork_ids))
    if not ids:
        return
    found = set(Artwork.objects.filter(id__in=ids).values_list("id", flat=True))
    if missing := [i for i in ids if i not in found]:
        raise HTTPException(404, f"작품을 찾을 수 없습니다: {missing[0]}")
    # DATETIME keeps whole seconds; spacing the times keeps the given order,
    # so the first artwork stays the cover. All stay at or before now.
    start = timezone.now() - timedelta(seconds=len(ids))
    CollectionItem.objects.bulk_create(
        CollectionItem(
            collection_id=row.id,
            artwork_id=artwork_id,
            created_at=start + timedelta(seconds=i),
        )
        for i, artwork_id in enumerate(ids)
    )


def delete_collection(user_id, collection_id):
    row = own_collection(user_id, collection_id)
    with transaction.atomic():
        CollectionItem.objects.filter(collection_id=row.id).delete()
        row.delete()


def add_artwork(user_id, collection_id, artwork_id):
    row = own_collection(user_id, collection_id)
    catalog_service.ensure_artwork(artwork_id)
    items = CollectionItem.objects.filter(collection_id=collection_id)
    try:
        with transaction.atomic():
            # Concurrent adds wait on the collection row; the locking read then sees
            # items they committed, so two adds cannot both pass at 29 items.
            list(
                Collection.objects.select_for_update()
                .filter(id=collection_id)
                .values_list("id")
            )
            existing = set(
                items.select_for_update().values_list("artwork_id", flat=True)
            )
            if artwork_id not in existing:
                if len(existing) >= MAX_COLLECTION_ARTWORKS:
                    raise HTTPException(
                        409,
                        f"컬렉션에는 작품을 {MAX_COLLECTION_ARTWORKS}점까지 담을 수 있어요.",
                    )
                CollectionItem.objects.create(
                    collection_id=collection_id, artwork_id=artwork_id
                )
                row.save(update_fields=["updated_at"])
    except IntegrityError:
        if not items.filter(artwork_id=artwork_id).exists():
            raise
    return serialize_collection(row)


def remove_artwork(user_id, collection_id, artwork_id):
    row = own_collection(user_id, collection_id)
    with transaction.atomic():
        CollectionItem.objects.filter(
            collection_id=collection_id, artwork_id=artwork_id
        ).delete()
        row.save(update_fields=["updated_at"])


def collection_page(user_id, collection_id, limit, before_id):
    own_collection(user_id, collection_id)
    cards = collection_cards(collection_id, limit + 1, before_id)
    return ArtworkPage(
        items=cards[:limit],
        next_cursor=cards[limit - 1].id if len(cards) > limit else None,
    )


def critiques(user_id, limit, before_id):
    entries = diary_repository.entries().filter(user_id=user_id)
    if before_id is not None:
        entries = entries.filter(id__lt=before_id)
    rows = [diary_repository.to_row(e) for e in entries.order_by("-id")[: limit + 1]]
    return CritiquePage(
        items=[diary_service.serialize(r) for r in rows[:limit]],
        next_cursor=rows[limit - 1][0].id if len(rows) > limit else None,
    )


def activity(user_id, limit, offset):
    def literal(value):
        return Value(value, output_field=CharField())

    no_artwork = Value(None, output_field=BigIntegerField())
    no_date = Value(None, output_field=DateField())
    columns = ("kind", "label", "at", "art", "day")
    views = ArtworkView.objects.filter(user_id=user_id).annotate(
        kind=literal("view"),
        label=F("artwork__title"),
        at=F("last_viewed_at"),
        art=F("artwork_id"),
        day=F("viewed_on"),
    )
    likes = ArtworkLike.objects.filter(user_id=user_id).annotate(
        kind=literal("like"),
        label=F("artwork__title"),
        at=F("created_at"),
        art=F("artwork_id"),
        day=no_date,
    )
    diary = DiaryEntry.objects.filter(user_id=user_id).annotate(
        kind=literal("diary"),
        label=literal("감상·비평을 남겼어요"),
        at=F("updated_at"),
        art=F("artwork_id"),
        day=F("entry_date"),
    )
    saved = Collection.objects.filter(user_id=user_id).annotate(
        kind=literal("collection"),
        label=F("name"),
        at=F("updated_at"),
        art=no_artwork,
        day=no_date,
    )
    events = (
        views.values(*columns)
        .union(
            likes.values(*columns),
            diary.values(*columns),
            saved.values(*columns),
            all=True,
        )
        .order_by("-at", "kind", "art", "label")
    )
    return [
        ActivityOut(
            kind=e["kind"],
            title=e["label"],
            occurred_at=e["at"].replace(tzinfo=UTC),
            artwork_id=e["art"],
            entry_date=date.fromisoformat(e["day"])
            if isinstance(e["day"], str)
            else e["day"],
        )
        for e in events[offset : offset + limit]
    ]


def taste_impressions(user_id, limit=20):
    # Only impressions the member already published. The intro is shown on the
    # public profile, so private diary text never reaches it.
    contents = (
        DiaryEntry.objects.filter(user_id=user_id, is_public=True)
        .order_by("-id")
        .values_list("content", flat=True)[:limit]
    )
    return [content[:300] for content in contents]


def taste_evidence(user_id):
    # Every supplied work belongs to the caller's likes or collections. No private
    # diary text, birth date, email or Firebase identifiers reach the language model.
    liked = ArtworkLike.objects.filter(user_id=user_id).values("artwork_id")
    collected = CollectionItem.objects.filter(collection__user_id=user_id).values(
        "artwork_id"
    )
    return card_rows(
        catalog_repository.with_artist()
        .filter(Q(id__in=liked) | Q(id__in=collected))
        .order_by("id")[:100]
    )


def taste_fingerprint(evidence, impressions=()):
    payload = [e.model_dump() for e in evidence]
    if impressions:
        payload = {"works": payload, "impressions": list(impressions)}
    return sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def get_taste(user_id):
    p = preference(user_id)
    evidence = taste_evidence(user_id)
    impressions = taste_impressions(user_id)
    return TasteOut(
        summary=p.taste_summary if p else None,
        evidence=evidence,
        impression_count=len(impressions),
        generated_at=p.taste_generated_at.replace(tzinfo=UTC)
        if p and p.taste_generated_at
        else None,
        stale=bool(
            p
            and p.taste_summary
            and p.taste_fingerprint != taste_fingerprint(evidence, impressions)
        ),
    )


def find_artists(query) -> list[tuple[int, str]]:
    """(id, name) of catalog artists named in user text, by alias first then name."""
    from llm.rag.classifier import collected_artist_slugs

    term = query.strip()[:40]
    if not term:
        return []
    slugs = collected_artist_slugs(term)
    artists = (
        Artist.objects.filter(slug__in=slugs)
        if slugs
        else Artist.objects.filter(name__icontains=term)
    )
    return list(artists.order_by("id").values_list("id", "name")[:5])


def search_artworks(query, limit=8):
    # Django escapes LIKE metacharacters; user text is data, never SQL or tool instructions.
    term = query.strip()[:80]
    return card_rows(
        catalog_repository.with_artist()
        .filter(Q(title__icontains=term) | Q(artist__name__icontains=term))
        .order_by("id")[:limit]
    )
