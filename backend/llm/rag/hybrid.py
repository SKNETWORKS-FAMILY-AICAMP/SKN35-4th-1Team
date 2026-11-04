"""벡터 순위와 한국어 BM25 순위를 RRF 로 합친다. 검색기와 평가 스크립트가 같은 함수를 쓴다.

벡터 검색만 쓰면 작품명·기법명·연도처럼 단어가 정확히 맞아야 하는 질문에서 생애·연표 같은 긴 문서가
위로 올라온다 (4차 테스트: 청크 Recall@5 0.787). 범위 안 청크 18문항 메모리 실험에서
RRF k=60 · BM25 비중 2배가 Recall@5 0.870 · MRR 0.852 · nDCG@5 0.828 로 목표를 넘었다.
BM25 비중 1.5~3, k 10~60 모두 목표를 넘어 특정 값에 맞춘 결과는 아니다.

    점수 = VECTOR_WEIGHT / (RRF_K + 벡터 순위) + BM25_WEIGHT / (RRF_K + BM25 순위)

두 점수의 단위를 맞출 필요가 없어서 튜닝 부담이 적다. 자리 보장 규칙(작품 해설·비교 문서·문서별 상한)은
이 순위를 매긴 뒤 검색기에서 그대로 적용한다.
"""

from collections.abc import Callable, Sequence
from functools import lru_cache

from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi

RRF_K = 60
VECTOR_WEIGHT = 1.0
BM25_WEIGHT = 2.0
# 명사·고유명사·수사·숫자·외국어·한자·어근만 색인한다. 조사·어미는 문서마다 흔해서 순위를 흐린다.
INDEX_TAGS = frozenset({"NNG", "NNP", "NR", "SN", "SL", "SH", "XR"})


@lru_cache(maxsize=1)
def _kiwi() -> Kiwi:
    """작가 별칭을 사용자 사전에 넣어 '카라바조'·'렘브란트' 같은 이름이 쪼개지지 않게 한다."""
    from llm.rag.classifier import _artists

    kiwi = Kiwi()
    for artist in _artists().values():
        for alias in artist.aliases:
            if " " not in alias and any("가" <= ch <= "힣" for ch in alias):
                kiwi.add_user_word(alias, "NNP", 10)
    return kiwi


# ponytail: 청크 본문 단위 캐시. 청크가 수만 개로 늘면 색인을 미리 만들어 두는 방식으로 바꾼다.
@lru_cache(maxsize=8192)
def tokens(text: str) -> tuple[str, ...]:
    return tuple(t.form.lower() for t in _kiwi().tokenize(text) if t.tag in INDEX_TAGS)


def hybrid_rank[T](
    items: Sequence[T],
    question: str,
    *,
    text: Callable[[T], str],
    distance: Callable[[T], float],
) -> list[T]:
    """items 를 RRF 점수 내림차순으로 돌려준다. BM25 점수가 같으면 벡터 순위가 앞선 쪽을 먼저 둔다."""
    if not items:
        return []
    by_vector = sorted(range(len(items)), key=lambda i: distance(items[i]))
    vector_rank = {i: rank for rank, i in enumerate(by_vector, 1)}
    scores = BM25Okapi([list(tokens(text(item))) or ["_"] for item in items]).get_scores(list(tokens(question)))
    by_bm25 = sorted(range(len(items)), key=lambda i: (-scores[i], vector_rank[i]))
    fused = {i: VECTOR_WEIGHT / (RRF_K + vector_rank[i]) for i in by_vector}
    for rank, i in enumerate(by_bm25, 1):
        fused[i] += BM25_WEIGHT / (RRF_K + rank)
    return [items[i] for i in sorted(fused, key=lambda i: (-fused[i], vector_rank[i]))]
