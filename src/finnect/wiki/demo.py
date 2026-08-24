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

`web/components/Upload.tsx` 의 `frame()` 은 올리기 화면(S1)의 칸 다섯을 5초에 걸쳐 채우는
것이고 **DB 를 아예 안 본다.** 이 파일은 위키 화면(S7)과 회사 정보가 읽을 **진짜 행**을 만든다.
둘이 같이 있어야 「올렸다 → 위키가 섰다」가 이어진다.

## ID 를 새로 발급한다

**2026-08-24 까지 뜬 ID 를 그대로 앉혔고, 그 근거가 「시연 DB 에는 회사가 하나뿐」이었다.**
입장 게이트가 서면서(ADR-0066) 그 전제가 깨졌다 — 사람마다 `company_id` 가 따로 나오는데
`clear()` 는 앉힐 회사 것만 지우므로 **둘째 사람의 올리기가 첫째 사람의 행과 같은 ID 로
부딪친다**(`duplicate key … user_file_pkey`). 스냅샷을 뜬 회사가 같은 DB 에 남아 있으면
첫 사람부터 그렇다.

그래서 ID 를 버리고 표가 발급하게 둔다. 행끼리 참조(`wiki_evidence.fact_id` 등)는 옛→새
표로 다시 잇고, **그 표를 손으로 안 적는다**(`_links` 가 모델에서 뽑는다) — 적어 두면 FK 가
하나 늘어난 날 그 컬럼만 옛 ID 를 들고 남고, 그때 터지는 것이 아니라 **남의 청크를 근거로
든 사실**이 조용히 선다. `TABLES` 순서가 부모를 먼저 넣으므로 자식이 물려받을 표는 그때
이미 서 있다.

**시퀀스를 안 만진다.** 발급을 표에 맡겼으니 올릴 것이 없다 — `setval` 이 없어지면서
「롤백이 안 되는 쓰기」도 같이 없어졌다.

**원본 파일은 안 뜬다.** `data/user-files/` 의 바이트는 `--rechunk`·`--rebuild` 만 읽고
화면은 청크(DB)만 본다. 넣으면 스냅샷이 1.2MB 커지는데 시연에서 쓰는 곳이 없다.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from sqlalchemy import Date, DateTime, delete, insert, select
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
#: **ID 를 다시 잇는 것도 이 순서에 기댄다** — 자식이 앉는 시점에 부모의 옛→새 표가
#: 이미 서 있어야 한다.
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


def _links(model: Any) -> list[tuple[str, str]]:
    """다시 이어야 하는 자리 — `(컬럼 이름, 가리키는 표)`. **모델에서 뽑는다.**"""
    return [
        (column.name, fk.column.table.name)
        for column in model.__table__.columns
        for fk in column.foreign_keys
    ]


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
    """그 회사 행을 전부 지운다. **앉히기 전에 부른다** — 안 지우면 같은 파일이 두 벌
    쌓여 `(company_id, sha256)` 유니크 위반이 난다. 캐스케이드에 맡기지 않고 역순으로
    직접 지우는 이유는 `wiki/service.purge` 와 같다(SQLite 는 FK 가 기본으로 꺼져 있다)."""
    for model in reversed(TABLES):
        session.execute(delete(model).where(model.company_id == company_id))


def put(session: Session, company_id: str, snap: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """스냅샷을 앉힌다. 돌려주는 것은 표마다 넣은 행 수다.

    **`company_id` 를 인자 것으로 덮어쓴다.** 스냅샷은 뜬 회사의 ID 를 들고 있는데, 앉는
    자리는 요청이 정한다 — 둘이 다르면 행은 들어가는데 그 회사 화면에서는 안 보인다.

    **`id` 는 안 싣는다.** 표가 발급한 것을 옛 값과 짝지어 두고 뒤 표의 참조를 그것으로
    바꾼다 — 이유는 파일 머리의 「ID 를 새로 발급한다」에 있다.
    """
    clear(session, company_id)

    #: 표 이름 → 옛 ID → 새 ID
    remap: dict[str, dict[int, int]] = {}
    counts: dict[str, int] = {}

    for model in TABLES:
        table = model.__tablename__
        rows = snap.get(table) or []
        counts[table] = len(rows)
        remap[table] = {}

        columns = {c.name: c for c in model.__table__.columns}
        links = _links(model)

        for row in rows:
            body = {
                name: _load(columns[name], value)
                for name, value in row.items()
                if name in columns and name != "id"
            }
            body["company_id"] = company_id
            for name, target in links:
                old = body.get(name)
                if old is None:
                    continue
                if old not in remap[target]:
                    # **여기서 멈춘다.** 그냥 두면 FK 가 없는 SQLite 에서는 남의 행을
                    # 가리키는 근거가 조용히 서고, Postgres 에서는 이유가 안 남는다.
                    raise SnapshotError(
                        f"스냅샷이 안 맞아요: {table}.{name}={old} 가 가리키는 "
                        f"{target} 행이 스냅샷에 없어요"
                    )
                body[name] = remap[target][old]

            new_id = session.execute(
                insert(model.__table__).values(**body).returning(model.__table__.c.id)
            ).scalar_one()
            remap[table][row["id"]] = new_id

    return counts


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
