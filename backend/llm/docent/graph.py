"""Docent answer flow as one LangGraph graph, shared by the JSON and SSE routes.

    classify ─(거절·단답)→ END
       └→ scope ─(범위 밖)→ END
            ├→ recommend → END
            └→ retrieve ─(자료 없음)→ END
                 └→ generate → validate → END

A node that decides the final answer sets ``response``; the routers then end the run.
With ``stream=True`` the generate node also emits ``("token" | "replace", text)``
through LangGraph's custom stream so the SSE route can show provisional text.
"""

import json
from typing import Any, TypedDict

from chromadb.errors import ChromaError
from httpx import HTTPError
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from openai import APIError
from pydantic import ValidationError

from catalog import catalog_service, recommendation_service
from chat.schemas import ChatRequest, ChatResponse
from config.app_settings import get_settings
from config.exceptions import HTTPException
from library import mypage_service
from llm.docent import scope as docent_scope
from llm.docent.grounding import (
    NO_EVIDENCE_MESSAGE,
    GroundedAnswer,
    context,
    direct_chat_response,
    retrieval_question,
    validate_response,
)
from llm.docent.grounding import instructions as grounding_instructions
from llm.rag.classifier import Route, classify_artwork, refusal_message
from llm.rag.retriever import retrieve


class DocentState(TypedDict, total=False):
    artwork_id: int
    body: ChatRequest
    user_id: int | None
    stream: bool
    art: Any
    route: Any
    docs: list
    draft: dict | None
    streamed: str | None  # 스트리밍으로 이미 보여 준 답변 본문
    response: ChatResponse


def _refused(text: str) -> ChatResponse:
    return ChatResponse(answer=text, refused=True, sources=[])


def instructions(user_id, explanation_style=None):
    preference = mypage_service.preference(user_id) if user_id else None
    return grounding_instructions(preference, explanation_style)


def _model(settings):
    return ChatOpenAI(
        model=settings.assistant_model,
        api_key=settings.openai_api_key,
        timeout=25,
        max_retries=0,
        temperature=0.3,
    )


def generate(schema, instruction, data):
    settings = get_settings()
    if settings.openai_api_key is None:
        raise HTTPException(503, "AI 연결 설정이 필요해요.")
    try:
        return _model(settings).with_structured_output(schema).invoke(
            [("system", instruction), ("human", json.dumps(data, ensure_ascii=False))]
        )
    except (APIError, OutputParserException, ValidationError, TimeoutError):
        raise HTTPException(503, "AI 응답을 완료하지 못했어요. 다시 시도해 주세요.") from None


def _titles(works) -> str:
    return " · ".join(f"『{work.title}』" for work in works[:3])


def _similar_answer(works) -> str:
    if not works:
        return "현재 이 작품과 유사한 작품 정보가 아직 준비되지 않았어요."
    return "이 작품과 비슷한 결을 가진 작품을 더 둘러보세요. " + _titles(works)


def _personal_answer(works) -> str:
    if not works:
        return "아직 충분한 취향 데이터가 쌓이지 않았어요."
    items = [
        f"『{work.title}』 — {work.reason}" if work.reason else f"『{work.title}』"
        for work in works[:3]
    ]
    return "이런 작품은 어떠신가요? " + " · ".join(items)


# ── nodes ──────────────────────────────────────────────────────────────


def classify_node(state: DocentState) -> DocentState:
    artwork_id, body = state["artwork_id"], state["body"]
    art = catalog_service.get_artwork(artwork_id)
    route = classify_artwork(artwork_id, body.question)
    update: DocentState = {"art": art, "route": route}
    if route.kind in ("refuse", "other_artist"):
        update["response"] = _refused(refusal_message(route))
    elif (
        route.kind == "rag"
        and len(getattr(route, "artists", ())) <= 1
        and not getattr(route, "names", ())
        and (direct := direct_chat_response(art, state["body"])) is not None
    ):
        update["response"] = direct
    return update


def scope_node(state: DocentState) -> DocentState:
    if docent_scope.is_artwork_request(state["art"], state["body"]):
        return {}
    return {"response": _refused(refusal_message(Route("refuse", "off_topic")))}


