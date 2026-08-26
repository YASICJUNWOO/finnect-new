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

import re
from dataclasses import dataclass, replace
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
    """읽어 낸 칸 하나.

    **병합과 크기가 기본값을 갖는다.** 어댑터가 못 주면 `1x1`·크기 0 이고, 그때는
    그 값을 보는 규칙이 안 걸린다 — 모르는 것을 1 로 아는 척하는 것과 0 으로
    모른다고 말하는 것이 다르다.
    """

    anchor: Anchor
    text: str
    #: 이 칸이 가로·세로로 몇 칸을 덮나. **좌표는 왼쪽 위 하나다**
    colspan: int = 1
    rowspan: int = 1
    #: HWPUNIT(1/7200 inch). **0 이면 모른다.** 얇은 장식 칸을 거르는 데 쓴다 —
    #: 실측에서 5.4pt 짜리 여백 칸이 값을 삼켰고 파일에 남았는데 안 보였다
    width: int = 0
    height: int = 0

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
    return re.sub(r"[\s　:：]", "", s or "").lower()


#: 채울 자리로 보기엔 너무 얇은 칸. HWPUNIT(1/7200 inch) 이고 8pt 다.
#:
#: 양식 저자가 표 사이 여백을 주려고 5.4pt 짜리 칸을 넣어 둔다. 글자를 넣으면
#: **파일에는 들어가는데 화면에서 안 보인다** — 실측에서 「주식회사 나린데이터」가
#: 그 칸에 앉았고 400% 로 확대해야 보였다. **크기를 모르는 어댑터에서는 안 건다.**
_MIN_CELL = 800

#: 열 머리로 인정하려면 그 행에 라벨이 이만큼은 있어야 한다.
#:
#: 값이 하나 덩그러니 있는 행은 머리가 아니다 — `사업자등록번호 × 2000-00-00` 이
#: 그렇게 생긴다. 관공서 표의 머리 행은 `구분 | 2020년 | 2021년 | …` 처럼 찬다.
_HEADER_ROW_MIN = 3

#: 채워 넣으라고 비워 둔 자리의 표시. `00 명` · `2000-00-00` · `OOOOO (상호명)`.
#:
#: **`Cell.blank` 를 안 바꾼다**(ADR-0060 결정 6). 저기는 글자가 없는 것만 보고,
#: 여기는 그 위에 얹는 값싼 바닥이다 — LLM 판정(`forms/slots.py`)이 켜지면
#: `fillable` 로 더 넓게 들어오고 둘은 겹쳐도 된다.
_PLACEHOLDER = re.compile(r"(OO|00|○○|ＯＯ)")

#: 플레이스홀더로 볼 글자 수 상한. 넘으면 안내 문장이지 채울 자리가 아니다.
_PLACEHOLDER_MAX = 60

#: 값 뒤에 붙는 단위만 든 칸. **라벨이 아니다.**
#:
#: `종업원수 | 사무직 | 00 명 | 기술직 | 00 명` 에서 `명` 을 라벨로 세면 그것이 아래
#: 칸의 열 머리가 되어 `아이템명 × 사무직` 이 나온다(육안 · 표 하나 75칸). 단위가
#: **혼자 있을 때만** 걸린다 — `인원(명)` 은 이름이라 그대로 라벨이다.
_UNIT_ONLY = re.compile(
    r"^[(\[（【]?\s*(명|원|천원|만원|백만원|억원|개|건|년|월|일|%|％|㎡|평|점|시간|kg|톤|배|회)"
    r"\s*[)\]）】]?$"
)

#: 통째로 괄호에 싸인 칸. **안내문이지 이름이 아니다.**
#:
#: `(기업의 경우만 작성)`·`(직함)`·`(무료 회원가입)` 이 라벨로 잡혀 있었다.
#: **통째로 싸인 것만 본다** — `(1) 사업 개요` 는 번호가 붙은 진짜 이름이고
#: `(주)가나다` 는 값이라, 여는 괄호만 보면 앞엣것을 잃는다.
_WRAPPED = re.compile(r"^[(（]\s*[^()（）]*\s*[)）]?$")


