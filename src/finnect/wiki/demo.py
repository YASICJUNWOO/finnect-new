"""시연용 위키 스냅샷 — 한 번 세운 것을 떠 두고 그대로 앉힌다.

**제품 기능이 아니다.** `api/service.DEMO_PICKS`(고정 추천)·`web/components/DemoReply`
(5초 집필)와 같은 자리에 있고, 시연이 끝나면 이 파일과 `settings.demo_snapshot` 과
부르는 자리 하나를 같이 지운다.

## 왜 필요한가

나린데이터 일곱 건으로 위키를 세우는 데 **241초**가 걸린다(2026-08-23 실측 · OCR 두 장
+ LLM 파일당 2회). 시연에서 그만큼 기다릴 수 없다. 그렇다고 미리 세워 두면 **시작할 때
이미 노드가 서 있어서** 「파일을 던지면 위키가 생긴다」를 못 보여 준다. 그래서 미리 세운
것을 떠 두고, 던지는 순간 앉힌다.

## 화면 연출과 다른 일이다

`web/components/demoProgress.ts` 는 올리기 화면(S1)의 칸 다섯을 5초에 걸쳐 채우는 것이고
**DB 를 아예 안 본다.** 이 파일은 위키 화면(S7)과 회사 정보가 읽을 **진짜 행**을 만든다.
둘이 같이 있어야 「올렸다 → 위키가 섰다」가 이어진다.

## ID 를 그대로 쓴다

행끼리 참조가 있어서(`wiki_evidence.fact_id` 등) ID 를 새로 발급하면 매핑 표를 들고
다녀야 한다. 앉히기 전에 그 회사 행을 지우므로 자기 자신과는 안 겹치고, **시연 DB 에는
회사가 하나뿐이라** 남과 겹칠 자리도 없다. 대신 앉힌 뒤 시퀀스를 올린다 — 안 올리면
다음 INSERT 가 이미 쓰인 ID 를 발급해 유니크 위반이 난다.

**원본 파일은 안 뜬다.** `data/user-files/` 의 바이트는 `--rechunk`·`--rebuild` 만 읽고
화면은 청크(DB)만 본다. 넣으면 스냅샷이 1.2MB 커지는데 시연에서 쓰는 곳이 없다.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from sqlalchemy import Date, DateTime, delete, func, insert, select, text
from sqlalchemy.orm import Session

from finnect.models import (
    Chunk,
    CompanyValue,
    UserFile,
    ValueEvidence,
    WikiEvidence,
    WikiFact,
    WikiNode,
)

#: 앉히는 순서다. **바꾸면 외래 키가 깨진다** — `chunk` 는 `user_file` 을, `wiki_fact` 는
#: `wiki_node` 를, 근거 둘은 그 앞의 것을 전부 참조한다. 지울 때는 이 순서를 뒤집는다.
TABLES = (UserFile, WikiNode, CompanyValue, Chunk, WikiFact, WikiEvidence, ValueEvidence)


class SnapshotError(RuntimeError):
    """스냅샷이 없거나 읽을 수 없다. **조용히 빈 위키로 넘어가지 않는다** — 그러면
    시연에서 파일을 던졌는데 노드가 0인 채로 끝나고 이유가 안 남는다."""


def _dump(value: Any) -> Any:
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    return value


def _load(column: Any, value: Any) -> Any:
    """JSON 이 문자열로 만든 것을 컬럼 타입대로 되돌린다. **`DateTime` 을 먼저 본다** —
    `Date` 가 `DateTime` 의 상위 타입이라 순서를 바꾸면 시각이 날짜로 잘린다."""
    if value is None:
        return None
    if isinstance(column.type, DateTime):
        return dt.datetime.fromisoformat(value)
    if isinstance(column.type, Date):
        return dt.date.fromisoformat(value)
    return value


def take(session: Session, company_id: str) -> dict[str, list[dict[str, Any]]]:
    """세워진 위키를 통째로 뜬다. 표 이름 → 행 목록이다."""
    out: dict[str, list[dict[str, Any]]] = {}
    for model in TABLES:
        rows = session.scalars(select(model).where(model.company_id == company_id)).all()
        out[model.__tablename__] = [
            {c.name: _dump(getattr(row, c.name)) for c in model.__table__.columns}
            for row in rows
        ]
    return out


def clear(session: Session, company_id: str) -> None:
    """그 회사 행을 전부 지운다. **앉히기 전에 부른다** — 안 지우면 같은 ID 가 두 번
    들어가 유니크 위반이 난다. 캐스케이드에 맡기지 않고 역순으로 직접 지우는 이유는
    `wiki/service.purge` 와 같다(SQLite 는 FK 가 기본으로 꺼져 있다)."""
    for model in reversed(TABLES):
        session.execute(delete(model).where(model.company_id == company_id))


def put(session: Session, company_id: str, snap: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """스냅샷을 앉힌다. 돌려주는 것은 표마다 넣은 행 수다.

    **`company_id` 를 인자 것으로 덮어쓴다.** 스냅샷은 뜬 회사의 ID 를 들고 있는데, 앉는
    자리는 요청이 정한다 — 둘이 다르면 행은 들어가는데 그 회사 화면에서는 안 보인다.
    """
    clear(session, company_id)

    counts: dict[str, int] = {}
    for model in TABLES:
        rows = snap.get(model.__tablename__) or []
        counts[model.__tablename__] = len(rows)
        if not rows:
            continue
        columns = {c.name: c for c in model.__table__.columns}
        session.execute(
            insert(model.__table__),
            [
                {k: _load(columns[k], v) for k, v in row.items() if k in columns}
                | {"company_id": company_id}
                for row in rows
            ],
        )

    _bump_sequences(session)
    return counts


def _bump_sequences(session: Session) -> None:
    """ID 를 그대로 넣었으니 시퀀스를 그 위로 올린다.

    **Postgres 에서만 한다.** SQLite 는 `AUTOINCREMENT` 가 최대값 다음을 쓰므로 할 일이
    없고, `pg_get_serial_sequence` 를 부르면 거기서 죽는다.
    """
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    for model in TABLES:
        table = model.__tablename__
        top = session.scalar(select(func.max(model.id))) or 0
        session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence(:t, 'id'), :v)"
                # 표가 비어 있으면 1 로 두되 아직 안 쓴 값이라고 알린다. `setval(…, 1,
                # false)` 가 그 뜻이고, 0 을 넣으면 Postgres 가 범위 밖이라고 거절한다.
                " WHERE pg_get_serial_sequence(:t, 'id') IS NOT NULL"
            ).bindparams(t=table, v=max(top, 1))
        )


def read(path: Path) -> dict[str, list[dict[str, Any]]]:
    """스냅샷 파일을 읽는다. **없으면 예외다** — 시연 설정이 켜져 있는데 파일이 없으면
    그것은 설정 실수이고, 조용히 넘어가면 화면이 빈 위키를 보여 준다."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise SnapshotError(f"시연 스냅샷이 없어요: {path}") from e
    except json.JSONDecodeError as e:
        raise SnapshotError(f"시연 스냅샷을 못 읽었어요: {path} — {e}") from e
    if not isinstance(data, dict):
        raise SnapshotError(f"시연 스냅샷 모양이 이상해요: {path}")
    return data


def write(path: Path, snap: dict[str, list[dict[str, Any]]]) -> int:
    """스냅샷을 파일로 쓴다. 돌려주는 것은 바이트 수다.

    **시각을 따로 안 넣는다.** 위키 마크다운을 저장하지 않는 것과 같은 이유로, 같은 DB 에서
    두 번 뜬 결과가 바이트로 같아야 한다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(body + "\n", encoding="utf-8")
    return len(body) + 1
