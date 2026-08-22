"""place_kind 를 value·event 로 — ADR-0049

`slot`·`node` 는 ADR-0032 의 어휘였다. ADR-0048 이 층을 셋(`sector`·`orbit`·`topic`)으로
줄이면서 topic 의 타입을 `value`·`event` 로 정했는데, 결정 3 이 저장을 안 바꾸기로 해서
**DB 만 옛말을 들고 있었다.** ADR-0049 가 그 결정을 대체한다.

**세 자리를 한 번에 옮긴다.** 셋 다 저장값이라 따로 가면 그 사이에 세운 위키가 깨진다.

    wiki_fact.place_kind    'slot' → 'value'   · 'node' → 'event'
    wiki_fact.dedupe_key    'slot|…' → 'value|…' · 'node|…' → 'event|…'
    item_need.place_kind    같은 매핑

**`dedupe_key` 를 같이 안 옮기면 조용히 중복이 생긴다.** 유니크 키가
`(company_id, dedupe_key)` 라, 접두사만 코드에서 바뀌면 다음 빌드가 같은 사실을
**새 행으로** 앉힌다 — 에러가 아니라 사실 수가 늘어난다.

접두사 치환은 1:1 이라 유니크 제약을 새로 어길 수 없다. `'slot|'` 과 `'node|'` 는
서로 다른 값으로 가고, 이미 `'value|'`·`'event|'` 인 행은 없다.

`uncategorized` 는 안 바뀐다 — 그 이름은 ADR-0048 이 손대지 않았다.

Revision ID: a1e0c7d4f2b9
Revises: b3b8cbc5cce8
Create Date: 2026-08-22

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1e0c7d4f2b9"
down_revision: str | None = "b3b8cbc5cce8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: (옛 이름, 새 이름). 되돌릴 때 뒤집어 쓴다
PAIRS = (("slot", "value"), ("node", "event"))


def upgrade() -> None:
    _swap(PAIRS)


def downgrade() -> None:
    _swap(tuple((new, old) for old, new in PAIRS))


def _swap(pairs: tuple[tuple[str, str], ...]) -> None:
    """**순서가 상관없다** — `slot`↔`value` 와 `node`↔`event` 가 서로 겹치지 않는다."""
    for old, new in pairs:
        op.execute(
            f"UPDATE wiki_fact SET place_kind = '{new}' WHERE place_kind = '{old}'"  # noqa: S608
        )
        op.execute(
            f"UPDATE item_need SET place_kind = '{new}' WHERE place_kind = '{old}'"  # noqa: S608
        )
        # **접두사만 바꾼다.** 뒤의 필드에 `|` 가 또 있어도 안전하다 — 왼쪽 끝만 자른다
        op.execute(
            "UPDATE wiki_fact "
            f"SET dedupe_key = '{new}|' || substring(dedupe_key from {len(old) + 2}) "
            f"WHERE dedupe_key LIKE '{old}|%'"  # noqa: S608
        )