def is_placeholder(text: str) -> bool:
    """`00 명` 처럼 **형식만 적어 둔 칸**인가.

    **라벨로 세면 안 된다.** 실측에서 `사업자등록번호 | 000-00-00000 | 법인등록번호`
    가 그 자리였고, `000-00-00000` 을 라벨로 읽으면 그것이 **`법인등록번호` 라는 라벨
    글자를 값 자리로 잡는다.**

    **`2000년` 같은 진짜 라벨이 걸릴 수 있다.** `00` 두 자만 보는 규칙이라 그렇고,
    대가로 얻는 것이 `2000-00-00`·`0000000-0000000`·`00 명` 셋이다. 걸리면 그 칸이
    라벨 노릇을 못 할 뿐이고 값이 딴 데 가지는 않는다.
    """
    t = text.strip()
    return bool(t) and len(t) <= _PLACEHOLDER_MAX and _PLACEHOLDER.search(t) is not None


@dataclass(frozen=True, slots=True)
class Slot:
    """채울 자리 하나와 **그 자리의 이름**.

    이름이 둘로 갈리는 이유는 표가 두 방향으로 짜여서다.

        기업명 | ____                    행 라벨 하나
        구분   | 2020년 | 2021년          ← 열 머리
        매출액 | ____   | ____            행 라벨 + 열 머리
    """

    anchor: Anchor
    #: 왼쪽으로 붙어 있는 라벨들. 바깥에서 안으로 (`대표자` → `성명`)
    row_path: tuple[str, ...]
    #: 같은 열을 위로 걸어 올라가 만난 머리. 없으면 `None`
    col_head: str | None

    @property
    def label(self) -> str:
        """**가장 안쪽 이름 하나.** 이미 깔린 항목과 짝지을 때 이걸 쓴다."""
        return self.row_path[-1] if self.row_path else (self.col_head or "")

    def __str__(self) -> str:
        p = " › ".join(self.row_path)
        return f"{p} × {self.col_head}" if self.col_head else p


def _fold_repeats(cells: list[Cell]) -> list[Cell]:
    """병합 칸을 되풀이해 주는 어댑터에서만 접는다. **첫 좌표를 남긴다.**

    `python-docx` 의 `row.cells` 가 병합된 칸을 걸친 수만큼 준다 — 실측에서
    `대표자명` 이 네 번 나왔다. 접지 않으면 라벨이 **자기 복제를 오른쪽 칸으로 보고**
    짝을 통째로 잃는다.

    **크기를 아는 어댑터에서는 안 접는다.** hwp 는 병합 칸을 한 번만 저장하고
    `colspan` 을 같이 주므로, 나란한 빈 칸 셋은 진짜 칸 셋이다 —
    `매출액 | __ | __ | __` 을 접으면 2021·2022 년 자리를 통째로 잃는다.

    **연속된 것만 접는다.** `국내 | 국외 | 국내` 처럼 떨어져서 되풀이되는 것은 병합이
    아니라 진짜 열이라 접으면 좌표가 밀린다.
    """
    if any(c.width or c.height or c.colspan > 1 or c.rowspan > 1 for c in cells):
        return cells

    by_row: dict[int, list[Cell]] = {}
    for c in cells:
        by_row.setdefault(c.anchor.row, []).append(c)

    out: list[Cell] = []
    for row in by_row.values():
        row.sort(key=lambda c: c.anchor.col)
        run: list[Cell] = []
        for c in row:
            adjacent = run and run[-1].anchor.col + max(run[-1].colspan, 1) == c.anchor.col
            if adjacent and run[-1].text == c.text:
                run.append(c)
                continue
            if run:
                out.append(replace(run[0], colspan=len(run)))
            run = [c]
        if run:
            out.append(replace(run[0], colspan=len(run)))
    return out


def _grid(cells: list[Cell]) -> dict[tuple[int, int], Cell]:
    """`(행, 열)` → 그 자리를 덮는 칸. **병합 칸은 여러 자리를 덮는다.**"""
    g: dict[tuple[int, int], Cell] = {}
    for c in cells:
        for dr in range(max(c.rowspan, 1)):
            for dc in range(max(c.colspan, 1)):
                g.setdefault((c.anchor.row + dr, c.anchor.col + dc), c)
    return g


