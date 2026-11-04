"""DB `documents` 를 청킹·임베딩해 `document_chunks` 에 넣는다.

backend/ 에서 실행::

    uv run python -m scripts.build_chunks --dry-run      # 무엇을 할지만 출력 (API 호출·쓰기 없음)
    uv run python -m scripts.build_chunks --limit 3      # 문서 3건만 처리해 보기
    uv run python -m scripts.build_chunks                # 전체 실행

needs_review=false인 승인 문서만 처리한다. 검수 대기 문서의 기존 청크는 이 스크립트가 삭제하지 않지만, 검색 계층에서 제외한다.

여러 번 돌려도 안전하다. 문서마다 지금 규칙으로 자른 청크와 DB 의 청크를 비교해서,
본문이나 청킹 규칙이 바뀌었거나 다른 임베딩 모델로 만든 문서만 청크를 지우고 다시 만든다.
나머지는 건너뛰므로 API 비용은 바뀐 문서에만 든다. 삭제된 문서의 청크는 FK CASCADE 로 함께 지워진다.

문서 단위로 커밋하므로 중간에 멈춰도 끝난 문서는 남고, 다시 실행하면 남은 문서부터 이어서 한다.
"""

import argparse
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from django.db import transaction

from documents.models import Document, DocumentChunk
from llm.clients import embedding_client
from llm.rag.chunking import Chunk, chunk_document

DOCS_PER_EMBED_CALL = 20  # 이 문서 수만큼 청크를 모아 한 번에 임베딩하고 커밋한다


@dataclass
class Plan:
    skip: list[int]  # 이미 최신인 문서 id
    new: dict[int, list[Chunk]]  # 청크가 없는 문서
    stale: dict[int, list[Chunk]]  # 청크가 있지만 본문·규칙·모델이 달라진 문서

    @property
    def todo(self) -> dict[int, list[Chunk]]:
        return {**self.new, **self.stale}


def plan(docs: list[dict], existing: dict[int, list[tuple[int, str, str]]], model: str) -> Plan:
    """docs: {id, doc_key, title, content}, existing: 문서 id → [(chunk_index, content, embedding_model)].

    DB 에 접속하지 않는 순수 함수라 테스트에서 그대로 쓴다.
    """
    result = Plan([], {}, {})
    for doc in docs:
        chunks = chunk_document(doc)
        have = sorted(existing.get(doc["id"], []))
        if not have:
            result.new[doc["id"]] = chunks
        elif [(c.chunk_index, c.content, model) for c in chunks] == have:
            result.skip.append(doc["id"])
        else:
            result.stale[doc["id"]] = chunks
    return result


def write(
    todo: dict[int, list[Chunk]],
    model: str,
    embed: Callable[[list[str]], list[list[float]]],
) -> int:
    """문서 묶음마다 임베딩 → 기존 청크 삭제 → 새 청크 추가 → 커밋. 넣은 청크 수를 돌려준다."""
    ids = list(todo)
    written = 0
    for start in range(0, len(ids), DOCS_PER_EMBED_CALL):
        batch = ids[start : start + DOCS_PER_EMBED_CALL]
        chunks = [c for doc_id in batch for c in todo[doc_id]]
        vectors = embed([c.content for c in chunks])  # API 를 먼저 불러서, 실패하면 DB 를 건드리지 않는다
        it = iter(vectors)
        with transaction.atomic():
            DocumentChunk.objects.filter(document_id__in=batch).delete()
            DocumentChunk.objects.bulk_create(
                DocumentChunk(
                    document_id=doc_id,
                    chunk_index=c.chunk_index,
                    content=c.content,
                    embedding=next(it),
                    embedding_model=model,
                )
                for doc_id in batch
                for c in todo[doc_id]
            )
        written += len(chunks)
        print(f"  {start + len(batch)}/{len(ids)} 문서 · 청크 {written}개")
    return written


def load() -> tuple[list[dict], dict[int, list[tuple[int, str, str]]]]:
    docs = list(
        Document.objects.filter(needs_review=False)
        .order_by("doc_key")
        .values("id", "doc_key", "title", "content")
    )
    existing: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    # embedding 컬럼은 읽지 않는다 (청크마다 벡터 6KB 가 네트워크로 넘어옴)
    rows = DocumentChunk.objects.filter(document__needs_review=False).values_list(
        "document_id", "chunk_index", "content", "embedding_model"
    )
    for document_id, chunk_index, content, embedding_model in rows:
        existing[document_id].append((chunk_index, content, embedding_model))
    return docs, existing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="계획만 출력하고 API 호출·DB 쓰기를 하지 않음")
    parser.add_argument("--limit", type=int, help="처리할 문서 수 상한 (시험 실행용)")
    args = parser.parse_args(argv)

    model = embedding_client.model_name()
    docs, existing = load()
    if not docs:
        print("documents 테이블이 비어 있습니다. 문서 적재(load_documents)를 먼저 실행하세요.")
        return 1
    p = plan(docs, existing, model)
    todo = p.todo
    if args.limit is not None:
        todo = dict(list(todo.items())[: args.limit])
    n_chunks = sum(len(v) for v in todo.values())
    n_chars = sum(len(c.content) for v in todo.values() for c in v)
    print(f"모델 {model} · 문서 {len(docs)}건: 최신 {len(p.skip)} · 새로 {len(p.new)} · 다시 만들기 {len(p.stale)}")
    print(f"이번 실행: 문서 {len(todo)}건 · 청크 {n_chunks}개 · {n_chars:,}자")
    if args.dry_run or not todo:
        return 0
    written = write(todo, model, embedding_client.embed_texts)
    print(f"완료: 청크 {written}개 기록")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
