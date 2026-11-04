"""Service-level errors. ``config.api`` turns them into ``{"detail": ...}`` responses."""


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str, headers: dict | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = headers


class NotFoundError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
