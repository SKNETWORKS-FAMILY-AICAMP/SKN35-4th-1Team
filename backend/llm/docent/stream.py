"""SSE delivery of the same docent graph as the JSON route."""

from collections.abc import AsyncIterator
from typing import Literal

from starlette.concurrency import run_in_threadpool

from chat import chat_service
from chat.schemas import ChatRequest, ChatResponse
from llm.docent.graph import docent_graph

EventName = Literal["token", "replace", "done"]
ChatEvent = tuple[EventName, str | ChatResponse]


async def answer_events(
    *, artwork_id: int, body: ChatRequest, user_id: int | None
) -> AsyncIterator[ChatEvent]:
    """Stream provisional text, then replace it with a validated final answer."""

    state: dict = {}
    # 동기 노드(DB·검색)는 LangGraph 가 이벤트 루프 밖 스레드에서 차례로 실행한다.
    async for mode, chunk in docent_graph.astream(
        {"artwork_id": artwork_id, "body": body, "user_id": user_id, "stream": True},
        stream_mode=["custom", "values"],
    ):
        if mode == "custom":
            yield chunk
        else:
            state = chunk

    response = state["response"]
    shown = state.get("streamed")
    if shown is None:
        yield "token", response.answer
    elif response.answer != shown:
        yield "replace", response.answer

    if user_id is not None:
        await run_in_threadpool(
            chat_service.save_exchange,
            user_id=user_id,
            artwork_id=artwork_id,
            question=body.question,
            response=response,
        )
    yield "done", response
