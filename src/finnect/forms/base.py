"""양식 채우기의 공통 말 (plan/24 T-0151 · [ADR-0060](
../../../docs/adr/0060-양식을-채워서-원본-포맷으로-돌려준다.md)).

**이 파일은 포맷을 모른다.** 라이브러리도 JVM 도 안 끌고 온다 — 부르는 쪽과
어댑터가 공유하는 것은 여기 있는 자료형뿐이다.

## 앵커가 좌표인 이유

라벨로 찾으면 **같은 이름이 여럿일 때 조용히 틀린다.** 실측(`spike/anchor_check.py`
· kstartup:178881)에서 우리가 채운 17칸 중 둘이 그런 라벨이었다.

    기업명  3회      ← 사용자가 화면에서 본 바로 그 칸
    합계    3회      ← 예산표마다 하나씩

틀려도 파일은 정상으로 열리므로 제출 직전에야 드러난다. **좌표는 그럴 자리가
없다** — `(표, 행, 열)` 이 하나를 가리킨다.

**누름틀(`fieldBegin`)에 기대지 않는다.** hwpx 9건 중 누름틀이 있는 것은 1건뿐이고
나머지는 전부 표다(ADR-0060 실측).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Anchor:
    """파일 안의 한 칸. **포맷과 무관한 좌표다.**

    `section` 이 따로 있는 이유는 hwp·hwpx 가 본문을 구역으로 나누고 표 번호가
    구역 안에서만 이어져서다. docx 는 구역이 하나뿐이라 늘 0 이다.
    """

    section: int
    table: int
    row: int
    col: int

    def __str__(self) -> str:
        return f"{self.section}:{self.table}:{self.row}:{self.col}"

    @classmethod
    def parse(cls, s: str) -> Anchor:
        """`"0:3:1:2"` 를 되돌린다. **DB 에 문자열로 앉는다** — 정수 넷을 컬럼
        넷으로 두면 인덱스가 넷이 되고, 이 값으로 범위 검색을 할 일이 없다."""
        a, b, c, d = (int(x) for x in s.split(":"))
        return cls(a, b, c, d)


@dataclass(frozen=True, slots=True)
class Cell:
    """읽어 낸 칸 하나."""

    anchor: Anchor
    text: str

    @property
    def blank(self) -> bool:
        """빈 칸인가. **여기서는 글자가 없는 것만 본다.**

        관공서 양식이 빈칸에 형식을 적어 두지만(`000-0000-0000`·`OOOO`) 그것을
        규칙으로 가르면 안내문이 붙었을 때 안 갈린다 — 실측에서 양식 하나가 표
        115개에서 한 칸도 안 걸렸다(ADR-0060 결정 6). 그 판정은 LLM 이 하고
        [plan/24](../../../docs/plan/24-양식을-채워서-돌려준다.md) T-0153 이다.
        """
        return not self.text.strip()


class Form(Protocol):
    """양식 하나. **어댑터가 이것을 만족한다.**

    **덮어쓰기 가부를 어댑터가 답한다**(`fill` 의 반환값). 부르는 쪽이 포맷을 보고
    분기하면 그 지식이 두 곳에 살고, hwp 제약이 바뀌는 날 한쪽만 고쳐진다.
    """

    @property
    def ext(self) -> str: ...

    def cells(self) -> list[Cell]:
        """표 안의 모든 칸을 좌표와 함께. **순회 순서가 좌표를 정한다.**"""
        ...

    def fill(self, anchor: Anchor, value: str) -> bool:
        """그 칸에 값을 넣는다. **못 넣으면 `False` 다.**

        hwp 는 이미 글자가 있는 칸에 `False` 를 준다 — 갈아 끼우는 것 자체가
        배치를 깨뜨린다(ADR-0060 결정 3, 판본 A~G).
        """
        ...

    def save(self, path: str) -> None:
        """채운 파일을 쓴다. **포맷을 안 바꾼다** — 제출처가 무엇을 받는지 모른다."""
        ...


def norm_label(s: str) -> str:
    """라벨 대조용 정규화. **공백을 지운다.**

    관공서 양식이 `기   업   명`·`업 체 명` 처럼 글자 사이를 벌려 칸을 맞춘다
    (ADR-0060 실측 — 셋이 같은 라벨로 걸렸다). 본문에서 어휘를 *찾는* 경우와는
    반대 규칙이다(`match/sectors.py` 는 지우면 안 되고 `wiki/topics.py` 는 지워야
    한다 — 여기는 뒤엣것과 같은 자리다).
    """
    import re

    return re.sub(r"[\s　:：]", "", s or "").lower()


def label_targets(cells: list[Cell]) -> list[tuple[str, Anchor]]:
    """`(라벨, 값이 들어갈 칸)` 을 순서대로.

    **오른쪽 첫 빈 칸이 값 자리다.** 관공서 양식이 `라벨 | 빈칸` 으로 짜여 있고,
    실측에서 그 규칙으로 165칸을 채웠다(ADR-0060).

    **라벨이 겹쳐도 여기서는 안 버린다.** 겹치는 것을 아는 것은 부르는 쪽이고,
    그쪽이 「둘 이상이면 안 채운다」를 정한다 — 여기서 첫 번째를 골라 주면 그
    선택이 조용히 일어난다(`spike/anchor_check.py` 가 부러뜨린 바로 그 방식).

    같은 행에서만 오른쪽을 본다. 아래 칸으로 내려가지 않는다 — 표가 세로로 짜인
    양식에서 엉뚱한 칸을 잡고, 그것을 가릴 근거가 아직 없다.
    """
    by_row: dict[tuple[int, int, int], list[Cell]] = {}
    for c in cells:
        by_row.setdefault((c.anchor.section, c.anchor.table, c.anchor.row), []).append(c)

    out: list[tuple[str, Anchor]] = []
    seen: set[tuple[str, Anchor]] = set()
    for row in by_row.values():
        row.sort(key=lambda c: c.anchor.col)
        for i, c in enumerate(row):
            if c.blank:
                continue
            nxt = next((n for n in row[i + 1 :] if n.blank), None)
            if nxt is None:
                continue
            # **병합 셀을 접는다.** `python-docx` 의 `row.cells` 가 가로로 병합된
            # 칸을 걸친 수만큼 반복해서 준다 — 실측에서 `대표자명` 이 네 번 나왔고
            # 넷 다 같은 좌표(`0:0:0:12`)였다. 접지 않으면 **같은 칸 하나가
            # 「겹치는 라벨」로 잘못 판정돼** 좌표가 통째로 버려진다.
            pair = (c.text, nxt.anchor)
            if pair in seen:
                continue
            seen.add(pair)
            out.append(pair)
    return out


class UnsupportedFormat(ValueError):
    """채울 수 없는 포맷. pdf·zip·xlsx 가 여기 온다(코퍼스의 8%)."""


class FormsUnavailable(RuntimeError):
    """이 환경에서 그 포맷을 못 연다.

    **`UnsupportedFormat` 과 다르다.** 저기는 포맷이 애초에 안 되는 것이고 여기는
    되는데 지금 이 서버에 준비가 없는 것이다 — hwp 에 JVM 이 없는 경우가 그렇고,
    화면이 사용자에게 다르게 말해야 한다.
    """
