"""끊긴 TiDB 연결을 재사용하지 않는지 확인한다 (DB 없이 가짜 연결로)."""

from unittest.mock import MagicMock, patch

from config.db.base import DatabaseWrapper
from django_tidb.base import DatabaseWrapper as TiDBDatabaseWrapper


def _wrapper(*, usable: bool, errors: bool):
    w = DatabaseWrapper.__new__(DatabaseWrapper)
    w.connection = MagicMock()
    w.in_atomic_block = False
    w.errors_occurred = errors
    w.last_used = 10**12  # 방금 쓴 연결 (idle 아님)
    w.is_usable = MagicMock(return_value=usable)
    w.close = MagicMock()
    return w


def test_broken_connection_after_error_is_closed_even_if_recent():
    w = _wrapper(usable=False, errors=True)
    with patch.object(TiDBDatabaseWrapper, "_cursor", return_value="cursor"), patch(
        "config.db.base.time.monotonic", return_value=10**12 + 1
    ):
        assert w._cursor() == "cursor"
    w.close.assert_called_once()


def test_healthy_connection_after_error_is_kept_and_flag_cleared():
    w = _wrapper(usable=True, errors=True)
    with patch.object(TiDBDatabaseWrapper, "_cursor", return_value="cursor"), patch(
        "config.db.base.time.monotonic", return_value=10**12 + 1
    ):
        w._cursor()
    w.close.assert_not_called()
    assert w.errors_occurred is False


def test_recent_connection_without_error_skips_ping():
    w = _wrapper(usable=False, errors=False)
    with patch.object(TiDBDatabaseWrapper, "_cursor", return_value="cursor"), patch(
        "config.db.base.time.monotonic", return_value=10**12 + 1
    ):
        w._cursor()
    w.is_usable.assert_not_called()
