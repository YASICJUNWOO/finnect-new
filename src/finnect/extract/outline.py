"""서술형 양식에서 **항목 트리와 지시문**을 뽑는다 (plan/11 T-0037 · ADR-0019).

집필의 축은 배점이 아니라 **양식 목차와 항목별 작성 지침**이다([ADR-0019](
../../../docs/adr/0019-집필의-축을-양식으로.md)). 그 축이 여기서 나온다.

## 규칙으로 한다

네 번 실패한 것은 **구간이 양식인지 가르는 일**이었지 항목을 읽는 일이 아니다.
양식이라는 것을 알고 나면 번호 체계가 실제로 규칙적이다.

    1. 사업 내용                    ← 1단
     1-1. 지원프로그램               ← 2단
      가. 신청 지원 프로그램          ← 3단
       ① 예) 시제품제작지원           ← 4단

## 지시문을 고쳐 쓰지 않는다

`- … 구체적으로 기술` 은 **양식이 쓴 그대로** 저장한다. 우리가 해요체로 바꾸면
어디까지가 공고의 요구인지 알 수 없게 된다(plan/11).

## 제목이 빈 헤딩은 항목이 아니다

`가.` 만 있고 뒤가 빈 줄이 실제로 있다. 이름이 없으면 화면에 쓸 것도 집필에 줄
것도 없다. **버리고, 그 아래 지시문은 위 항목에 붙인다** — 지시문이 더 값지다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: 1단. `2. 사업 내용`
_L1 = re.compile(r"^[ \t]*(?P<no>\d{1,2})\.[ \t]*(?P<title>.*)$")
#: 2단. `2-1. 지원프로그램` · `2.1 지원프로그램`
_L2 = re.compile(r"^[ \t]*(?P<no>\d{1,2}\s*[-.]\s*\d{1,2})\.?[ \t]*(?P<title>.*)$")
#: 3단. `가.` ~ `하.` **`다.` 는 접속사로도 쓰이므로 뒤에 마침표를 요구한다**
_L3 = re.compile(r"^[ \t]*(?P<no>[가-힣])\.[ \t]*(?P<title>.*)$")
#: 4단. `①` · `(1)` · `1)`
_L4 = re.compile(r"^[ \t]*(?P<no>[①-⑳]|\(\d{1,2}\)|\d{1,2}\))[ \t]*(?P<title>.*)$")

#: 3단에 올 수 있는 글자. 이 밖의 한 글자 + 마침표는 문장 끝이다
_HANGUL_ORDER = "가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허"

#: 지시문 줄머리. 양식이 실제로 쓰는 것만 넣었다
_BULLET = re.compile(r"^[ \t]*(?:[-–—*※○◦◇□▷▶·∙•]|[oO]\s)[ \t]*(?P<body>.+)$")

#: 지시문임을 말하는 동사. **`※` 는 이것 없이도 지시문으로 본다**
_VERB = re.compile(r"기술|기재|작성|서술|설명|제시|명시|기입|입력|첨부|삭제")

#: `50페이지 내외` · `1page 이내` · `A4 2매 이하` · `500자 이내`
_LIMIT = re.compile(
    r"(?:A4\s*)?\d{1,4}\s*(?:페이지|page|pages|p|매|장|자|글자|줄)\s*(?:이내|내외|이하|미만)"
)

#: 표지가 아니라 본문인 줄. 이보다 길면 헤딩이 아니다
_MAX_TITLE = 60
#: 지시문 한 항목이 이보다 길면 자른다. 원문은 오프셋으로 다시 열 수 있다
_MAX_INSTRUCTION = 1_200


@dataclass(frozen=True, slots=True)
class Item:
    """항목 하나. **오프셋은 넘겨받은 텍스트 기준이다** — 구간 시작을 더해서 쓴다."""

    number: str | None
    title: str
    level: int
    instruction: str | None
    limit_text: str | None
    start: int
    end: int
    #: 부모의 목록 인덱스. 최상위는 `None`
    parent: int | None


@dataclass(slots=True)
class _Head:
    number: str
    title: str
    level: int
    start: int
    line_end: int
    lines: list[str] = field(default_factory=list)


def items(text: str) -> list[Item]:
    """양식 하나에서 항목을 순서대로 뽑는다.

    **항목이 하나도 안 나오면 빈 목록이다.** 지어내지 않는다 — 서술형으로 판정됐는데
    항목이 0개면 그것이 판정이 틀렸다는 신호이고, 가짜 항목을 만들면 그 신호가 사라진다.
    """
    heads = _headings(text)
    if not heads:
        return []

    out: list[Item] = []
    stack: list[tuple[int, int]] = []  # (level, 목록 인덱스)
    for i, h in enumerate(heads):
        end = heads[i + 1].start if i + 1 < len(heads) else len(text)
        block = "\n".join(h.lines)
        instruction = _instruction(h.lines)

        while stack and stack[-1][0] >= h.level:
            stack.pop()
        parent = stack[-1][1] if stack else None

        out.append(
            Item(
                number=h.number,
                title=h.title,
                level=h.level,
                instruction=instruction,
                limit_text=_limit(f"{h.title}\n{block}"),
                start=h.start,
                end=end,
                parent=parent,
            )
        )
        stack.append((h.level, len(out) - 1))
    return out


def _headings(text: str) -> list[_Head]:
    """헤딩 줄을 찾고 그 아래 줄들을 매단다."""
    heads: list[_Head] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        start, pos = pos, pos + len(line)
        bare = line.rstrip("\r\n")

        hit = _match(bare)
        if hit is None:
            if heads:
                heads[-1].lines.append(bare)
            continue

        number, title, level = hit
        if not title:
            # **제목이 없으면 항목이 아니다.** 아래 지시문은 위 항목이 받는다
            if heads:
                heads[-1].lines.append(bare)
            continue
        heads.append(_Head(number=number, title=title, level=level, start=start, line_end=pos))
    return heads


def _match(line: str) -> tuple[str, str, int] | None:
    """헤딩이면 `(번호, 제목, 단)`. **2단을 1단보다 먼저 본다** — `2-1.` 이 `2.` 로 잡힌다."""
    if not line.strip() or "\t" in line:
        return None  # 탭이 있으면 표의 한 줄이다

    for pattern, level in ((_L2, 2), (_L1, 1), (_L3, 3), (_L4, 4)):
        m = pattern.match(line)
        if m is None:
            continue
        no = re.sub(r"\s+", "", m.group("no"))
        if level == 3 and no not in _HANGUL_ORDER:
            continue  # `다.` 는 되지만 `것.` 은 아니다
        title = m.group("title").strip()
        if len(title) > _MAX_TITLE:
            return None  # 본문 문장이다
        return no.replace(".", "-"), title, level
    return None


def _instruction(lines: list[str]) -> str | None:
    """줄머리가 붙은 지시문만 모은다. **양식이 쓴 그대로 둔다.**"""
    out: list[str] = []
    for raw in lines:
        if "\t" in raw:
            continue  # 표의 한 줄이다
        m = _BULLET.match(raw)
        if m is None:
            continue
        body = m.group("body").strip()
        marker = raw.lstrip()[:1]
        if not body:
            continue
        if marker != "※" and not _VERB.search(body):
            continue
        out.append(body)
        if sum(len(x) for x in out) > _MAX_INSTRUCTION:
            break
    return "\n".join(out)[:_MAX_INSTRUCTION] or None


def _limit(block: str) -> str | None:
    """`본문은 50페이지 내외로 작성` 에서 `50페이지 내외` 만."""
    m = _LIMIT.search(block)
    return m.group(0).strip() if m else None
