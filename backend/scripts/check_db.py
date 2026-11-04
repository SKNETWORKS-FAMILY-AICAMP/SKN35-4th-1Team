"""Read-only TiDB connectivity and schema check.

Run from ``backend/`` with::

    uv run python -m scripts.check_db
"""

from django.apps import apps
from django.db import connection


def main() -> None:
    expected_tables = {model._meta.db_table for model in apps.get_models()}

    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE(), VERSION()")
        database, version = cursor.fetchone()
    actual_tables = set(connection.introspection.table_names())

    missing_tables = sorted(expected_tables - actual_tables)

    print("connection=OK")
    print(f"database={database}")
    print(f"version={version}")
    print(f"tables={len(actual_tables)}")
    print(f"missing={','.join(missing_tables) if missing_tables else '(none)'}")

    if missing_tables:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
