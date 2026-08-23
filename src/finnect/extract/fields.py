"""구간이 **칸 채우기 서식인지** 보고, 맞으면 칸 이름을 꺼낸다(plan/11 T-0037).

**서술형은 여기서 안 한다.** 공고문의 절(`1. 사업개요 / 2. 신청자격`)과 양식의
항목(`1. 추진배경 / 2. 주요내용`)이 생김새가 같아서 규칙이 네 번 실패했다
([실측 §3](../../../docs/adr/evidence/2026-08-17-양식-항목-추출-실측.md)).
그 판정은 T-0036 이 LLM 으로 한다. 여기는 **규칙으로 갈리는 것만** 한다.

칸 채우기는 신호가 다르다. 신청자가 채워 내는 문서라 끝에
`위와 같이 신청합니다 / OO장 귀하 / (인)` 이 오고, 표에 `라벨 → 빈칸` 이 있다.
**공고문에는 그 조합이 없다.**

표본 10건을 눈으로 봤다. 파일 단위로 8건이 진짜 서식이었고, 틀린 둘은
공고문의 '지원내용' 표와 평가 배점표였다. **그 둘은 구간을 자르면 안 들어온다** —
`segment.split()` 이 선행인 이유가 이것이다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from finnect.extract import segment as sg

_SUBMIT = re.compile(
    r"(위와|상기와)\s*같이[^\n]{0,40}?(신청|제출|지원)합니다|신청합니다|제출합니다"
)
_RECEIVER = re.compile(r"귀\s*하|귀\s*중")
_SIGN = re.compile(r"\(\s*서\s*명[^)]{0,8}\)|\(\s*인\s*\)|서명\s*또는\s*인")

#: 표의 첫 셀. T-0032·T-0033 이 살린 탭 경계다.
_ROW = re.compile(r"^(?P<label>[^\t]{1,24})\t")

#: 값이지 라벨이 아닌 것. 숫자·기호만이거나 날짜 꼴이다.
_NOT_LABEL = re.compile(r"^[\d\s.·,%()\-~/]+$|^\d{4}\s*[.\-]")

#: 체크 상자만 늘어선 칸. 라벨이 아니라 보기다.
_CHOICE = re.compile(r"^[□■☐▢]")

#: 서류 표지. **채울 칸이 아니라 서식 제목이다.**
#:
#: 한글 양식이 제목을 표 하나로 감싸는데(`붙임 1 | (빈칸) | (빈칸) | 임대신청서 및
#: 사업계획서 서식`) 그러면 `붙임 1` 이 라벨이 되고 **옆의 장식용 빈 칸이 값 자리로
#: 판정된다.** 실제로 그 자리에 회사 이름이 들어갔고, 칸이 좁아서 한/글에서 글자가
#: 세로로 눌려 나왔다(2026-08-23 육안).
#:
#: 코퍼스에서 그렇게 잡힌 항목이 **166개**이고 그중 90개에 좌표가 붙어 있었다.
#:
#: **낱말을 `segment` 와 공유한다** — 갈리면 한 파서가 표지로 자른 자리를 다른
#: 파서가 채울 칸으로 뽑는다.
_MARKER_LABEL = re.compile(rf"^[\[【<(]?\s*(?:{sg.MARKER_WORDS})\s*(?:제\s*)?\d")

MIN_LABELS = 5
MIN_SIGNALS = 2


def signals(text: str) -> int:
    """'채워 내는 문서' 신호가 몇 개인가. 줄바꿈에 기대지 않는다."""
    flat = re.sub(r"\s+", " ", text)
    return sum(bool(p.search(flat)) for p in (_SUBMIT, _RECEIVER, _SIGN))


@dataclass(frozen=True, slots=True)
class Row:
    """표 라벨 하나와 **원문에서의 자리.**

    위치를 드는 이유는 한 서식에 표와 서술이 섞여 있어서다. 둘을 같이 깔 때
    원문 순서로 섞으려면 양쪽이 자리를 알아야 한다 — 표를 다 내고 서술을 뒤에
    붙이면 화면 순서가 문서와 어긋난다(실측: `kstartup:178697` 에서 신청서 표와
    사업계획 항목이 번갈아 나온다).
    """

    label: str
    start: int


def rows(text: str, *, limit: int = 400) -> list[Row]:
    """표의 라벨을 자리와 함께 순서대로. **중복은 첫 번째만 남긴다.**

    같은 라벨이 여러 서식에 반복되는데(기업명·대표자), 화면에 두 번 낼 이유가 없다.
    """
    out: list[Row] = []
    seen: set[str] = set()
    pos = 0
    for line in text.splitlines(keepends=True):
        start, pos = pos, pos + len(line)
        m = _ROW.match(line)
        if not m:
            continue
        lab = re.sub(r"\s{2,}", " ", m.group("label").strip())
        if len(lab) < 2 or lab in seen:
            continue
        if _NOT_LABEL.match(lab) or _CHOICE.match(lab) or is_marker(lab):
            continue
        seen.add(lab)
        out.append(Row(lab, start))
        if len(out) >= limit:
            break
    return out


def labels(text: str, *, limit: int = 400) -> list[str]:
    """라벨만. 자리가 필요 없는 쪽이 쓴다(`is_fields` 와 화면)."""
    return [r.label for r in rows(text, limit=limit)]


def is_marker(label: str) -> bool:
    """서류 표지인가. **라벨이 아니다** — 옆 칸은 값 자리가 아니라 장식이다."""
    return bool(_MARKER_LABEL.match((label or "").strip()))


def is_fields(text: str) -> bool:
    """칸 채우기 서식인가. **애매하면 아니라고 한다.**

    놓친 것은 화면에 안 뜰 뿐이고, 잘못 잡으면 공고문 표가 '채울 칸'으로 뜬다.
    둘 중에는 놓치는 쪽이 낫다.
    """
    return signals(text) >= MIN_SIGNALS and len(labels(text)) >= MIN_LABELS