def _is_label(c: Cell) -> bool:
    """이 칸이 **이름**인가. 글자가 있고 이름 노릇을 할 수 있으면 이름이다.

    아닌 것이 셋이다 — 플레이스홀더(`000-00-00000`) · **단위만 든 칸**(`명`) ·
    **통째로 괄호에 싸인 안내문**(`(기업의 경우만 작성)`). 뒤의 둘은 육안에서 나왔다
    (표 하나 75칸 · `초기창업 현황 › 전년도매출액 › 백만원 › 업종/업태 × 명`).

    **`fillable` 을 안 본다.** 판정이 라벨을 값 자리로 오검출해도 그 오른쪽 빈 칸은
    여전히 그 라벨의 자리다 — 실측에서 `실무자성명 | (빈칸)` 이 그렇게 살았고,
    여기까지 버리면 오검출 하나가 **좌표 둘을 잃게 만든다.** 한 칸이 이름이면서
    동시에 값 자리인 것은 모순이 아니다.
    """
    t = c.text.strip()
    if not t or is_placeholder(t):
        return False
    return not _UNIT_ONLY.match(t) and not _WRAPPED.match(t)


def _is_slot(c: Cell, fillable: frozenset[Anchor]) -> bool:
    """이 칸이 **채울 자리**인가."""
    if c.height and c.height < _MIN_CELL:
        return False
    if c.width and c.width < _MIN_CELL:
        return False
    return c.blank or is_placeholder(c.text) or c.anchor in fillable


def _row_labels(g: dict[tuple[int, int], Cell], c: Cell, *, skip: bool) -> list[Cell]:
    """왼쪽으로 훑어 **가장 가까운 연속 덩어리**만.

    처음 만난 라벨부터 붙어 있는 데까지 잡고 끊기면 멈춘다. 이 한 줄이
    `대표자 › 성명` 과 `실무자 › 성명` 을 가른다 — 안 끊으면 실무자 칸이
    `대표자 › 성명 › 실무자 › 성명` 이 되어 **둘이 구별되지 않는다.**

        대표자 | 성명 | ____ | 실무자 | 성명 | ____
                        └ [대표자, 성명]        └ [실무자, 성명]

    `skip` 이 앞쪽의 값 자리를 건너뛸지 정한다. **건너뛰면 남의 라벨을 훔친다** —
    `사업자등록번호 | 000-00-00000 | 법인등록번호 | ___` 에서 셋이 다 사업자등록번호를
    자기 이름으로 들고 겹침으로 전부 버려진다. 그래서 기본은 안 건너뛰는 것이고,
    `매출액 | __ | __` 처럼 **열 머리가 자리를 갈라 줄 때만** 건너뛴다.
    """
    out: list[Cell] = []
    col, started = c.anchor.col - 1, False
    while col >= 0:
        o = g.get((c.anchor.row, col))
        if o is None or o is c:
            break
        if _is_label(o):
            out.append(o)
            started = True
        elif started or not skip:
            break
        col = o.anchor.col - 1
    out.reverse()
    return out


