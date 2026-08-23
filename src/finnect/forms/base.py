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
class ParaAnchor:
    """파일 안의 **문단** 하나. 표 밖에 있는 자리다.

    ## 왜 좌표가 둘로 갈리나

    서술 항목의 글 자리는 표가 아니다. 실측(`bizinfo:PBLN_…125577` 활동계획서)에서
    이렇게 생겼다.

        문단 16   1. 목적 및 필요성           ← 제목
        문단 17   - 참가하고자 하는 …작성      ← 지시문
        문단 18   (빈 문단)                  ← 여기에 글이 들어간다
        문단 25   2. 수주 활동 대상           ← 다음 항목

    `Anchor` 는 `(구역, 표, 행, 열)` 이라 이 자리를 못 가리킨다. 그래서 서술 항목
    1,158개가 **전부 좌표 없이** 남아 있었고, 채우기가 그것을 통째로 건너뛰었다 —
    화면은 「썼어요」라고 말하는데 파일에는 안 들어갔다.

    **DB 에는 `p:0:18` 로 앉는다.** 앞에 `p:` 가 붙는 것이 셀 좌표와 가르는 표시이고,
    그래서 이미 심긴 셀 좌표 956개를 **손대지 않아도 된다**(`parse_anchor` 참조).
    """

    section: int
    #: 그 구역 안에서 몇 번째 문단인가. **표 안 문단은 안 센다**
    index: int

    def __str__(self) -> str:
        return f"p:{self.section}:{self.index}"

    @classmethod
    def parse(cls, s: str) -> ParaAnchor:
        _, a, b = s.split(":")
        return cls(int(a), int(b))


def parse_anchor(s: str) -> Anchor | ParaAnchor:
    """DB 문자열을 좌표로. **`p:` 로 시작하면 문단이다.**

    옛 값(`0:3:1:2`)이 그대로 셀로 읽히는 것이 이 형식의 요점이다 — 문단 좌표를
    더하면서 마이그레이션을 안 만든다.
    """
    return ParaAnchor.parse(s) if s.startswith("p:") else Anchor.parse(s)


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


@dataclass(frozen=True, slots=True)
class Para:
    """읽어 낸 문단 하나. **표 안 문단은 여기 안 온다** — 저기는 `Cell` 이다."""

    anchor: ParaAnchor
    text: str

    @property
    def blank(self) -> bool:
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

    def paragraphs(self) -> list[Para]:
        """표 **밖**의 문단을 순서대로. 서술 항목의 글 자리가 여기 있다.

        **표 안 문단을 여기 넣지 않는다.** 넣으면 같은 글자가 `cells()` 와 두 번
        나오고, 좌표 둘이 같은 자리를 가리켜 채우기가 두 번 쓴다.
        """
        ...

    def fill(self, anchor: Anchor | ParaAnchor, value: str) -> bool:
        """그 자리에 값을 넣는다. **못 넣으면 `False` 다.**

        hwp 는 이미 글자가 있는 자리에 `False` 를 준다 — 갈아 끼우는 것 자체가
        배치를 깨뜨린다(ADR-0060 결정 3, 판본 A~G). **문단도 같은 규칙이다.**
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


def _fold_spans(row: list[Cell]) -> list[Cell]:
    """가로로 병합된 칸을 하나로 접는다. **첫 좌표를 남긴다.**

    `python-docx` 의 `row.cells` 가 병합된 칸을 걸친 수만큼 반복해서 준다 —
    실측에서 `대표자명` 이 네 번 나왔다. 접지 않으면 라벨이 **자기 복제를 오른쪽
    칸으로 보고** 짝을 통째로 잃는다.

    **연속된 것만 접는다.** `국내 | 국외 | 국내` 처럼 떨어져서 되풀이되는 것은
    병합이 아니라 진짜 열이라 접으면 좌표가 밀린다.
    """
    out: list[Cell] = []
    for c in row:
        if out and out[-1].text == c.text:
            continue
        out.append(c)
    return out


def label_targets(cells: list[Cell]) -> list[tuple[str, Anchor]]:
    """`(라벨, 값이 들어갈 칸)` 을 순서대로.

    **바로 오른쪽 칸이 값 자리다.** 관공서 양식이 `라벨 | 빈칸` 으로 짜여 있고,
    실측에서 그 모양으로 165칸을 채웠다(ADR-0060).

    ## 건너뛰지 않는다

    예전에는 「오른쪽 **첫 빈 칸**」이었고 그것이 칸을 건너뛰었다. 실측
    (`bizinfo:PBLN_…125460` 신청서)의 한 행이 이렇게 생겼다.

        사업자등록번호 | 000-00-00000 | 법인등록번호 | (빈칸)

    `000-00-00000` 은 안내문이라 빈 칸이 아니고, 규칙이 그것을 지나쳐 **법인등록번호의
    빈 칸**을 사업자등록번호의 값 자리로 골랐다. 채운 파일에서 사업자등록번호가
    법인등록번호 칸에 앉았고 **파일은 정상으로 열려서** 제출 직전에야 드러난다.
    한 칸이라도 건너뛴 시점에서 그 빈 칸은 **이미 다른 라벨의 값 자리**다.

    **재현율을 정확성과 바꾼 것이다.** 건너뛰어야 닿는 칸을 이제 못 채우는데, 그
    자리는 안내문이 값 자리를 막고 있는 경우라 [plan/24] T-0153 이 그 칸을 값
    자리로 인정하면서 되찾는다. **모르는 자리를 찍어서 채우지 않는다** — 라벨이
    겹칠 때 아예 버리는 것과 같은 판단이다.

    ## 그 밖의 경계

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
    for row in by_row.values():
        row.sort(key=lambda c: c.anchor.col)
        # **접고 나서 인접을 본다.** 순서가 반대면 병합된 라벨이 자기 복제를
        # 오른쪽 칸으로 보고 전부 탈락한다.
        run = _fold_spans(row)
        for i, c in enumerate(run[:-1]):
            nxt = run[i + 1]
            if c.blank or not nxt.blank:
                continue
            out.append((c.text, nxt.anchor))
    return out


