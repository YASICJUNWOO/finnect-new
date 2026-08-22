"""자리표를 고정하고 key 를 뺀다 — ADR-0058

위키 자리가 **기획 문서 `20_지식베이스구조.md` §2 의 마흔여섯 고정**이 되고
(`wiki/spots.py`), 사실에 붙던 `key` 가 없어진다
([ADR-0058](../../docs/adr/0058-자리표를-기획-트리로-고정하고-key-를-없앤다.md)).

스키마에서 하는 일은 셋이다.

1. `wiki_fact.grade` · `source` 추가 — 기획 §5 의 자료 등급을 추출기가 매긴다
2. `wiki_fact.key` · `norm_key` 를 nullable 로 — **지우지 않는다**
3. 끝. **`dedupe_key` 는 안 건드린다** (아래)

## `key` 컬럼을 지우지 않는 이유

되돌릴 수 있게 두는 값이 마이그레이션 하나뿐이다. 지우면 `downgrade` 가 컬럼을 다시
만들어도 **값이 안 살아난다** — 사람이 읽는 라벨이라 재계산할 방법이 없다. 읽는
코드는 하나도 안 남았고(`grep 'WikiFact.key'` 가 0건) 새 행은 NULL 로 앉는다.

## `dedupe_key` 를 다시 쓰지 않는 이유

키 모양이 바뀌었다.

    옛  event|{경로}|{key}|{시점}      ·  value|{경로}|{key}|{한정어}|{시점}|{값}
    새  {kind}|{경로}|{한정어}|{시점}|{값 또는 문장}

SQL 로 다시 쓸 수는 있다. **하지만 옛 키가 `key` 로 갈라 두었던 행들이 새 모양에서
같은 키가 될 수 있고**, 그러면 `(company_id, dedupe_key)` 유니크에 걸려 마이그레이션
전체가 죽는다. 피하려면 겹치는 행을 지워야 하는데 그건 사실을 버리는 일이다.

안 써도 되는 이유는 **옛 행이 새 행과 부딪칠 자리가 없어서**다. `--build` 는 `chunked`
파일만 읽으므로(plan/12 T-0092) 이미 `done` 인 파일의 사실은 다시 만들어지지 않고,
`--rebuild` 는 `clear()` 가 전부 지운 뒤 새로 세운다. **옛 키는 옛 행에만 남고 조용히
는 일이 없다.**

## 옛 노드 경로는 그대로 둔다

`wiki_node.path` 에 자리표 밖 경로가 남아 있다(`Product/기능` · `Company/지역관계`).
**옮기지 않는다** — 옛 경로 상당수가 LLM 이 지은 것이라 어느 자리로 갈지 정할 표가
우리에게 없고, 지어서 옮기면 사실이 엉뚱한 데 앉는다.

그대로 둬도 화면은 깨지지 않는다. `read_nodes` 가 폴더(`category`)로 묶어서 돌려주고
그 열은 안 바뀌었다 — 옛 자리는 제 폴더 밑에 그대로 서고, 새로 올린 파일의 사실만
표 안으로 들어온다. **정리하려면 `--rebuild` 다.**

**배포 DB 에도 돌려야 한다**([deploy.md](../../docs/deploy.md) §2).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d9a4e17c6b52"
down_revision = "b7c31f0a92e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    #: 기획 §5 의 자료 등급. `1차` · `2차` · `가정` 셋만 앉는다 —
    #: `실측` 은 `source_type` 이, `미정` 은 빈 자리가 말한다
    op.add_column("wiki_fact", sa.Column("grade", sa.String(length=8), nullable=True))
    #: `2차` 일 때 문서가 밝힌 기관·자료 이름
    op.add_column("wiki_fact", sa.Column("source", sa.Text(), nullable=True))

    #: **값을 남긴 채 내린다.** 새 행이 NULL 로 앉을 수 있게만 한다
    op.alter_column("wiki_fact", "key", existing_type=sa.Text(), nullable=True)
    op.alter_column("wiki_fact", "norm_key", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    #: NOT NULL 로 되돌리려면 새 행의 NULL 을 채워야 한다. **빈 문자열이다** —
    #: 라벨을 지어내면 화면에 그 글자가 뜨고, 그건 아무도 쓴 적 없는 말이 된다
    op.execute("UPDATE wiki_fact SET key = '' WHERE key IS NULL")
    op.execute("UPDATE wiki_fact SET norm_key = '' WHERE norm_key IS NULL")
    op.alter_column("wiki_fact", "norm_key", existing_type=sa.Text(), nullable=False)
    op.alter_column("wiki_fact", "key", existing_type=sa.Text(), nullable=False)

    op.drop_column("wiki_fact", "source")
    op.drop_column("wiki_fact", "grade")