def _col_head(g: dict[tuple[int, int], Cell], c: Cell, labels: list[Cell]) -> Cell | None:
    """같은 열을 위로 걸어 올라가 처음 만나는 머리 칸. **두 겹으로 거른다.**

    **① 행 라벨 블록 위로 안 넘어간다.** 없으면 `매출액` 을 찾다가 위 블록의
    `실무자 이메일` 까지 올라가고, 그러면 `실무자이메일 › 2024년 › 매출액` 이 나온다.

    **② 머리 행에서만 인정한다.** 값이 하나 있는 행은 머리가 아니다 —
    `사업자등록번호 × 2000-00-00` 이 그렇게 생긴다.

    **③ 머리 행에는 이름 아닌 글자가 없다.** 라벨 셋만 세면 `종업원수 | 사무직 |
    00 명 | 기술직 | 00 명 | …` 이 머리 행으로 통과해서 아래 칸이 `아이템명 ×
    사무직` 을 이름으로 든다(육안). 그 행은 머리가 아니라 **자기 값을 든 데이터
    행**이고, 가르는 재료가 「이름 아닌 글자가 섞여 있는가」다. 빈 칸은 섞인 것이
    아니다 — 진짜 머리 행의 왼쪽 위 모서리가 비어 있다.
    """
    stop = min((o.anchor.row for o in labels), default=c.anchor.row)
    r = c.anchor.row - 1
    while r >= 0:
        o = g.get((r, c.anchor.col))
        if o is None or o is c:
            return None
        if _is_label(o):
            if o.anchor.row > stop:
                return None
            row = {id(x): x for (rr, _cc), x in g.items() if rr == o.anchor.row}.values()
            names = [x for x in row if _is_label(x)]
            if len(names) < _HEADER_ROW_MIN:
                return None
            return o if all(_is_label(x) or not x.text.strip() for x in row) else None
        # 빈 칸도 플레이스홀더도 머리가 아니다 — 지나쳐서 계속 올라간다
        r = o.anchor.row - 1
    return None


def label_paths(cells: list[Cell], fillable: frozenset[Anchor] = frozenset()) -> list[Slot]:
    """채울 자리마다 **이름을 붙인다** (ADR-0070).

    `label_targets` 가 「같은 행 바로 오른쪽」만 볼 수 있었던 것은 좌표의 열이 격자
    열이 아니어서였다 — 위 칸과 아래 칸이 같은 열인지 알 방법이 없었다. 좌표가
    격자로 올라오면서 **열 축이 생겼고**, 그래서 열 머리를 걸어 올라갈 수 있다.

    실측에서 값 자리 후보 29,497칸 중 **왼쪽에 라벨이 있는 것은 37%뿐**이고 나머지
    63%는 머리가 위에 있었다. 그 63%가 여기서 열린다.

    **모르면 안 낸다.** 라벨도 머리도 없는 칸은 목록에 안 오른다.
    """
    out: list[Slot] = []
    by_table: dict[tuple[int, int], list[Cell]] = {}
    for c in cells:
        by_table.setdefault((c.anchor.section, c.anchor.table), []).append(c)

    for group in by_table.values():
        folded = _fold_repeats(group)
        g = _grid(folded)
        for c in folded:
            if not _is_slot(c, fillable):
                continue
            # **바로 왼쪽이 먼저다.** 건너뛴 라벨은 열 머리가 뒷받침할 때만 쓴다
            labels = _row_labels(g, c, skip=False)
            head = _col_head(g, c, labels)
            if not labels:
                far = _row_labels(g, c, skip=True)
                head = _col_head(g, c, far)
                labels = far if head is not None else []
            if not labels and head is None:
                continue
            out.append(
                Slot(
                    c.anchor,
                    tuple(o.text.strip().replace("\n", " ") for o in labels),
                    head.text.strip().replace("\n", " ") if head is not None else None,
                )
            )
    return out


def label_targets(
    cells: list[Cell], fillable: frozenset[Anchor] = frozenset()
) -> list[tuple[str, Anchor]]:
    """`(라벨, 값이 들어갈 칸)` 을 순서대로. **가장 안쪽 이름 하나를 낸다.**

    이미 깔린 `document_item` 과 짝지으려면 이름이 하나여야 한다 — 저쪽 제목은
    텍스트 추출이 만든 것이라 `대표자 › 성명` 같은 경로가 아니다. 한정된 경로가
    필요한 자리는 `label_paths` 를 쓴다.

    **라벨이 겹쳐도 여기서는 안 버린다.** 겹치는 것을 아는 것은 부르는 쪽이고,
    그쪽이 「둘 이상이면 안 채운다」를 정한다 — 여기서 첫 번째를 골라 주면 그
    선택이 조용히 일어난다(`spike/anchor_check.py` 가 부러뜨린 바로 그 방식).
    """
    return [(s.label, s.anchor) for s in label_paths(cells, fillable) if s.label]


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