def outline_targets(
    paras: list[Para], titles: list[str]
) -> list[tuple[str, ParaAnchor]]:
    """`(항목 제목, 글이 들어갈 빈 문단)` 을 순서대로 (ADR-0061 결정 3의 뒷자리).

    **제목 문단 다음의 첫 빈 문단이 글 자리다.** 실측한 모양이 이렇다.

        16   1. 목적 및 필요성       ← 제목. 항목의 `title` 은 번호를 뗀 것이라
        17   - …에 대하여 작성        ← 지시문. 비어 있지 않으니 건너뛴다
        18   (빈 문단)              ← 여기
        25   2. 수주 활동 대상        ← 다음 제목을 만나면 멈춘다

    **다음 제목을 넘어가지 않는다.** 넘어가면 항목 둘이 같은 문단을 가리키고,
    나중 항목의 글이 앞 항목 자리에 앉는다.

    **제목이 파일에 없거나 빈 문단이 없으면 그 항목을 안 낸다.** `1. 목적 및
    필요성` 바로 밑에 표가 오는 양식이 있는데, 거기서 아무 문단이나 고르면 글이
    엉뚱한 데에 들어가고 **파일은 정상으로 열려서** 제출 직전에야 드러난다 —
    셀 좌표에서 라벨이 겹칠 때 아예 버리는 것과 같은 판단이다.

    **라벨 대조가 `endswith` 인 것이 요점이다.** 항목 제목은 `outline` 이 번호를
    떼어 낸 값(`목적 및 필요성`)이고 문단은 번호를 달고 있다(`1. 목적 및 필요성`).
    """
    want = {norm_label(t): t for t in titles if norm_label(t)}
    if not want:
        return []

    #: 제목이 앉은 문단. **겹치면 그 제목을 통째로 버린다**
    at: dict[str, int | None] = {}
    for i, p in enumerate(paras):
        key = norm_label(p.text)
        if not key:
            continue
        for k in want:
            # **짧은 제목이 아무 문장에나 걸리는 것을 막는다.** `기타` 같은 두
            # 글자가 본문 한복판에서 끝나는 일이 실제로 있다
            if key == k or (key.endswith(k) and len(key) - len(k) <= _NUMBER_HEAD):
                at[k] = None if k in at else i
    heads = sorted(i for i in at.values() if i is not None)

    out: list[tuple[str, ParaAnchor]] = []
    for k, i in at.items():
        if i is None:
            continue
        stop = next((h for h in heads if h > i), len(paras))
        # **구역을 건너지 않는다.** hwp 는 본문이 구역으로 갈리고 구역이 바뀌면
        # 쪽이 갈린 것이라, 그 너머의 빈 문단은 이 항목의 자리가 아니다.
        sec = paras[i].anchor.section
        blank = next(
            (p for p in paras[i + 1 : stop] if p.blank and p.anchor.section == sec), None
        )
        if blank is not None:
            out.append((want[k], blank.anchor))
    return out


#: 제목 앞에 붙을 수 있는 번호의 최대 길이. `1.`·`2-1.`·`(3)`·`가.` 를 견딘다.
#: **늘리면 `사업 계획` 이 `향후 사업 계획` 에 걸린다.**
_NUMBER_HEAD = 6


class UnsupportedFormat(ValueError):
    """채울 수 없는 포맷. pdf·zip·xlsx 가 여기 온다(코퍼스의 8%)."""


class FormsUnavailable(RuntimeError):
    """이 환경에서 그 포맷을 못 연다.

    **`UnsupportedFormat` 과 다르다.** 저기는 포맷이 애초에 안 되는 것이고 여기는
    되는데 지금 이 서버에 준비가 없는 것이다 — hwp 에 JVM 이 없는 경우가 그렇고,
    화면이 사용자에게 다르게 말해야 한다.
    """
