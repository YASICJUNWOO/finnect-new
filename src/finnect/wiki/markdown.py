"""사실 하나를 마크다운 조각으로 — **뷰다. 저장하지 않는다**(plan/12 `구상도와의 차이`).

구상도는 ⑥에서 마크다운을 만들고 ⑦에서 SQL 로도 저장한다. **우리는 저장하지 않는다.**
`SPEC.md` §2-1 이 "소스가 갈라지면 불일치가 생긴다"고 적었고, 사실이 `wiki_fact` 에
있는데 같은 내용을 마크다운으로도 들고 있으면 둘 중 하나가 먼저 낡는다.

그래서 이 파일은 **읽을 때마다 다시 만든다.** 대가는 매번 조인 몇 번이고, 얻는 것은
"화면에 보이는 글자가 DB 와 다를 수 없다"는 성질이다.

## 값 블록이 여기서 나갔다

2026-08-22 트랙이 둘로 갈리면서(ADR-0056) 정형 값이 `company_value` 로 옮겨 갔다.
여기 남은 것은 **트랙 A 의 사실 블록과 근거 목록**이다.

## 장을 만드는 것은 여기가 아니다

2026-08-22 까지 이 모듈이 **궤도 자리 한 장**을 통째로 만들었다(`render(node)`). 화면이
기획 폴더 트리로 바뀌면서 그 장이 없어졌고(ADR-0052), 여기 남은 것은 **어느 뷰든 쓰는
조각들**이다 — 값 블록 · 사실 블록 · 근거 파일 목록.
장을 조립하는 것은 `export.py` 하나다. **뷰가 둘이던 시절의 잔재를 남기지 않는다.**

## 시각이 안 들어간다

`generated: 2026-08-18` 같은 것을 넣지 않는다. 넣으면 같은 DB 에서 만든 마크다운이
매일 달라져 **바이트로 비교할 수 없다.** 테스트가 그걸 본다.

프론트매터의 `updated_at` 은 다른 것이다 — 그것은 `wiki_fact.updated_at` 이라 **DB 가
같으면 같다.** 만든 시각이 아니라 사실이 바뀐 시각이다.

## `SPEC.md` F1-3 의 한 장이 이 모양이다

머리말 · 본문 · **자기 근거가 되는 원문 조각** 셋이다. 근거는 `파일명 N쪽` 까지 적는다 —
"출처는 문자열이 아니라 연결이다"(F1-3)라고 한 그 연결의 마크다운 표현이다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

#: 충돌한 값 앞에 붙는 말. **이모지를 쓰지 않는다** — 옵시디언과 터미널에서 폭이 갈린다.
#: 값은 이제 트랙 B(`company_value`)에 살고 회사 정보 화면이 이 말을 쓴다.
CONFLICT_NOTE = "> 값이 갈려요. 어느 쪽이 맞는지 정해야 해요 — 둘 다 두었어요."


@dataclass(frozen=True, slots=True)
class Evidence:
    """근거 하나. `파일명 3쪽`.

    `sha256` 을 드는 이유는 기획 문서 §5 의 `source_path` 때문이다 — 원본은 콘텐츠
    주소로 누워 있어서(`ADR-0029`) 파일명만으로는 위치를 되찾을 수 없다. **비어 있어도
    된다** — 프론트매터가 그 줄을 건너뛴다.
    """

    filename: str
    page: int | None
    quote: str
    sha256: str = ""

    def __str__(self) -> str:
        return f"{self.filename}{f' {self.page}쪽' if self.page else ''}"


@dataclass(frozen=True, slots=True)
class Statement:
    """노드에 앉은 사실 하나.

    `topic` 은 옛 이름이고 지금 담기는 것은 **`key`** 다 — 라벨이자 병합 열쇠(ADR-0056
    결정 3). 이름을 안 바꾼 이유는 `draft/` 와 `match/` 가 이 필드를 읽고 있어서다.
    """

    text: str
    #: 노드 안에서 이 사실을 부르는 이름. **`WikiFact.key` 가 여기 온다**
    topic: str
    evidence: tuple[Evidence, ...]
    source_type: str = "document"
    updated_at: dt.date | None = None


def render_facts(items: tuple[Statement, ...] | list[Statement]) -> list[str]:
    """event topic. **한 사실에 근거가 여럿이다** — 문서 넷이 같은 말을 하면 줄 하나에 근거 넷."""
    out: list[str] = []
    for s in items:
        out += [s.text, ""]
        where = " · ".join(str(e) for e in s.evidence)
        out.append(f"> 근거 {len(s.evidence)} — {where}")
        out.append("")
    return out


def render_sources(evidence: list[Evidence]) -> list[str]:
    """이 장을 만든 파일들. **어느 파일을 지우면 무엇이 사라지는지** 보이는 자리다."""
    files = sorted({e.filename for e in evidence})
    return ["## 근거 파일", "", *[f"- {f}" for f in files], ""]
