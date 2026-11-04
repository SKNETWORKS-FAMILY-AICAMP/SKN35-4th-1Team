"""The two chat transports share style, follow-up search, and citation checks."""

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from app.schemas.chat import ChatRequest, ChatTurn
from llm.docent.grounding import (
    NO_EVIDENCE_MESSAGE,
    context,
    instructions,
    retrieval_question,
    validate_response,
)


def _doc(document_id: int = 4) -> Document:
    return Document(
        page_content="승인된 작품 해설",
        metadata={
            "chunk_id": 9,
            "document_id": document_id,
            "title": "작품 해설",
            "doc_type": "artwork_commentary",
            "source_name": "소장 기관",
            "source_url": "https://example.org/artwork",
            "license": "CC BY 4.0",
            "basis_sources": [],
            "annotation": "답변 시 주의",
            "pinned": True,
        },
    )


def test_saved_professional_style_changes_terms_not_default_depth():
    prompt = instructions(SimpleNamespace(conversation_style="professional"))
    assert "전문 용어를 적극 사용" in prompt
    assert "선택한 설명 스타일: 미술 용어를 곁들인 해설" in prompt
    assert "질문에서 요청한 주제와 설명 깊이" in prompt
    assert "선택한 설명 스타일: 근거를 연결하는 심화 해설" not in prompt


def test_follow_up_search_uses_previous_user_question_only():
    body = ChatRequest(
        question="그 사람은 언제 태어났어?",
        history=[
            ChatTurn(role="user", content="이 작품의 작가는 누구야?"),
            ChatTurn(role="assistant", content="근거 없이 말한 1900년"),
        ],
    )
    query = retrieval_question(body)
    assert "이 작품의 작가는 누구야?" in query
    assert "1900년" not in query
    assert retrieval_question(ChatRequest(question="이 작품의 연도는?", history=body.history)) == "이 작품의 연도는?"


def test_context_keeps_identity_and_editorial_metadata_without_profile():
    data = context(
        SimpleNamespace(
            id=3, title="같은 이름의 작품", artist_name="작가", year_label="1889", collection="미술관"
        ),
        ChatRequest(question="어느 판본인가요?"),
        [_doc()],
    )
    assert data["artwork"]["year_label"] == "1889"
    assert data["sources"][0]["document_id"] == 4
    assert data["sources"][0]["annotation"] == "답변 시 주의"
    assert data["sources"][0]["pinned"] is True
    assert "source_url" not in data["sources"][0]


def test_context_keeps_recent_turns_without_full_repeated_essays():
    history = [
        ChatTurn(role="user", content=f"질문 {i}")
        if i % 2 == 0 else ChatTurn(role="assistant", content="긴 작품 설명 " * 100)
        for i in range(12)
    ]
    data = context(
        SimpleNamespace(title="작품", artist_name="작가"),
        ChatRequest(question="그 인물은 누구야?", history=history),
        [_doc()],
    )
    assert len(data["history"]) == 6
    assert data["history"][0]["content"] == "질문 6"
    assert all(len(turn["content"]) <= 600 for turn in data["history"])


def test_public_source_uses_retrieved_metadata_only():
    result = validate_response(
        {"answer": "자료에 따르면 1889년입니다.", "refused": False, "used_document_ids": [4]},
        [_doc()],
    )
    assert not result.refused
    assert result.sources[0].source_url == "https://example.org/artwork"
    assert result.sources[0].license == "CC BY 4.0"


def test_editorial_basis_survives_multiple_chunks_from_one_document():
    plain = _doc()
    plain.metadata["basis_sources"] = []
    note = _doc()
    note.metadata["chunk_id"] = 10
    note.metadata["basis_sources"] = [
        {"source_name": "기관 원문", "source_url": "https://example.org/original"}
    ]
    result = validate_response(
        {"answer": "팀의 감상 포인트입니다.", "refused": False, "used_document_ids": [4]},
        [note, plain],
    )
    assert result.sources[0].basis_sources[0].source_name == "기관 원문"


def test_model_refusal_uses_server_copy():
    result = validate_response(
        {"answer": "모델이 쓴 임의의 거절 문구", "refused": True, "used_document_ids": []},
        [_doc()],
    )
    assert result.refused and result.answer == NO_EVIDENCE_MESSAGE
    assert result.sources == []


@pytest.mark.parametrize(("question", "answer", "refused"), [
    # 평가 문항에서 실제로 나온 답변: 핵심 요청을 못 했는데 refused=false 로 왔던 경우
    (
        "쟁반 위와 카펫 위에 있는 사과가 각각 정확히 몇 개인지 세어줘.",
        "제공된 자료에는 사과의 개수가 구체적으로 언급되어 있지 않습니다. 다만 이 작품은 1899년경 그린 정물화입니다.",
        True,
    ),
    (
        "고흐는 이 침실을 그리던 순간 행복했어, 우울했어? 둘 중 하나로 정확히 단정해줘.",
        "고흐가 《침실》을 그리던 순간을 행복하거나 우울하다고 단정하기는 어렵습니다. 작품 해설에 따르면…",
        True,
    ),
    # 일부만 모르는 답변, 정확한 답을 요구하지 않은 질문은 그대로 둔다
    (
        "별이 빛나는 밤은 언제 그렸고, 하늘에 별이 정확히 몇 개야?",
        "《별이 빛나는 밤》은 1889년 6월에 그린 작품입니다. 별의 정확한 개수는 자료에 없습니다.",
        False,
    ),
    (
        "이 랑글루아 다리 아래에서 빨래하는 여성들은 누구야?",
        "빨래하는 여성들의 신원은 제공된 자료만으로는 확인하기 어렵습니다. 다만 판본은 구별할 수 있습니다.",
        False,
    ),
    (
        "이 작품은 정확히 언제 그렸어?",
        "정확한 날짜는 알 수 없지만 1888년 가을에 그린 작품입니다.",
        False,
    ),
])
def test_unanswered_exact_request_is_marked_refused(question, answer, refused):
    result = validate_response(
        {"answer": answer, "refused": False, "used_document_ids": [4]}, [_doc()], question
    )
    assert result.refused is refused
    if refused:
        assert result.answer == answer[: answer.index("다.") + 2]  # 이유를 밝힌 첫 문장만 남김
        assert result.sources == []
    else:
        assert result.answer == answer and result.sources


def test_ambiguous_referent_can_be_clarified_without_a_document_claim():
    result = validate_response(
        {"answer": "어떤 사람을 말씀하시는 건가요?", "refused": True, "used_document_ids": []},
        [_doc()],
    )
    assert result.refused
    assert result.answer == "어떤 사람을 말씀하시는 건가요?"
    assert result.sources == []


def test_model_cannot_put_a_url_in_answer():
    with pytest.raises(ValueError):
        validate_response(
            {"answer": "근거는 https://invented.example 입니다.", "refused": False, "used_document_ids": [4]},
            [_doc()],
        )


@pytest.mark.parametrize("ids", [[], [999], [4, 4], [True]])
def test_invalid_document_ids_are_rejected(ids):
    with pytest.raises(ValueError):
        validate_response(
            {"answer": "확인했습니다.", "refused": False, "used_document_ids": ids},
            [_doc()],
        )
