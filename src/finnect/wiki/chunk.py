"""해독 텍스트를 원문 조각으로 쪼갠다 — **위치정보를 심는 단계다**(plan/12 T-0043).

이 단계가 제품의 병목이다. 여기서 좌표를 안 남기면 노드에서 원문을 열 수 없고,
집필은 요약만 보게 되고, 모델이 나머지를 지어낸다(ADR-0014).
**나중에 붙이는 것은 불가능하다.**

남기는 좌표가 셋이다.

| | 언제 있나 |
|---|---|
| `char_start` · `char_end` | **항상.** 해독 텍스트 전체에서의 자리라 그대로 잘라 보여 줄 수 있다 |
| `page` | **PDF 만.** HWPX·DOCX·XLSX 에는 쪽이라는 것이 없다 |
| `heading` | 규칙으로 잡은 최선 추정. 없을 수 있다 |

표 좌표(행·열)는 여기 없다. XLSX 파서가 T-0042 에서 붙을 때 같이 온다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from finnect.config import settings

#: 제목처럼 보이는 줄. plan/11 `extract/segment.py` 의 구간 표지와 같은 계열이지만
#: 이쪽은 **문서 안의 소제목**을 잡는다. 규칙이라 오탐이 있고, 그래서 최선 추정이다.
_HEADING = re.compile(
    r"^\s*(?:"
    r"\d{1,2}\.\s*\S"  # 3. 문제인식
    r"|\d{1,2}-\d{1,2}\.?\s*\S"  # 3-1. 창업아이템 배경
    r"|[가-하]\.\s*\S"  # 가. 개발 동기
    r"|\d{1,2}\)\s*\S"  # 1) ...
    r"|[■▶◆●□▪]\s*\S"  # ■ 사업계획서
    r"|\[[^\]]{1,24}\]\s*\S*"  # [붙임2] 사업계획서
    r"|##\s*\S"  # ## 손익계산서 · ## 슬라이드 7 — xlsx·pptx 파서가 넣는 표지
    r"|제\s*\d+\s*[조장절편]"  # 제1조
    r")"
)

#: 제목 줄의 길이 상한. 이걸 넘으면 본문이다 — 번호로 시작하는 문단이 실재한다.
_HEADING_MAX = 60

#: 서술어로 끝나는가. 한국어 제목은 이렇게 끝나지 않는다.
#: '요' 는 **앞 음절까지 묶어서** 본다 — 맨 '요' 로 잡으면 "개요"·"요금"·"필요"가 죽는다.
_SENTENCE_END = re.compile(r"(?:다|죠|[어아여워해에예네세지고나래려까게]요|함|임)\.?$")


@dataclass(slots=True)
class Piece:
    ordinal: int
    text: str
    char_start: int
    char_end: int
    page: int | None
    heading: str | None

    @property
    def chars(self) -> int:
        return len(self.text)


#: **조각을 잇는 유일한 자리.** 이 문자열이 좌표계를 정한다 — 저장하는 텍스트와
#: 청크의 `char_start`/`char_end` 가 같은 기준을 써야 한다. 두 곳에서 각자 이으면
#: 어긋난다. 실제로 그랬다: `from_pptx` 가 "\n\n" 로, 청커가 "\n" 로 이어서
#: pptx 청크 12개 중 11개의 좌표가 거짓이 됐다.
PAGE_SEP = "\n"


def join(pages: list[str]) -> str:
    """청크 좌표가 가리키는 그 텍스트. **저장할 것도 이것이다.**"""
    return PAGE_SEP.join(pages)


def is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > _HEADING_MAX:
        return False
    # 서술어로 끝나면 본문이다. **마침표 유무로 가르면 안 된다** — 마침표 없이
    # "…본문입니다" 로 끝나는 줄이 실재한다.
    #
    # 다만 '요' 로 끝나는 것을 통째로 빼면 **"1. 회사 개요" 가 같이 죽는다.** 개요·요금·
    # 필요·주요가 전부 걸린다. 그래서 해요체 어미를 앞 음절까지 붙여 본다.
    if _SENTENCE_END.search(s):
        return False
    return bool(_HEADING.match(s))


def _line_spans(text: str, base: int) -> list[tuple[int, int, str]]:
    """(시작, 끝, 줄). 끝은 줄바꿈을 빼고 잡는다 — 잘라낸 텍스트에 꼬리 개행이 안 붙는다."""
    out: list[tuple[int, int, str]] = []
    pos = 0
    for line in text.split("\n"):
        out.append((base + pos, base + pos + len(line), line))
        pos += len(line) + 1
    return out


def split(
    pages: list[str],
    *,
    target: int | None = None,
    maximum: int | None = None,
    numbered: bool | None = None,
) -> list[Piece]:
    """쪽 목록을 청크로 쪼갠다.

    `pages` 가 한 원소면 쪽이 없는 포맷이고 `page` 는 전부 None 이다.
    **쪽 경계를 절대 넘지 않는다** — 넘으면 그 청크의 쪽 번호가 거짓이 된다.

    `numbered=False` 는 **경계는 지키되 번호는 붙이지 않는다**. XLSX 시트가 그렇다 —
    손익계산서와 재무상태표가 한 조각에 섞이면 안 되지만 시트는 쪽이 아니다.
    시트 이름은 파서가 `## 손익계산서` 로 넣어 두고 `heading` 이 받는다.

    전체 텍스트는 `"\\n".join(pages)` 다. `attach.hwp.from_pdf` 와 같은 좌표계라
    `char_start`/`char_end` 가 그 텍스트에 그대로 들어맞는다.
    """
    target = target or settings.chunk_target_chars
    maximum = maximum or settings.chunk_max_chars
    has_pages = len(pages) > 1 if numbered is None else numbered

    full = join(pages)
    pieces: list[Piece] = []
    base = 0

    for idx, page_text in enumerate(pages, start=1):
        page_no = idx if has_pages else None
        #: 지금까지 본 마지막 제목. 쪽이 바뀌면 이어진다 — 절이 쪽을 넘어간다
        heading: str | None = None
        #: **이 청크가 시작될 때의** 제목. `heading` 을 그대로 쓰면 청크 안에 제목이
        #: 둘 들어갔을 때 뒤엣것으로 덮여, 청크 머리와 제목이 어긋난다
        buf_heading: str | None = None
        #: 이 청크에 들어간 줄들의 (시작, 끝). 텍스트는 full 에서 잘라 쓴다.
        buf: list[tuple[int, int]] = []

        for start, end, line in _line_spans(page_text, base):
            # 제목 앞에서 자른다. 제목이 다음 청크의 머리에 와야 그 청크가 무엇인지 말한다.
            if is_heading(line):
                if buf and buf[-1][1] - buf[0][0] >= target // 2:
                    _emit(pieces, full, buf, page_no, buf_heading)
                    buf = []
                heading = line.strip()

            if not buf:
                buf_heading = heading
            buf.append((start, end))
            size = buf[-1][1] - buf[0][0]

            # 빈 줄에서 끊는 것이 1순위, 넘치면 줄 경계에서라도 끊는다.
            if size >= maximum or (size >= target and not line.strip()):
                _emit(pieces, full, buf, page_no, buf_heading)
                buf = []

        _emit(pieces, full, buf, page_no, buf_heading)
        base += len(page_text) + len(PAGE_SEP)

    for i, piece in enumerate(pieces):
        piece.ordinal = i
    return pieces


def _emit(
    pieces: list[Piece],
    full: str,
    buf: list[tuple[int, int]],
    page: int | None,
    heading: str | None,
) -> None:
    """빈 조각은 버린다. 쪽 사이 공백만 있는 구간이 실제로 나온다."""
    if not buf:
        return
    start, end = buf[0][0], buf[-1][1]
    body = full[start:end]
    if not body.strip():
        return
    pieces.append(
        Piece(
            ordinal=len(pieces),
            text=body,
            char_start=start,
            char_end=end,
            page=page,
            heading=heading,
        )
    )
