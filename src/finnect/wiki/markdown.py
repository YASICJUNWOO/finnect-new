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

    **`key` 가 이 사실의 이름이다**(ADR-0056 결정 3) — 라벨이자 병합 열쇠다. 2026-08-22
    까지 이 필드가 `topic` 이었고 「`draft/` 와 `match/` 가 읽어서 못 바꾼다」고 적혀
    있었는데, **그 둘은 `WikiFact` 를 직접 읽지 이 모양을 안 쓴다.** 유일한 소비자가
    `api/wiki_service.py` 하나라 이름을 DB 와 맞췄다.
    """

    text: str
    #: 노드 안에서 이 사실을 부르는 이름. **`WikiFact.key` 가 여기 온다**
    key: str
    evidence: tuple[Evidence, ...]
    source_type: str = "document"
    updated_at: dt.date | None = None

    # --- kind == "value" 일 때만 찬다 ---
    #: `value` 또는 `event`. **병합 규칙을 이게 정한다**(`merge.node_key`)
    kind: str = "event"
    #: **정규화된 값이다**(`120000000`). 병합의 재료라 읽는 쪽이 고쳐 쓰지 않는다
    value: str | None = None
    #: 같은 key 안의 종류. `시드` · `예비창업패키지`
    qualifier: str | None = None
    as_of: dt.date | None = None


def group(items: tuple[Statement, ...] | list[Statement]) -> list[tuple[str, list[Statement]]]:
    """`key` 로 묶고 묶음 안에서 **시점 내림차순**으로 세운다(ADR-0057 결정 3·4).

    **이력은 상태 컬럼이 아니라 이 정렬이 만든다.** EVENT 에는 `status` 가 없다 — 옛
    서술은 밀려난 것이 아니라 그때의 기록이라 흐리지도 지우지도 않고 아래에 둔다.

    시점이 없는 것은 뒤로 보낸다. **언제 것인지 모르는 서술이 아는 것을 밀어내면 안
    된다** — `merge` 가 시점 없는 값을 가장 오래된 것으로 놓는 것과 같은 규칙이다.

    key 의 순서는 **처음 나온 순서**다. 정렬하지 않는 이유는 그것이 곧 추출 순서이고,
    가나다순으로 다시 세우면 문서가 말한 순서가 사라져서다.
    """
    by_key: dict[str, list[Statement]] = {}
    for s in items:
        by_key.setdefault(s.key, []).append(s)

    out = []
    for key, mine in by_key.items():
        dated = sorted((s for s in mine if s.as_of), key=lambda s: s.as_of, reverse=True)  # type: ignore[arg-type,return-value]
        out.append((key, [*dated, *(s for s in mine if not s.as_of)]))
    return out


def _meta(s: Statement) -> str:
    """사실 한 줄의 머리. `**300000000** — 시드 · 2025-09-30 기준`. 없으면 빈 문자열.

    **값과 시점이 절 제목이 아니라 여기 온다.** 한 절 안에 사실이 여럿이라(이력·충돌)
    제목에 넣으면 둘 중 하나만 실린다.

    **단위를 안 붙인다.** `profile.display()` 의 단위표는 매칭 정보 열넷의 것이고 트랙 A
    의 key 는 자유 문자열이라 거기 없다 — **아는 척 `원`·`명` 을 붙이면 값이 거짓이 된다.**
    """
    bits = []
    if s.value:
        bits.append(f"**{s.value}**" + (f" — {s.qualifier}" if s.qualifier else ""))
    elif s.qualifier:
        bits.append(s.qualifier)
    if s.as_of:
        bits.append(f"{s.as_of.isoformat()} 기준")
    #: 값이 없으면 시점만 남아 문장처럼 보이므로 기울인다
    line = " · ".join(bits)
    return line if s.value else (f"*{line}*" if line else "")


def render_facts(items: tuple[Statement, ...] | list[Statement]) -> list[str]:
    """`key` 마다 한 절, 그 안에 사실 여럿(ADR-0057 결정 4).

    2026-08-22 까지 이 함수가 `text` 와 근거 줄만 냈다. `key` 가 라벨이자 병합 열쇠인데
    **찍는 자리가 어디에도 없어서** 한 장에 사실 셋이 이름 없는 문단 셋으로 섰다 —
    프롬프트는 「같은 key 면 같은 사실」이라고 시켜 놓고 그 key 를 화면·마크다운·API
    어디에도 안 내보냈다. 값형의 `value`·`as_of` 도 같이 떨어지고 있었다.

    **한 절 안에 사실이 여럿인 것이 정상이다.** EVENT 는 시점마다 쌓이고(이력), VALUE 는
    같은 자리에 값이 둘이면 그것이 곧 충돌이다 — **어느 쪽도 접지 않는다.** 접으면 하나가
    조용히 사라지고, 그것이 [ADR-0057](../../../docs/adr/0057-서술을-쌓고-시점을-남긴다.md)
    이 고친 병이다.

    **한 사실에 근거가 여럿이다** — 문서 넷이 같은 말을 하면 줄 하나에 근거 넷.
    """
    out: list[str] = []
    for key, mine in group(items):
        out += [f"## {key}", ""]
        for s in mine:
            if meta := _meta(s):
                out += [meta, ""]
            if s.text:
                out += [s.text, ""]
            where = " · ".join(str(e) for e in s.evidence)
            out += [f"> 근거 {len(s.evidence)} — {where}", ""]
    return out


def render_sources(evidence: list[Evidence]) -> list[str]:
    """이 장을 만든 파일들. **어느 파일을 지우면 무엇이 사라지는지** 보이는 자리다."""
    files = sorted({e.filename for e in evidence})
    return ["## 근거 파일", "", *[f"- {f}" for f in files], ""]
