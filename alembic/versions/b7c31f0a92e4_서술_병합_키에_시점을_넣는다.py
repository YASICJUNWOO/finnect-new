"""서술 병합 키에 시점을 넣는다 — ADR-0057

[ADR-0057](../../docs/adr/0057-서술을-쌓고-시점을-남긴다.md) 이 EVENT 의 병합 키를
바꿨다.

    옛  event|{경로}|{key}
    새  event|{경로}|{key}|{as_of}

**따로 가면 안 된다.** 유니크 키가 `(company_id, dedupe_key)` 라, 코드만 바뀌고 행이
옛 키를 들고 있으면 다음 빌드에서 **같은 사실이 새 행으로 앉아 조용히 는다.** `ADR-0049`
때 `place_kind` 와 `dedupe_key` 접두사를 한 마이그레이션에 넣은 것과 같은 이유다.

## 붙이는 값이 항상 빈 문자열이다

기존 EVENT 행은 `as_of` 가 **전부 NULL** 이다 — 코드가 `as_of=fact.as_of if is_value
else None` 로 저장 직전에 버리고 있었고, 그것이 ADR-0057 이 고친 결함이다. 그래도
`as_of` 를 읽어서 붙이는 이유는 **규칙을 그대로 적기 위해서**다. 상수 `'|'` 를 붙이면
이 파일이 「왜 파이프 하나인가」를 설명하지 못하고, 나중에 누가 읽을 때 옛 키 모양을
역산해야 한다.

## VALUE 는 안 건드린다

값 쪽 키(`value|{경로}|{key}|{한정어}|{시점}|{값}`)는 이미 시점을 들고 있어서 안 바뀐다.

## 되돌리기

시점이 붙은 뒤 새로 선 행은 `as_of` 가 찰 수 있어서 **되돌리면 그 행의 키가 옛 모양과
안 맞는다.** 그래서 `downgrade` 는 시점이 없는 행만 되돌리고, 시점이 있는 행은 그대로
둔다 — 옛 코드에서는 어차피 만들어질 수 없던 행이라 **되돌린 척하는 것보다 남기는 것이
정직하다.**
"""

from __future__ import annotations

from alembic import op

revision = "b7c31f0a92e4"
down_revision = "f4b8c02e91d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE wiki_fact
           SET dedupe_key = dedupe_key || '|' || COALESCE(CAST(as_of AS VARCHAR), '')
         WHERE kind = 'event'
        """
    )


def downgrade() -> None:
    #: 시점이 없는 행만 되돌린다. 있는 행은 옛 코드가 만들 수 없던 것이라 그대로 둔다
    op.execute(
        """
        UPDATE wiki_fact
           SET dedupe_key = LEFT(dedupe_key, LENGTH(dedupe_key) - 1)
         WHERE kind = 'event'
           AND as_of IS NULL
           AND dedupe_key LIKE '%|'
        """
    )