def recommend_node(state: DocentState) -> DocentState:
    artwork_id, user_id = state["artwork_id"], state.get("user_id")
    if state["route"].kind == "recommend_personal":
        if user_id is None:
            works = recommendation_service.similar(artwork_id=artwork_id)
            login_hint = "로그인 후 감상 기록이 쌓이면 더 정교한 추천을 받아볼 수 있어요."
            text = (
                f"{login_hint} 현재 작품과 비슷한 작품을 먼저 만나보세요. {_titles(works)}"
                if works
                else f"{login_hint} {_similar_answer(works)}"
            )
        else:
            text = _personal_answer(recommendation_service.recommend_artworks(user_id=user_id))
    else:
        text = _similar_answer(recommendation_service.similar(artwork_id=artwork_id))
    return {"response": ChatResponse(answer=text, refused=False, sources=[])}


def retrieve_node(state: DocentState) -> DocentState:
    try:
        docs = retrieve(state["artwork_id"], retrieval_question(state["body"]))[:40]
    except (ChromaError, APIError, HTTPError, ConnectionError, TimeoutError, ValueError, RuntimeError):
        raise HTTPException(503, "작품 자료를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.") from None
    if not docs:
        return {"docs": [], "response": _refused(NO_EVIDENCE_MESSAGE)}
    return {"docs": docs}


def generate_node(state: DocentState) -> DocentState:
    body = state["body"]
    instruction = instructions(state.get("user_id"), body.explanation_style)
    data = context(state["art"], body, state["docs"])
    if not state.get("stream"):
        return {"draft": generate(GroundedAnswer, instruction, data).model_dump()}

    # 스트리밍: JSON 을 조금씩 파싱해서 answer 본문이 늘어날 때마다 내보낸다.
    settings = get_settings()
    if settings.openai_api_key is None:
        raise HTTPException(503, "AI 연결 설정이 필요해요.")
    parser = JsonOutputParser(pydantic_object=GroundedAnswer)
    write = get_stream_writer()
    latest: dict | None = None
    shown = ""
    for partial in (_model(settings) | parser).stream(
        [
            ("system", instruction + "\n\n" + parser.get_format_instructions()),
            ("human", json.dumps(data, ensure_ascii=False)),
        ]
    ):
        if not isinstance(partial, dict):
            continue
        latest = partial
        text = partial.get("answer")
        if not isinstance(text, str) or text == shown:
            continue
        write(("token", text[len(shown):]) if text.startswith(shown) else ("replace", text))
        shown = text
    return {"draft": latest, "streamed": shown}


def validate_node(state: DocentState) -> DocentState:
    try:
        return {"response": validate_response(state.get("draft"), state["docs"])}
    except (ValueError, AttributeError, TypeError):
        return {"response": _refused(NO_EVIDENCE_MESSAGE)}


# ── edges ──────────────────────────────────────────────────────────────


def _after_classify(state: DocentState) -> str:
    return END if "response" in state else "scope"


def _after_scope(state: DocentState) -> str:
    if "response" in state:
        return END
    return "recommend" if state["route"].kind.startswith("recommend") else "retrieve"


def _after_retrieve(state: DocentState) -> str:
    return END if "response" in state else "generate"


def build_graph():
    graph = StateGraph(DocentState)
    graph.add_node("classify", classify_node)
    graph.add_node("scope", scope_node)
    graph.add_node("recommend", recommend_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("validate", validate_node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", _after_classify, ["scope", END])
    graph.add_conditional_edges("scope", _after_scope, ["recommend", "retrieve", END])
    graph.add_edge("recommend", END)
    graph.add_conditional_edges("retrieve", _after_retrieve, ["generate", END])
    graph.add_edge("generate", "validate")
    graph.add_edge("validate", END)
    return graph.compile()


docent_graph = build_graph()


def answer(artwork_id, body, user_id=None) -> ChatResponse:
    state = docent_graph.invoke(
        {"artwork_id": artwork_id, "body": body, "user_id": user_id}
    )
    return state["response"]
