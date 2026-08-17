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

MIN_LABELS = 5
MIN_SIGNALS = 2


def signals(text: str) -> int:
    """'채워 내는 문서' 신호가 몇 개인가. 줄바꿈에 기대지 않는다."""
    flat = re.sub(r"\s+", " ", text)
    return sum(bool(p.search(flat)) for p in (_SUBMIT, _RECEIVER, _SIGN))


def labels(text: str, *, limit: int = 400) -> list[str]:
    """표의 라벨을 순서대로. **중복은 첫 번째만 남긴다.**

    같은 라벨이 여러 서식에 반복되는데(기업명·대표자), 화면에 두 번 낼 이유가 없다.
    """
    out: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        lab = re.sub(r"\s{2,}", " ", m.group("label").strip())
        if len(lab) < 2 or lab in seen:
            continue
        if _NOT_LABEL.match(lab) or _CHOICE.match(lab):
            continue
        seen.add(lab)
        out.append(lab)
        if len(out) >= limit:
            break
    return out


def is_fields(text: str) -> bool:
    """칸 채우기 서식인가. **애매하면 아니라고 한다.**

    놓친 것은 화면에 안 뜰 뿐이고, 잘못 잡으면 공고문 표가 '채울 칸'으로 뜬다.
    둘 중에는 놓치는 쪽이 낫다.
    """
    return signals(text) >= MIN_SIGNALS and len(labels(text)) >= MIN_LABELS
