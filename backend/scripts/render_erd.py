"""Render the Django schema as Mermaid and Graphviz ERD files.

Run from ``backend/`` with::

    uv run python -m scripts.render_erd
"""

from __future__ import annotations

import html
import shutil
import subprocess
from pathlib import Path

from django.apps import apps
from django.db import connection, models

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "docs" / "db"

TABLE_GROUPS = {
    "Identity & Preferences": ("users", "social_accounts", "user_preferences"),
    "Catalog": ("art_movements", "artists", "artworks", "artwork_embeddings"),
    "User Activity": (
        "diary_entries",
        "collections",
        "collection_items",
        "theme_collection_cache",
        "artwork_likes",
        "artist_follows",
        "artwork_views",
        "chat_sessions",
        "chat_messages",
    ),
    "Documents & RAG": (
        "documents",
        "document_artists",
        "document_artworks",
        "document_basis_documents",
        "document_chunks",
    ),
}

GROUP_COLORS = {
    "Identity & Preferences": "#E8F2EC",
    "Catalog": "#EDF1F7",
    "User Activity": "#F8F0E5",
    "Documents & RAG": "#F2EDF7",
}

def tables() -> dict:
    return {
        model._meta.db_table: model
        for model in apps.get_models()
        if not model._meta.managed
    }


def ordered_table_names() -> list[str]:
    grouped = [table for names in TABLE_GROUPS.values() for table in names]
    return grouped + sorted(set(tables()) - set(grouped))


def columns(model) -> list:
    # 복합 기본키는 필드로 잡히지만 실제 컬럼이 없다.
    return [field for field in model._meta.local_fields if field.column]


def type_name(field) -> str:
    return (field.db_type(connection) or field.get_internal_type()).split("(")[0].split()[0].lower()


def is_primary_key(model, field) -> bool:
    pk = model._meta.pk
    return field.primary_key or (
        isinstance(pk, models.CompositePrimaryKey) and field.attname in pk.field_names
    )


def key_labels(model, field) -> str:
    labels = []
    if is_primary_key(model, field):
        labels.append("PK")
    if field.is_relation:
        labels.append("FK")
    if field.unique and not field.primary_key:
        labels.append("UK")
    return ",".join(labels)


def foreign_keys(model) -> list:
    return sorted((f for f in columns(model) if f.is_relation), key=lambda f: f.column)


def mermaid_source() -> str:
    lines = ["erDiagram"]
    for table_name in ordered_table_names():
        for field in foreign_keys(tables()[table_name]):
            parent = field.related_model._meta.db_table
            child_cardinality = "o|" if field.one_to_one else "o{"
            lines.append(f'    {parent} ||--{child_cardinality} {table_name} : "{field.column}"')

    lines.append("")
    for table_name in ordered_table_names():
        model = tables()[table_name]
        lines.append(f"    {table_name} {{")
        for field in columns(model):
            keys = key_labels(model, field)
            key_suffix = f" {keys}" if keys else ""
            lines.append(f"        {type_name(field)} {field.column}{key_suffix}")
        lines.append("    }")
    return "\n".join(lines) + "\n"


def graphviz_source() -> str:
    lines = [
        "digraph ERD {",
        '  graph [rankdir="LR", bgcolor="#FBFAF7", pad="0.35", nodesep="0.45", ranksep="1.0", splines="polyline"];',
        '  node [shape="plain", fontname="Malgun Gothic"];',
        '  edge [color="#718076", penwidth="1.2", arrowsize="0.7", fontname="Malgun Gothic", fontsize="9"];',
    ]

    for index, (group_name, table_names) in enumerate(TABLE_GROUPS.items()):
        lines.append(f"  subgraph cluster_{index} {{")
        lines.append(f'    label="{group_name}"; color="{GROUP_COLORS[group_name]}"; penwidth="2"; style="rounded";')
        for table_name in table_names:
            model = tables()[table_name]
            rows = []
            for field in columns(model):
                keys = html.escape(key_labels(model, field)) or "&#160;"
                nullable = "" if field.null or is_primary_key(model, field) else "NOT NULL"
                nullable_label = html.escape(nullable) or "&#160;"
                rows.append(
                    "<TR>"
                    f'<TD ALIGN="LEFT"><FONT COLOR="#66736B">{html.escape(type_name(field))}</FONT></TD>'
                    f'<TD PORT="{html.escape(field.column)}" ALIGN="LEFT">{html.escape(field.column)}</TD>'
                    f'<TD ALIGN="CENTER"><B>{keys}</B></TD>'
                    f'<TD ALIGN="LEFT"><FONT COLOR="#8A928D">{nullable_label}</FONT></TD>'
                    "</TR>"
                )
            label = (
                '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5" COLOR="#ADB6B0">'
                f'<TR><TD COLSPAN="4" BGCOLOR="{GROUP_COLORS[group_name]}"><B>{table_name}</B></TD></TR>'
                + "".join(rows)
                + "</TABLE>>"
            )
            lines.append(f"    {table_name} [label={label}];")
        lines.append("  }")

    for table_name in ordered_table_names():
        for field in foreign_keys(tables()[table_name]):
            parent = field.related_model._meta.db_table
            parent_column = field.target_field.column
            child_column = field.column
            cardinality = "1 : 0..1" if field.one_to_one else "1 : N"
            lines.append(
                f'  {parent}:{parent_column} -> {table_name}:{child_column} '
                f'[label="{cardinality}", arrowhead="vee"];'
            )

    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    dot = shutil.which("dot")
    if dot is None:
        raise SystemExit("Graphviz 'dot' executable was not found.")

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "00_erd.mmd").write_text(mermaid_source(), encoding="utf-8")

    source = graphviz_source()
    for output_format in ("png", "svg"):
        output_path = OUTPUT_DIRECTORY / f"00_erd.{output_format}"
        subprocess.run(
            [dot, f"-T{output_format}", "-o", str(output_path)],
            input=source,
            text=True,
            encoding="utf-8",
            check=True,
        )

    print(f"rendered_tables={len(tables())}")
    print(f"output={OUTPUT_DIRECTORY / '00_erd.png'}")


if __name__ == "__main__":
    main()
