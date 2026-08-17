"""첨부 하나를 **낼 서류 단위로 쪼갠다**(plan/11 T-0035).

**파일 하나가 서류 하나가 아니다.** 한 파일에 공고문 → `[붙임1] 신청서` →
`[붙임2] 사진` → `[붙임3] 동의서` 가 이어 붙는다. 파일 단위로 판정하면 틀린다 —
실측에서 ✗ 로 분류한 16건 중 8건이 이것 때문이었다
(`docs/adr/evidence/2026-08-17-양식-항목-추출-실측.md` §5).

**구간마다 원문 오프셋을 들고 다닌다.** ADR-0014(통합 그래프와 근거 청크)
가 "위치정보는 파싱 단계에서만 심을 수 있다" 고 못 박았다. 여기서 안 심으면 나중에 못 붙인다.

표지 모양은 실측으로 잡았다. 텍스트 400건에서 753줄이 걸렸고 대부분 이렇게 생겼다.

    [서식 3]      【서식 2】      <서식 5>      (서식1)
    [붙임 1]      [별지 제1호 서식]            서식4)
    [서식1] 컨설팅 신청서          【서식 제2호】 반도체 … 사업계획서
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: 표지 후보. 대괄호가 있으면 번호가 없어도 받고, 없으면 번호를 요구한다.
_MARKER = re.compile(
    r"^\s*"
    r"(?P<open>[\[【<(])?\s*"
    r"(?P<kind>붙임|별첨|서식|별지|양식|첨부)\s*"
    r"(?:제\s*)?"
    r"(?P<no>\d{1,2}(?:\s*[-–]\s*\d{1,2})?)?\s*"
    r"(?:호)?\s*(?:서식)?\s*"
    r"(?P<close>[\]】>)])?"
    r"\s*(?P<tail>.{0,44})$"
)

#: `붙임 1. 온라인 입점 지원사업 신청서 1부.` 는 표지가 아니라 **제출서류 목록**이다.
_SUBMIT_LINE = re.compile(r"\d+\s*부\s*\.?\s*$|각\s*1부")

#: 표지 줄은 짧다. 이보다 길면 본문이다.
_MAX_MARKER_LEN = 60


@dataclass(slots=True)
class Segment:
    """낼 서류 한 벌. 원문의 [start, end) 구간이다."""

    seq: int
    title: str
    start: int
    end: int
    text: str


def _marker_title(line: str) -> str | None:
    """표지면 제목을, 아니면 None 을 준다."""
    if not line or len(line) > _MAX_MARKER_LEN or "\t" in line:
        return None
    m = _MARKER.match(line)
    if not m:
        return None

    tail = m.group("tail").strip()
    if _SUBMIT_LINE.search(line):
        # 서류 목록이다. 자를 자리가 아니다.
        return None

    bracketed = bool(m.group("open") and m.group("close"))
    if not bracketed and not m.group("no"):
        # `첨부파일` 처럼 맨몸 낱말은 표지로 안 본다. 본문에 흔하다.
        return None
    if not bracketed and len(tail) > 20:
        # 괄호가 없으면 뒤가 길수록 본문일 확률이 높다.
        return None

    head = m.group("kind") + (f" {m.group('no').replace(' ', '')}" if m.group("no") else "")
    return f"{head} {tail}".strip() if tail else head


def split(text: str, *, head_title: str = "공고문") -> list[Segment]:
    """텍스트를 구간으로 쪼갠다. **첫 표지 앞은 그대로 한 구간이다.**

    표지가 하나도 없으면 통째로 한 구간을 준다. 빈 목록을 주지 않는다 —
    "안 잘렸다"와 "내용이 없다"는 다른 사실이다.
    """
    cuts: list[tuple[int, str]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        title = _marker_title(line.strip())
        if title is not None:
            cuts.append((pos, title))
        pos += len(line)

    if not cuts:
        return [Segment(0, head_title, 0, len(text), text)]

    bounds: list[tuple[int, str]] = []
    if cuts[0][0] > 0:
        bounds.append((0, head_title))
    bounds.extend(cuts)

    out: list[Segment] = []
    for i, (start, title) in enumerate(bounds):
        end = bounds[i + 1][0] if i + 1 < len(bounds) else len(text)
        body = text[start:end]
        if not body.strip():
            continue
        out.append(Segment(len(out), title, start, end, body))
    return out
