"""사조, 작가, 작품. 3차 TiDB 테이블을 그대로 쓰므로 Django가 스키마를 바꾸지 않는다."""

from django.db import models
from django_tidb.fields.vector import VectorField

EMBEDDING_DIMENSION = 1536


class ArtMovement(models.Model):
    id = models.BigAutoField(primary_key=True)
    slug = models.CharField(unique=True, max_length=100)
    name = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'art_movements'

    def __str__(self):
        return self.name


class Artist(models.Model):
    id = models.BigAutoField(primary_key=True)
    slug = models.CharField(unique=True, max_length=120)
    name = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200, blank=True, null=True)
    movement = models.ForeignKey(ArtMovement, models.DO_NOTHING, blank=True, null=True)
    birth_year = models.SmallIntegerField(blank=True, null=True)
    death_year = models.SmallIntegerField(blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    portrait_url = models.CharField(max_length=1024, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'artists'

    def __str__(self):
        return self.name


class Artwork(models.Model):
    id = models.BigAutoField(primary_key=True)
    slug = models.CharField(unique=True, max_length=160)
    artist = models.ForeignKey(Artist, models.DO_NOTHING)
    movement = models.ForeignKey(ArtMovement, models.DO_NOTHING, blank=True, null=True)
    title = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True, null=True)
    year_label = models.CharField(max_length=50, blank=True, null=True)
    year_start = models.SmallIntegerField(blank=True, null=True)
    medium = models.CharField(max_length=255, blank=True, null=True)
    dimensions = models.CharField(max_length=100, blank=True, null=True)
    collection = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image_url = models.CharField(max_length=1024, blank=True, null=True)
    image_source_url = models.CharField(max_length=1024, blank=True, null=True)
    image_license = models.CharField(max_length=100, blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'artworks'

    def __str__(self):
        return self.title


class ArtworkEmbedding(models.Model):
    artwork = models.OneToOneField(Artwork, models.DO_NOTHING, primary_key=True)
    embedding = VectorField(dimensions=EMBEDDING_DIMENSION)
    embedding_model = models.CharField(max_length=64)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'artwork_embeddings'
