"""좋아요, 팔로우, 열람 기록, 컬렉션, 일기.

3차 TiDB 테이블을 그대로 쓰므로 Django가 스키마를 바꾸지 않는다.
"""

from django.db import models
from django.utils import timezone

from accounts.models import User
from catalog.models import Artist, Artwork


class ArtworkLike(models.Model):
    pk = models.CompositePrimaryKey('user_id', 'artwork_id')
    user = models.ForeignKey(User, models.DO_NOTHING)
    artwork = models.ForeignKey(Artwork, models.DO_NOTHING)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'artwork_likes'


class ArtistFollow(models.Model):
    pk = models.CompositePrimaryKey('user_id', 'artist_id')
    user = models.ForeignKey(User, models.DO_NOTHING)
    artist = models.ForeignKey(Artist, models.DO_NOTHING)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'artist_follows'


class ArtworkView(models.Model):
    pk = models.CompositePrimaryKey('user_id', 'viewed_on', 'artwork_id')
    user = models.ForeignKey(User, models.DO_NOTHING)
    viewed_on = models.DateField()
    artwork = models.ForeignKey(Artwork, models.DO_NOTHING)
    view_count = models.IntegerField()
    first_viewed_at = models.DateTimeField()
    last_viewed_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'artwork_views'


class Collection(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, models.DO_NOTHING)
    name = models.CharField(max_length=80)
    description = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'collections'
        unique_together = (('user', 'name'),)

    def __str__(self):
        return self.name


class CollectionItem(models.Model):
    pk = models.CompositePrimaryKey('collection_id', 'artwork_id')
    collection = models.ForeignKey(Collection, models.DO_NOTHING)
    artwork = models.ForeignKey(Artwork, models.DO_NOTHING)
    # 표지 순서를 지키려고 서비스가 시각을 정해서 넣는다.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'collection_items'


class DiaryEntry(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, models.DO_NOTHING)
    entry_date = models.DateField()
    artwork = models.ForeignKey(Artwork, models.DO_NOTHING, blank=True, null=True)
    content = models.TextField()
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'diary_entries'
        unique_together = (('user', 'artwork'),)


class ThemeCollectionCache(models.Model):
    user = models.OneToOneField(User, models.DO_NOTHING, primary_key=True)
    fingerprint = models.CharField(max_length=64, blank=True, null=True)
    themes = models.JSONField(default=list)
    basis = models.JSONField(blank=True, null=True)
    generated_at = models.DateTimeField(blank=True, null=True)
    attempted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'theme_collection_cache'
