"""순서와 이유 — **템플릿으로 만들고 잰다** (plan/17 T-0074 · M2).

취지 키워드와 사업 내용 노드의 겹침으로 순서를 내고, 겹친 노드로 이유 한 줄을
만든다. **LLM 0회.**

## 점수를 만들지 않는다

등급 셋뿐이고 같은 등급 안의 순서는 코드가 정한다 — 분야 일치 → 겹침 수 → 마감
임박. 연속값을 만들면 화면에 안 내도 **설명할 눈금이 없는 순서**가 된다
(`DESIGN.md` §6 · `Fact` 에 `confidence` 를 안 넣은 것과 같은 이유).

## 근거가 자동으로 매달린다

겹친 것이 어느 `wiki_fact` 인지 코드가 알고 있어서 **LLM 출력을 검증할 필요가
없다.** `draft_evidence` 가 `fact_id` 를 든 것과 같은 자리고 나중에 붙일 수 없다.

## 겹친 노드가 0건이면 추천하지 않는다

`SPEC.md` §9-2("적합도 이유를 못 만들 때")가 여기서 닫힌다 — 템플릿이라 못 만드는
경우가 **그 하나뿐이다.** `02_기능명세` 의 "안 나오면 내보내지 않는다" 를 따른다.

## 흔한 낱말을 키워드로 안 쓴다

`지원` · `기업` · `사업` 은 어느 위키에나 있다. 그것으로 겹침을 세면 전부 `맞다` 가
되고 순서가 무의미해진다. `STOP` 이 그 목록이고, **키워드가 전부 걸러지면 그 공고는
겹침 0 이다** — 조용히 통과시키지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from finnect.match.profile import NEED_NODES, NodeFact
from finnect.models import FitVerdict

#: 겹침으로 세지 않는 낱말. **어느 위키에나 있어서 신호가 0 이다**
STOP: frozenset[str] = frozenset(
    {
        "지원", "기업", "사업", "창업", "중소기업", "스타트업", "소기업", "중소",
        "모집", "신청", "접수", "공고", "선정", "참여", "운영", "추진", "육성",
        "기술", "제품", "서비스", "시장", "성장", "혁신", "개발", "국내",
    }
)

#: 이유 문장에 넣는 근거의 길이 상한. 노드 텍스트가 100자를 넘는다
_CLIP = 70

#: 어느 노드가 **"왜 맞는지"** 를 말하기에 좋은가. 앞이 좋다.
#:
#: **실측으로 넣었다**(2026-08-20 손 라벨 15건). 넣기 전에는 겹침 수와 길이만 봐서
#: 이런 이유가 나왔다 —
#:
#:     "소상공인이 주제예요. 성남·용인 소상공인 30명 중 21명(70%)이 재고를 수기
#:      또는 기억으로만 관리하고 있었다"
#:
#: 짧아서 골린 `problem` 노드인데, 그건 **시장 조사 결과이지 우리가 맞는 이유가
#: 아니다.** `identity`(우리가 하는 일)가 맞는 근거인데 59자로 더 길어서 밀렸다.
#: 표에 없는 노드는 맨 뒤다.
NODE_RANK: dict[str, int] = {
    "identity": 0,   # 우리가 하는 일. **이유의 근거로 가장 적합하다**
    "solution": 1,   # 솔루션과 기술
    "customer": 2,   # 목표 고객
    "region": 3,     # 지역 연계 — 지자체 공고에 직결된다
    "traction": 4,   # 매출과 성과
    "roadmap": 5,    # 로드맵
    "team": 6,
    "market": 7,
    "finance": 8,
    "problem": 9,    # 문제 인식. **조사 결과라 이유로 약하다**
}
_RANK_TAIL = len(NODE_RANK)

_WS = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Fit:
    verdict: FitVerdict
    #: 화면에 나가는 한 줄. **비면 추천에 안 올린다**
    reason: str
    #: 겹친 키워드
    matched: tuple[str, ...]
    #: 근거가 된 사실. **`notice_fit_evidence` 가 이걸 앉힌다**
    evidence: tuple[int, ...]
    sector_hit: bool


def _squash(s: str) -> str:
    return _WS.sub("", s or "")


def _usable(kw: str) -> bool:
    k = _squash(kw)
    return len(k) >= 2 and k not in STOP


def josa(word: str, with_jong: str, without: str) -> str:
    """받침에 맞는 조사. `디지털전환` → `이`, `소상공인` → `이`, `기술` → `이`.

    **문장을 코드가 만드는 자리라 여기서 틀리면 화면 카피가 틀린다.**
    """
    if not word:
        return without
    c = word[-1]
    if not ("가" <= c <= "힣"):
        return without
    return with_jong if (ord(c) - 0xAC00) % 28 else without


def quotable(text: str) -> bool:
    """이 노드를 이유 문장에 **그대로 인용해도 되나.**

    **실측으로 만들었다**(2026-08-21 · 진짜 추출기로 갈아 넣은 뒤 첫 추천).
    화면에 이런 것이 나갔다 —

        사업화 분야예요. 통합 9만 9천원\t연동 + 다점포 통합 관리\t2027년 출시

    표 한 줄이 노드가 된 것이다. 추출 스키마가 `text` 를 "사람이 읽는 문장" 이라고
    적었는데 지켜지지 않은 것이라 **뿌리는 추출 쪽에 있다**(plan/12). 다만 이유는
    화면 카피라 여기서도 막는다 — 근거 링크로는 남기고 **인용만 안 한다.**

    **줄바꿈도 같다.** 같은 실측에서 탭을 막았더니 이번엔 줄이 셋인 목록이 나갔다 —
    이유는 카드 한 줄이라 여러 줄이 들어가면 자리가 깨진다.

    고쳐 쓰지 않는 이유는 `document_item` 과 같다. 탭을 공백으로 바꾸면 읽히긴 하지만
    원문에 없는 문장이 되고, 그러면 근거를 대조할 수가 없다.
    """
    # **일반 공백만 허용한다.** 탭·줄바꿈은 문장이 아니라 표나 목록이라는 신호다
    return not any(c.isspace() and c != " " for c in (text or ""))


def _clip(s: str) -> str:
    t = (s or "").strip()
    return t if len(t) <= _CLIP else t[: _CLIP - 1].rstrip(" ,·") + "…"


def _sector_fit(
    nodes: tuple[NodeFact, ...], label: str, cues: tuple[str, ...]
) -> Fit:
    """④ 분야가 걸렸는데 ⑤ 키워드는 안 겹칠 때의 이유 (T-0076).

    **실측으로 만든 자리다**(2026-08-20 · 층0 542건 · 정규화 100건). 자격을 넘은
    8건 중 5건이 여기였다 — ④가 살렸는데 ⑤ 교집합이 0 이라 이유가 없었고, 이유가
    없으면 추천에 못 올라간다. 눈으로 보면 5/5 가 합리적인 공고들이었다.

    **④가 어느 낱말에 걸렸는지 이미 안다**(`sectors.Match.cues`). 그 낱말이 든
    노드를 찾으면 근거가 나온다 — 임베딩보다 먼저 할 일이 이것이었다.

    등급은 `애매` 그대로다. **`맞다` 로 올리지 않는다** — 분야가 맞는 것과 취지가
    맞는 것은 다른 주장이고, 둘을 같은 등급에 넣으면 순서가 뜻을 잃는다
    ([ADR-0013](../../../docs/adr/0013-판정-두-층.md)).
    """
    if not label:
        # 이름 없는 버킷(`정보`)이거나 표 밖이다. **지어내지 않는다**
        return Fit(FitVerdict.MAYBE, "", (), (), True)

    # 낱말이 걸린 자리는 `need_text()` 안이다 — 그걸 만든 노드에서만 찾는다.
    # 전체 노드에서 찾으면 ④가 안 본 자리를 근거로 들게 된다
    scored = [
        (NODE_RANK.get(n.place, _RANK_TAIL), len(n.text), n)
        for n in nodes
        if n.place in NEED_NODES and any(c in n.text for c in cues)
    ]
    if not scored:
        # `need_text()` 는 노드를 이어 붙인 글이라 **낱말이 이음매에 걸릴 수 있다.**
        # 그러면 어느 노드의 것도 아니라 근거가 없다 — 이유를 만들지 않는다
        return Fit(FitVerdict.MAYBE, "", (), (), True)

    scored.sort(key=lambda x: (x[0], x[1]))
    evidence = tuple(x[2].fact_id for x in scored)
    best = next((x[2] for x in scored if quotable(x[2].text)), None)
    if best is None:
        return Fit(FitVerdict.MAYBE, "", cues, evidence, True)
    return Fit(
        FitVerdict.MAYBE,
        f"{label} 분야예요. {_clip(best.text)}",
        cues,
        evidence,
        True,
    )


def judge(
    *,
    keywords: tuple[str, ...],
    nodes: tuple[NodeFact, ...],
    sector_label: str = "",
    sector_cues: tuple[str, ...] = (),
) -> Fit:
    """취지 키워드와 사업 내용 노드를 대조한다.

    `nodes` 는 서술 노드 전부다. **④와 달리 로드맵만 보지 않는다** — 취지는 사업
    내용 어디와도 맞물릴 수 있다.

    **`sector_hit` 을 따로 받지 않는다.** `sectors.Match` 가 `hit=bool(cues)` 로
    만들어서 둘이 같은 값인데, 나눠 받으면 어긋난 채로 부를 수 있다.
    """
    live = tuple(k for k in keywords if _usable(k))
    sector_hit = bool(sector_cues)

    # 노드마다 몇 개의 키워드가 걸렸나. 겹침이 많은 것이 좋은 근거다
    scored: list[tuple[int, int, int, NodeFact, tuple[str, ...]]] = []
    matched: list[str] = []
    for n in nodes:
        body = _squash(n.text)
        hits = tuple(k for k in live if _squash(k) in body)
        if not hits:
            continue
        # 겹침 많은 순 → **노드 종류 순** → 짧은 순.
        # 종류가 길이보다 앞인 것이 요점이다 — 위 `NODE_RANK` 주석 참고
        scored.append(
            (-len(hits), NODE_RANK.get(n.place, _RANK_TAIL), len(n.text), n, hits)
        )
        for k in hits:
            if k not in matched:
                matched.append(k)

    if not scored:
        # 겹친 것이 없다. **분야가 맞으면 `애매`, 그것도 아니면 `아니다`**
        if not sector_hit:
            return Fit(FitVerdict.MISS, "", (), (), False)
        return _sector_fit(nodes, sector_label, sector_cues)

    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    # 근거는 겹친 노드 전부를 든다. **문장에 쓰는 것은 하나지만 링크는 다 남긴다** —
    # 그 사실이 갱신될 때 어느 추천이 낡았는지 계산되어야 한다
    evidence = tuple(t[3].fact_id for t in scored)

    best = next((t[3] for t in scored if quotable(t[3].text)), None)
    if best is None:
        # 겹치기는 했는데 인용할 문장이 없다. **근거는 남기고 이유만 비운다**
        return Fit(FitVerdict.MATCH, "", tuple(matched), evidence, sector_hit)

    head = "·".join(matched[:3])
    reason = f"{head}{josa(head, '이', '가')} 주제예요. {_clip(best.text)}"
    return Fit(FitVerdict.MATCH, reason, tuple(matched), evidence, sector_hit)


#: 등급의 순서. **`아니다` 와 `확인 필요` 는 추천에 안 오른다**
_ORDER: dict[str, int] = {
    str(FitVerdict.MATCH): 0,
    str(FitVerdict.MAYBE): 1,
    str(FitVerdict.MISS): 2,
    str(FitVerdict.UNKNOWN): 3,
}


def sort_key(verdict: str, sector_hit: bool, matched: int, days_left: int | None):
    """추천 정렬. **연속값이 없다.**

    마감일이 없는 공고(기업마당 접수 기간의 57%)는 맨 뒤로 보낸다 — 급하지 않다.
    """
    return (
        _ORDER.get(verdict, 9),
        0 if sector_hit else 1,
        -matched,
        days_left if days_left is not None else 10_000,
    )
