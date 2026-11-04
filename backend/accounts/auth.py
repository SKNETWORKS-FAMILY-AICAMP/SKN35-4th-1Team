"""Firebase Bearer 인증. 토큰 검증은 ``accounts.firebase``를 그대로 쓴다.

필수 인증은 ``request.auth``, 선택 인증은 ``request.optional_user``에 사용자를 둔다.
"""

from ninja.security import HttpBearer

from accounts.firebase import resolve_user


class FirebaseBearer(HttpBearer):
    def __call__(self, request):
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None
        return self.authenticate(request, token.strip())

    def authenticate(self, request, token):
        return resolve_user(token)


class OptionalFirebaseBearer(FirebaseBearer):
    """토큰이 없으면 익명으로 통과하고, 검증에 실패한 토큰은 그대로 401이다."""

    def __call__(self, request):
        request.optional_user = super().__call__(request)
        return True


current_user = FirebaseBearer()
optional_user = OptionalFirebaseBearer()
