from ninja import NinjaAPI
from ninja.errors import AuthenticationError
from ninja.renderers import BaseRenderer
from pydantic_core import to_json

from accounts.api import router as accounts_router
from catalog.api import router as catalog_router
from chat.api import router as chat_router
from config.exceptions import HTTPException, NotFoundError
from library.api import router as library_router


class PydanticRenderer(BaseRenderer):
    """날짜 형식이 3차 응답과 같도록 Pydantic으로 직렬화한다."""

    media_type = "application/json"

    def render(self, request, data, *, response_status):
        return to_json(data, fallback=str)


api = NinjaAPI(title="Docentalk API", renderer=PydanticRenderer())


def _error(request, status, detail, headers=None):
    response = api.create_response(request, {"detail": detail}, status=status)
    for name, value in (headers or {}).items():
        response[name] = value
    return response


@api.exception_handler(AuthenticationError)
def unauthorized(request, exc):
    return _error(request, 401, "로그인이 필요합니다.", {"WWW-Authenticate": "Bearer"})


@api.exception_handler(HTTPException)
def http_exception(request, exc):
    return _error(request, exc.status_code, exc.detail, exc.headers)


@api.exception_handler(NotFoundError)
def not_found(request, exc):
    return _error(request, 404, exc.detail)


@api.get("/health")
def health(request):
    return {"status": "ok"}


api.add_router("", catalog_router)
api.add_router("", chat_router)
api.add_router("", library_router)
api.add_router("", accounts_router)
