"""동적 노드 트리와 매칭 정보 — ADR-0056

트랙을 둘로 가른다.

    트랙 A   wiki_node + wiki_fact       그래프. 카테고리 10만 고정
    트랙 B   company_value               회사 정보 표. key 14 고정

**옛 데이터를 버리지 않는다.** `export.TREE` 가 topic → 경로 표를 이미 들고 있어서
기계적으로 옮길 수 있다 — 그 고정 표가 **동적 트리의 씨앗**이 된다.

    place_kind=value  →  company_value   (place 가 그대로 key 다)
    place_kind=event  →  wiki_node       (topic 을 EVENT_PATH 로 경로로)
    uncategorized     →  Custom/검토 대기  (**버리지 않는다**)

**표를 코드에서 임포트하지 않고 여기 얼린다.** `export.TREE` 는 이 마이그레이션 뒤
지워질 것이라, 임포트하면 다음 사람이 이 파일을 못 돌린다.

Revision ID: c7f2a91b4d38
Revises: 4c1f7a92be08
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7f2a91b4d38"
down_revision: str | None = "4c1f7a92be08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: topic → 노드 경로. `export.TREE` 에서 뽑아 얼린 것이다.
EVENT_PATH: dict[str, str] = {
    "vision": "Company/비전",
    "team": "Company/팀",
    "region_link": "Company/지역관계",
    "service_overview": "Product/소개",
    "service_feature": "Product/기능",
    "service_differentiator": "Product/차별점",
    "development_status": "Product/개발현황",
    "market_size": "Market/시장규모",
    "market_trend": "Market/트렌드",
    "competitor": "Competitor/경쟁사",
    "target_customer": "Customer/타깃고객",
    "customer_problem": "Customer/고객문제",
    "customer_evidence": "Customer/검증",
    "revenue_model": "BusinessModel/수익모델",
    "pricing": "BusinessModel/가격정책",
    "go_to_market": "BusinessModel/판매전략",
    "revenue": "Financial/매출",
    "cost": "Financial/비용",
    "funding": "Financial/자금계획",
    "patent": "Custom/특허",
    "certification": "Custom/인증",
    "technology": "Custom/기술",
    "roadmap": "Plan/일정",
}

#: 갈 자리를 못 찾았던 사실이 가는 곳. **버리지 않는다**
FALLBACK = "Custom/검토 대기"

_PUNCT = re.compile(r"[\s·:()\[\]{}/\\,.\-_]+")


def _norm(s: str) -> str:
    """공백과 구두점을 지운다. **병합 그물이 이걸로 찾는다**(ADR-0056 결정 6)."""
    return _PUNCT.sub("", s or "")


def _norm_path(path: str) -> str:
    """경로는 마디를 유지한 채 마디마다 정규화한다 — `A/기 능` 과 `A/기능` 이 같아야 한다."""
    return "/".join(_norm(p) for p in path.split("/"))


def upgrade() -> None:
    _create_tables()
    _add_fact_columns()

    conn = op.get_bind()
    _move_values(conn)
    _build_nodes(conn)
    _finish_fact_columns()


# ─────────────────────────────────────────────────────────────────
# 표
# ─────────────────────────────────────────────────────────────────


def _create_tables() -> None:
    op.create_table(
        "wiki_node",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent", sa.Text(), nullable=False, server_default=""),
        sa.Column("norm_path", sa.Text(), nullable=False),
        sa.Column(
            "first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "path", name="uq_wiki_node_company_path"),
    )
    op.create_index("ix_wiki_node_company_id", "wiki_node", ["company_id"])
    op.create_index("ix_wiki_node_category", "wiki_node", ["category"])
    op.create_index("ix_wiki_node_norm_path", "wiki_node", ["norm_path"])
    op.create_index("ix_wiki_node_parent", "wiki_node", ["company_id", "parent"])

    op.create_table(
        "company_value",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("key", sa.String(32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("qualifier", sa.Text(), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False, server_default="document"),
        sa.Column("extractor", sa.String(32), nullable=False),
        sa.Column(
            "first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "dedupe_key", name="uq_company_value_key"),
    )
    op.create_index("ix_company_value_company_id", "company_value", ["company_id"])
    op.create_index("ix_company_value_key", "company_value", ["company_id", "key"])

    op.create_table(
        "value_evidence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("value_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), nullable=False),
        sa.Column("user_file_id", sa.BigInteger(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["value_id"], ["company_value.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunk.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_file_id"], ["user_file.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("value_id", "chunk_id", name="uq_value_evidence_value_chunk"),
    )
    op.create_index("ix_value_evidence_value_id", "value_evidence", ["value_id"])
    op.create_index("ix_value_evidence_company", "value_evidence", ["company_id"])


def _add_fact_columns() -> None:
    """**nullable 로 먼저 넣는다.** 데이터를 옮긴 뒤에 조인다."""
    op.add_column("wiki_fact", sa.Column("node_id", sa.BigInteger(), nullable=True))
    op.add_column("wiki_fact", sa.Column("kind", sa.String(16), nullable=True))
    op.add_column("wiki_fact", sa.Column("key", sa.Text(), nullable=True))
    op.add_column("wiki_fact", sa.Column("norm_key", sa.Text(), nullable=True))


# ─────────────────────────────────────────────────────────────────
# 데이터
# ─────────────────────────────────────────────────────────────────


def _move_values(conn) -> None:  # noqa: ANN001
    """`place_kind='value'` 를 `company_value` 로. **근거를 먼저 옮기고 지운다.**

    `place` 가 그대로 `key` 다 — 옛 슬롯 이름 열넷이 곧 트랙 B 의 고정 열넷이다.
    """
    conn.execute(
        sa.text("""
        INSERT INTO company_value
            (company_id, key, value, qualifier, as_of, status, dedupe_key,
             source_type, extractor, first_seen_at, updated_at)
        SELECT company_id, place, COALESCE(value, ''), qualifier, as_of,
               COALESCE(status, 'current'), dedupe_key,
               source_type, extractor, first_seen_at, updated_at
        FROM wiki_fact
        WHERE place_kind = 'value'
        """)
    )
    #: 근거를 옮긴다. `dedupe_key` 가 회사 안에서 유니크라 그걸로 잇는다
    conn.execute(
        sa.text("""
        INSERT INTO value_evidence (company_id, value_id, chunk_id, user_file_id, quote)
        SELECT e.company_id, cv.id, e.chunk_id, e.user_file_id, e.quote
        FROM wiki_evidence e
        JOIN wiki_fact f ON f.id = e.fact_id AND f.place_kind = 'value'
        JOIN company_value cv
          ON cv.company_id = f.company_id AND cv.dedupe_key = f.dedupe_key
        """)
    )
    #: 옮겼으니 지운다. `wiki_evidence` 는 CASCADE 로 따라 지워진다
    conn.execute(sa.text("DELETE FROM wiki_fact WHERE place_kind = 'value'"))


def _build_nodes(conn) -> None:
    """남은 사실(event · uncategorized)에 노드를 만들어 붙인다."""
    rows = conn.execute(
        sa.text("SELECT id, company_id, place_kind, topic, dedupe_key, text FROM wiki_fact")
    ).all()

    made: dict[tuple[str, str], int] = {}

    for fid, company, kind, topic, dedupe, text in rows:
        path = EVENT_PATH.get(topic or "") if kind == "event" else None
        path = path or FALLBACK

        node_id = made.get((company, path))
        if node_id is None:
            node_id = _ensure_node(conn, company, path)
            made[(company, path)] = node_id

        #: 옛 `dedupe_key` 는 `event|<orbit>|<fact_key 또는 정규화 문장>` 이다.
        #: 셋째 조각이 그대로 새 `key` 가 된다 — **라벨이자 열쇠다**(ADR-0056 결정 3).
        parts = (dedupe or "").split("|", 2)
        key = (parts[2] if len(parts) == 3 else "") or (text or "")[:80] or "사실"

        conn.execute(
            sa.text("""
            UPDATE wiki_fact
               SET node_id = :n, kind = 'event', key = :k, norm_key = :nk,
                   dedupe_key = :d
             WHERE id = :i
            """),
            {"n": node_id, "k": key, "nk": _norm(key), "d": f"event|{path}|{key}", "i": fid},
        )


def _ensure_node(conn, company: str, path: str) -> int:  # noqa: ANN001
    """경로 하나와 **그 조상 전부**를 만든다. 뼈대가 없으면 트리가 안 선다."""
    parts = path.split("/")
    node_id = 0
    for depth in range(1, len(parts) + 1):
        cur = "/".join(parts[:depth])
        parent = "/".join(parts[: depth - 1])
        got = conn.execute(
            sa.text("SELECT id FROM wiki_node WHERE company_id = :c AND path = :p"),
            {"c": company, "p": cur},
        ).scalar()
        if got is None:
            got = conn.execute(
                sa.text("""
                INSERT INTO wiki_node (company_id, path, category, name, parent, norm_path)
                VALUES (:c, :p, :cat, :n, :par, :np) RETURNING id
                """),
                {
                    "c": company,
                    "p": cur,
                    "cat": parts[0],
                    "n": parts[depth - 1],
                    "par": parent,
                    "np": _norm_path(cur),
                },
            ).scalar()
        node_id = int(got)
    return node_id


def _finish_fact_columns() -> None:
    """옮겼으니 조이고 옛 컬럼을 뺀다."""
    op.alter_column("wiki_fact", "node_id", nullable=False)
    op.alter_column("wiki_fact", "kind", nullable=False)
    op.alter_column("wiki_fact", "key", nullable=False)
    op.alter_column("wiki_fact", "norm_key", nullable=False)
    op.create_foreign_key(
        "fk_wiki_fact_node", "wiki_fact", "wiki_node", ["node_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_wiki_fact_node", "wiki_fact", ["node_id"])

    op.drop_index("ix_wiki_fact_place", table_name="wiki_fact")
    for col in ("place_kind", "place", "topic", "slot_key"):
        op.drop_column("wiki_fact", col)


def downgrade() -> None:
    """**되돌리지 않는다.** 동적 노드 경로를 옛 topic 스물셋으로 되접을 방법이 없다 —
    `Custom/특허/등록-10-2025-0114882` 가 어느 topic 이었는지 복원할 수 없다."""
    raise NotImplementedError("ADR-0056 은 되돌리지 않는다. 백업에서 복구한다")
