"""Hybrid ranking lifts exact-term chunks; the retriever keeps its seat rules on top of that ranking."""

from types import SimpleNamespace

import pytest

from documents import document_repository as repo
from llm.rag import retriever
from llm.rag.hybrid import hybrid_rank, tokens


def _rank(items, question):
    return hybrid_rank(items, question, text=lambda x: x[1], distance=lambda x: x[2])


def test_tokens_keep_nouns_numbers_and_artist_names():
    words = tokens("렘브란트는 1642년에 야경을 그렸다")
    assert "렘브란트" in words and "1642" in words
    assert "는" not in words and "그렸다" not in words


def test_exact_term_chunk_overtakes_vector_neighbour():
    # 벡터로는 생애 문서가 가장 가깝지만, 질문의 기법명·연도가 정확히 들어 있는 청크가 위로 온다
    items = [
        ("bio", "렘브란트는 암스테르담에서 활동한 화가로 생애 동안 많은 초상화를 남겼다", 0.30),
        ("bio2", "렘브란트의 가족과 후원자, 말년의 경제적 어려움", 0.32),
        ("tenebrism", "1620년대 초기 작품은 촛불 하나로 밝힌 테네브리즘 명암을 쓴다", 0.45),
    ]
    assert _rank(items, "렘브란트가 1620년대 초기에 촛불로 만든 명암은?")[0][0] == "tenebrism"


def test_without_matching_words_vector_order_is_kept():
    items = [("a", "가을 풍경", 0.1), ("b", "바다 풍경", 0.2), ("c", "도시 풍경", 0.3)]
    assert [x[0] for x in _rank(items, "쓸쓸한 느낌이 드는 이유")] == ["a", "b", "c"]
    assert _rank([], "질문") == []


class FakeCollection:
    def __init__(self, chunks):
        self.chunks = chunks

    def query(self, **kwargs):
        pytest.fail("근사 검색은 필터를 건 청크를 빼먹으므로 쓰지 않는다")

    def get(self, ids=None, where=None, include=None):
        rows = [c for c in self.chunks if (ids is None or c["id"] in ids)]
        return {
            "ids": [c["id"] for c in rows],
            "documents": [c["text"] for c in rows],
            "metadatas": [c["meta"] for c in rows],
            "embeddings": [c["vec"] for c in rows],
        }


def _chunk(chunk_id, doc_id, text, vec, artwork_id=None, doc_type="artist_bio", index=0):
    meta = {"document_id": doc_id, "doc_key": f"doc-{doc_id}", "doc_type": doc_type, "chunk_index": index}
    if artwork_id is not None:
        meta["artwork_id"] = artwork_id
    return {"id": str(chunk_id), "text": text, "meta": meta, "vec": vec}


def test_retriever_puts_own_commentary_first_and_caps_each_document(monkeypatch):
    q = [1.0, 0.0]
    chunks = [
        # 생애 문서 청크 4개가 벡터로 가장 가깝다
        *[_chunk(i, 1, f"작가 생애 이야기 {i}", [1.0, 0.05 * i], index=i) for i in range(1, 5)],
        _chunk(10, 2, "사과와 오렌지 정물의 과일 배치와 흰 천", [0.6, 0.8], artwork_id=7, doc_type="artwork_commentary"),
        _chunk(20, 3, "세잔 연표", [0.5, 0.9]),
    ]
    monkeypatch.setattr(repo, "scope_document_ids", lambda a: [1, 2, 3])
    monkeypatch.setattr(repo, "pinned_chunk_ids", lambda a, scope: [])
    monkeypatch.setattr(
        repo,
        "document_sources",
        lambda ids: {i: SimpleNamespace(document_id=i, doc_key=f"doc-{i}", doc_type="t", title="제목",
                                           source_name=None, source_url=None, license=None, basis_sources=[])
                        for i in ids},
    )
    docs = retriever.retrieve(
        7, "사과와 오렌지에서 흰 천은 어떤 역할이야?", collection=FakeCollection(chunks), embed=lambda _: q
    )
    assert docs[0].metadata["chunk_id"] == 10  # 고른 작품 해설이 맨 앞
    assert sum(d.metadata["document_id"] == 1 for d in docs) <= retriever.MAX_PER_DOC
