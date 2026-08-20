"""분량 제한 — 양식이 준 것을 **잴 수 있을 때만 잰다** (plan/16 구멍 2).

지금까지 `limit_text` 를 프롬프트에 주기만 하고 안 쟀다. 모델이 지키기를 바라고
있었다. 여기가 그것을 코드로 재는 자리다.

## 쪽 수는 환산하지 않는다

`50페이지 내외` 를 글자 수로 바꾸려면 A4 한 장에 한글 몇 자인지를 정해야 하는데,
그건 서체·여백·줄간격이 정하는 값이고 **우리에게 근거가 없다.** 관례로 1,800자를
쓰지만 관례는 근거가 아니다(CLAUDE.md — 근거 없는 주장은 쓰지 않는다).

그래서 쪽 수 제한은 `unmeasurable` 로 남긴다. **틀린 숫자를 내는 것보다 못 잰다고
말하는 것이 낫다.**

## `내외` 는 초과 판정을 못 한다

`이내` · `이하` · `미만` 은 상한이라 넘으면 넘은 것이다. `내외` 는 "그 정도" 라서
넘었다고 말할 근거가 없다 — 비율만 낸다.

## 저장하지 않는다

`limit_text` 는 `document_item` 에 있고 본문은 `draft_item.body` 에 있다. 둘로
계산되는 값이라 **읽을 때마다 만드는 뷰**다 — 위키 마크다운과 같은 이유로, 들고
있으면 둘 중 하나가 먼저 낡는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: 단위 → 무엇으로 세나. **쪽 계열은 전부 `pages` 다 — 못 잰다**
UNITS: dict[str, str] = {
    "자": "chars",
    "글자": "chars",
    "페이지": "pages",
    "page": "pages",
    "pages": "pages",
    "p": "pages",
    "매": "pages",
    "장": "pages",
    "줄": "lines",
    "행": "lines",
}

#: 상한인 것. `내외` 는 여기 없다
HARD = frozenset({"이내", "이하", "미만"})

_PAT = re.compile(
    r"(?P<amount>\d{1,4})\s*"
    r"(?P<unit>글자|페이지|pages|page|자|매|장|줄|행|p)\s*"
    r"(?P<qualifier>이내|내외|이하|미만)?",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Limit:
    """양식이 준 제한 하나."""

    kind: str
    amount: int
    #: `이내` · `내외` · `이하` · `미만` · 없으면 빈 문자열
    qualifier: str
    raw: str

    @property
    def hard(self) -> bool:
        """넘었다고 말할 수 있는 제한인가."""
        return self.qualifier in HARD


@dataclass(frozen=True, slots=True)
class Check:
    """잰 결과.

    `verdict` 넷이다.

        none            제한이 없다
        ok              상한 안이다
        over            상한을 넘었다
        unmeasurable    제한은 있는데 우리가 못 잰다 (쪽 수 · `내외`)
    """

    verdict: str
    limit: Limit | None
    measured: int | None
    note: str

    @property
    def over(self) -> bool:
        return self.verdict == "over"


def parse(limit_text: str | None) -> Limit | None:
    """`본문은 50페이지 내외로 작성` → `Limit(pages, 50, 내외)`. 못 읽으면 `None`.

    **여러 개가 있으면 첫 것만 쓴다.** 양식이 둘을 주는 경우(`5페이지 이내, 2,000자
    이내`)가 있는데 어느 쪽이 우선인지 정할 근거가 없다 — 순서대로 앞의 것을 본다.
    """
    if not limit_text:
        return None
    m = _PAT.search(limit_text)
    if m is None:
        return None
    unit = UNITS.get(m.group("unit").lower())
    if unit is None:
        return None
    return Limit(
        kind=unit,
        amount=int(m.group("amount")),
        qualifier=m.group("qualifier") or "",
        raw=m.group(0).strip(),
    )


def check(body: str, limit_text: str | None) -> Check:
    """본문이 제한을 지켰나.

    **넘었어도 다시 쓰지 않는다.** F1-5-5 가 자동 수정을 금지했고, 여기는 표시하는
    자리다 — 무엇이 넘쳤는지 사람이 보고 판단한다.
    """
    limit = parse(limit_text)
    if limit is None:
        return Check("none", None, None, "")

    if limit.kind == "pages":
        return Check(
            "unmeasurable", limit, None,
            f"{limit.raw} — 쪽 수는 글자로 환산하지 않는다. 환산율의 근거가 없다",
        )

    measured = _measure(body, limit.kind)
    if not limit.hard:
        return Check(
            "unmeasurable", limit, measured,
            f"{limit.raw} — `{limit.qualifier or '단위만'}` 이라 초과 판정을 안 한다"
            f" (지금 {measured:,})",
        )
    if measured > limit.amount:
        return Check(
            "over", limit, measured,
            f"{limit.raw} 인데 {measured:,} 다 ({measured - limit.amount:,} 넘음)",
        )
    return Check("ok", limit, measured, f"{limit.raw} · 지금 {measured:,}")


def _measure(body: str, kind: str) -> int:
    """`chars` 는 공백을 뺀다 — 양식이 세는 방식이 아니라 **우리가 정한 방식이다.**

    공백을 넣고 세면 줄바꿈을 늘려 제한을 우회할 수 있다. 어느 쪽이든 정확한 값이
    아니라서, 넘쳤다는 신호로만 쓴다.
    """
    if kind == "lines":
        return len([ln for ln in body.splitlines() if ln.strip()])
    return len(re.sub(r"\s", "", body))
