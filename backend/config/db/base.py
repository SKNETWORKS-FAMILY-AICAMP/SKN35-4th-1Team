"""django-tidb에 끊긴 연결 확인을 더한 백엔드.

LangGraph 노드처럼 요청 밖 스레드의 연결은 Django가 정리하지 않아서, 오래 쉬면
서버가 끊은 연결을 그대로 쓰게 된다. 3차의 ``pool_pre_ping``과 같은 역할이다.
쿼리 오류로 연결이 망가진 경우(``errors_occurred``)도 같은 방식으로 버리고 다시 연결한다.
"""

import time
from contextlib import suppress

from django.db import Error
from django_tidb.base import DatabaseWrapper as TiDBDatabaseWrapper

IDLE_SECONDS = 60


class DatabaseWrapper(TiDBDatabaseWrapper):
    last_used = 0.0

    def _cursor(self, name=None):
        now = time.monotonic()
        idle = now - self.last_used > IDLE_SECONDS
        suspect = idle or self.errors_occurred
        if self.connection is not None and suspect and not self.in_atomic_block:
            if self.is_usable():
                self.errors_occurred = False
            else:
                with suppress(Error):  # 이미 끊겼다. close()는 실패해도 연결을 비운다.
                    self.close()
        self.last_used = now
        return super()._cursor(name)
