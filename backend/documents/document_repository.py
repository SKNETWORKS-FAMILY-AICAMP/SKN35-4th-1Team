"""챗봇 검색에 쓰는 TiDB 조회. 벡터 거리는 Chroma 가 계산하고, 여기서는 범위와 출처만 다룬다 (docs/rag-handoff.md 5·6절)."""

from dataclasses import dataclass, field

from django.db.models import F, Func, TextField, Value

from catalog.models import Artwork
from documents.models import (
    Document,
    DocumentArtist,
    DocumentBasis,
    DocumentChunk,
)
from llm.rag.chunking import ANNOTATION_SECTIONS, annotation_section

CORRECTION = ANNOTATION_SECTIONS[1]  # "답변 시 주의": 원문의 오래된 정보·오류를 바로잡은 보정문
ARTIST_COMPARISON = "artist_comparison"


@dataclass(frozen=True)
class DocumentSource:
    """답변 아래 출처 표시에 쓰는 값."""

    document_id: int
    doc_key: str
    doc_type: str
    title: str
    source_name: str | None
    source_url: str | None
    license: str | None
    # 덧붙인 절(감상 포인트·답변 시 주의)의 편집 근거: [{"source_name", "source_url"}]
    basis_sources: list[dict[str, str | None]] = field(default_factory=list)


def scope_document_ids(artwork_id: int) -> list[int]:
    """① 그 작품의 해설 + ②③ 그 작가가 연결된 생애·연표·비교 문서. 작품이 없으면 빈 목록."""
    own = Document.objects.filter(artwork_id=artwork_id, needs_review=False)
    by_artist = DocumentArtist.objects.filter(
        artist__artwork__id=artwork_id, document__needs_review=False
    )
    ids = set(own.values_list("id", flat=True))
    return sorted(ids | set(by_artist.values_list("document_id", flat=True)))


def pinned_chunk_ids(artwork_id: int, scope_ids: list[int]) -> list[int]:
    """거리와 상관없이 항상 넣을 청크.

    - ④ 그 작품을 언급한 연표 사건(document_artworks). 질문 벡터만으로는 상위에 오지 않을 수 있다.
    - 범위 안 문서의 `답변 시 주의` 보정문. 짧아서 순위에서 밀리면 원문의 틀린 정보로 답하게 된다.
    """
    timeline = DocumentChunk.objects.filter(
        document__documentartwork__artwork_id=artwork_id, document__needs_review=False
    )
    ids = set(timeline.values_list("id", flat=True))
    if scope_ids:
        header = Func(
            F("content"),
            Value("\n"),
            Value(1),
            function="SUBSTRING_INDEX",
            output_field=TextField(),
        )
        rows = (
            DocumentChunk.objects.filter(document_id__in=scope_ids)
            .annotate(header=header)
            .filter(header__icontains=f"> {CORRECTION}")
            .values_list("id", "content")
        )
        ids |= {i for i, content in rows if annotation_section(content) == CORRECTION}
    return sorted(ids)


def document_sources(document_ids: set[int]) -> dict[int, DocumentSource]:
    if not document_ids:
        return {}
    docs = list(Document.objects.filter(id__in=document_ids, needs_review=False))
    basis: dict[int, list[dict[str, str | None]]] = {d.id: list(d.basis_external_sources or []) for d in docs}
    rows = (
        DocumentBasis.objects.filter(document_id__in=basis, basis_document__needs_review=False)
        .order_by("document_id", "basis_document__doc_key")
        .values_list("document_id", "basis_document__source_name", "basis_document__source_url")
    )
    for doc_id, name, url in rows:
        basis[doc_id].insert(0, {"source_name": name, "source_url": url})  # 데이터셋 안 근거를 앞에
    return {
        d.id: DocumentSource(
            document_id=d.id, doc_key=d.doc_key, doc_type=d.doc_type, title=d.title,
            source_name=d.source_name, source_url=d.source_url, license=d.license, basis_sources=basis[d.id],
        )
        for d in docs
    }


def artwork_artist_slug(artwork_id: int) -> str | None:
    """질문 분류(llm.rag.classifier)에 넘길 '고른 작품의 작가' slug. 없는 작품이면 None."""
    return Artwork.objects.filter(id=artwork_id).values_list("artist__slug", flat=True).first()


def name_in_scope(scope_ids: list[int], name: str) -> bool:
    """이름이 범위 문서 본문에 나오는지. 질문 분류가 범위 밖 작가로 거절하기 전에 확인한다."""
    if not scope_ids:
        return False
    return Document.objects.filter(id__in=scope_ids, content__icontains=name).exists()


def comparison_covers(scope_ids: list[int], artist_slugs: tuple[str, ...]) -> bool:
    """범위 안 비교 문서가 질문에 나온 다른 작가를 모두 함께 다루는지. 비교 질문을 답할지 거절할지 가른다."""
    if not scope_ids or not artist_slugs:
        return False
    covered = DocumentArtist.objects.filter(
        document_id__in=scope_ids,
        document__doc_type=ARTIST_COMPARISON,
        artist__slug__in=artist_slugs,
    ).values_list("artist__slug", flat=True)
    return set(artist_slugs) <= set(covered)
