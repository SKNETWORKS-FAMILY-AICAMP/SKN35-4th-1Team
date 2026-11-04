"""작품 도슨트 채팅과 채팅 기록.

질문은 로그인 없이도 가능하고, 로그인 상태면 질문과 답변을 저장한다.
답변 맥락은 로그인 여부와 관계없이 요청의 `history`로 받는다.
"""

import json
import logging

from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from ninja import Router

from accounts.auth import current_user, optional_user
from chat import chat_service
from chat.schemas import ChatMessageOut, ChatRequest, ChatResponse, ChatSummary
from config.exceptions import HTTPException
from llm.docent import collection_suggestions
from llm.docent import graph as docent_service
from llm.docent import stream as docent_stream

router = Router(tags=["chat"])
logger = logging.getLogger(__name__)


def _frame(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/artworks/{artwork_id}/chat", auth=optional_user, response=ChatResponse)
def ask(request, artwork_id: int, body: ChatRequest):
    """작품 도슨트에게 질문. 근거가 없으면 `refused: true`.

    RAG 답변이 나오면 로그인 사용자는 `chat_service.save_exchange`로 저장한다.
    """
    user = request.optional_user
    response = docent_service.answer(artwork_id, body, user_id=user.id if user else None)
    if user is not None:
        chat_service.save_exchange(user_id=user.id, artwork_id=artwork_id, question=body.question, response=response)
        response.suggestion = collection_suggestions.suggest(user.id, artwork_id, body, response)
    return response


@router.post("/artworks/{artwork_id}/chat/stream", auth=optional_user)
def ask_stream(request, artwork_id: int, body: ChatRequest):
    """임시 답변을 흘려보내고, 검증이 끝난 최종 응답을 한 번 보낸다."""
    user_id = request.optional_user.id if request.optional_user else None

    async def events():
        try:
            async for event, payload in docent_stream.answer_events(
                artwork_id=artwork_id, body=body, user_id=user_id
            ):
                if event == "done":
                    assert isinstance(payload, ChatResponse)
                    if user_id is not None:
                        payload.suggestion = await sync_to_async(
                            collection_suggestions.suggest, thread_sensitive=False
                        )(user_id, artwork_id, body, payload)
                    frame = payload.model_dump(mode="json")
                    if frame["suggestion"] is None:
                        del frame["suggestion"]  # keep the done frame unchanged without an offer
                    yield _frame(event, frame)
                else:
                    assert isinstance(payload, str)
                    yield _frame(event, {"content": payload})
        except HTTPException as exc:
            yield _frame("error", {"message": str(exc.detail)})
        except Exception as exc:  # noqa: BLE001 -- SSE boundary must end with a safe error frame.
            # Provider exceptions may contain request data. Log the type only.
            logger.error("Docent stream failed for artwork_id=%s: %s", artwork_id, type(exc).__name__)
            yield _frame("error", {"message": "AI 응답을 완료하지 못했어요. 다시 시도해 주세요."})

    return StreamingHttpResponse(
        events(),
        content_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/artworks/{artwork_id}/chat/messages", auth=current_user, response=list[ChatMessageOut])
def list_messages(request, artwork_id: int):
    """이 작품과 나눈 내 대화 기록 (오래된 순). 대화가 없으면 빈 배열."""
    return chat_service.list_messages(user_id=request.auth.id, artwork_id=artwork_id)


@router.delete("/artworks/{artwork_id}/chat", auth=current_user, response={204: None})
def reset_chat(request, artwork_id: int):
    """이 작품 대화 초기화. 대화가 없어도 204."""
    chat_service.reset(user_id=request.auth.id, artwork_id=artwork_id)
    return 204, None


@router.get("/me/chats", auth=current_user, response=list[ChatSummary])
def list_my_chats(request):
    """내가 대화한 작품 목록 (최근 대화순)."""
    return chat_service.list_chats(user_id=request.auth.id)
