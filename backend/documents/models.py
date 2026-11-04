"""RAG 문서와 청크. 3차 TiDB 테이블을 그대로 쓰므로 Django가 스키마를 바꾸지 않는다."""

from django.db import models
from django_tidb.fields.vector import VectorField

from catalog.models import EMBEDDING_DIMENSION, Artist, Artwork


class Document(models.Model):
    id = models.BigAutoField(primary_key=True)
    doc_key = models.CharField(unique=True, max_length=191)
    doc_type = models.CharField(max_length=30)
    artwork = models.ForeignKey(Artwork, models.DO_NOTHING, blank=True, null=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    lang = models.CharField(max_length=8)
    topic = models.CharField(max_length=30, blank=True, null=True)
    source_url = models.CharField(max_length=1024, blank=True, null=True)
    source_name = models.CharField(max_length=255, blank=True, null=True)
    license = models.CharField(max_length=100, blank=True, null=True)
    needs_review = models.BooleanField(default=False)
    basis_external_sources = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'documents'

    def __str__(self):
        return self.title


class DocumentArtist(models.Model):
    pk = models.CompositePrimaryKey('document_id', 'artist_id')
    document = models.ForeignKey(Document, models.DO_NOTHING)
    artist = models.ForeignKey(Artist, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'document_artists'


class DocumentArtwork(models.Model):
    pk = models.CompositePrimaryKey('document_id', 'artwork_id')
    document = models.ForeignKey(Document, models.DO_NOTHING)
    artwork = models.ForeignKey(Artwork, models.DO_NOTHING, related_name='linked_documents')

    class Meta:
        managed = False
        db_table = 'document_artworks'


class DocumentBasis(models.Model):
    pk = models.CompositePrimaryKey('document_id', 'basis_document_id')
    document = models.ForeignKey(Document, models.DO_NOTHING)
    basis_document = models.ForeignKey(Document, models.DO_NOTHING, related_name='based_on_by')

    class Meta:
        managed = False
        db_table = 'document_basis_documents'


class DocumentChunk(models.Model):
    id = models.BigAutoField(primary_key=True)
    document = models.ForeignKey(Document, models.DO_NOTHING)
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=EMBEDDING_DIMENSION)
    embedding_model = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'document_chunks'
        unique_together = (('document', 'chunk_index'),)
