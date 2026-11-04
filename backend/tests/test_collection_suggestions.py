"""Collection offers use saved substantive questions and appear once."""

from types import SimpleNamespace

import pytest

from chat.models import ChatRole
from chat.schemas import ChatRequest, ChatResponse
from llm.docent import collection_suggestions as offers

SAVED = []


@pytest.fixture(autouse=True)
def saved_messages(monkeypatch):
    monkeypatch.setattr(
        offers.chat_repository, "list_messages", lambda session_id: SAVED
    )


def conversation(*exchanges):
    messages = []
    for question, refused in exchanges:
        messages.append(SimpleNamespace(
            id=len(messages) + 1, role=ChatRole.USER, content=question, refused=False
        ))
        messages.append(SimpleNamespace(
            id=len(messages) + 1, role=ChatRole.ASSISTANT, content="답", refused=refused
        ))
    SAVED[:] = messages


def interested(*exchanges):
    conversation(*exchanges)
    return offers.first_interest(1, 1)


def test_first_answered_third_substantive_question_only(monkeypatch):
    monkeypatch.setattr(offers.chat_repository, "get_session_id", lambda *a, **kw: 1)
    exchanges = (
        ("작품의 재료는?", False),
        ("작가 이름을 답변에 넣지마", False),
        ("색은 어떻게 사용했나요?", False),
        ("왜 이름을 말 안해?", False),
        ("이 작품은 언제 제작됐나요?", False),
    )
    assert not interested(*exchanges[:4])
    assert interested(*exchanges[:5])
    assert not interested(*exchanges, ("다른 근거도 있나요?", False))


def test_refused_third_question_allows_next_answer(monkeypatch):
    monkeypatch.setattr(offers.chat_repository, "get_session_id", lambda *a, **kw: 1)
    questions = (
        ("재료는?", False),
        ("색은?", False),
        ("기법은?", True),
        ("제작 시기는?", False),
    )
    assert not interested(*questions[:3])
    assert interested(*questions)


def test_current_correction_never_offers(monkeypatch):
    monkeypatch.setattr(
        offers, "first_interest", lambda *a: (_ for _ in ()).throw(AssertionError("queried"))
    )
    answer = ChatResponse(answer="알겠습니다", refused=False, sources=[])
    body = ChatRequest(question="왜 이름을 말 안해?")
    assert offers.suggest(1, 1, body, answer) is None
