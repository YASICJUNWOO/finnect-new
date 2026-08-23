"""트랙 A — 자리 추출.

묻는 것은 **「이 문서가 우리 사업에 대해 뭐라고 말하나」** 하나다. 답은 **자리표
마흔여섯 중 하나**로 온다(`spots.py` · 기획 문서 §2).

    폴더    Company · Product · …     열 고정
      자리  회사소개 · {업체명}         .md 한 장. 번호로 고른다

**트랙 B 와 호출을 나눈 이유는 그대로다.** 저쪽은 열다섯 고정이라 빠뜨리면 안 되고,
여기는 넓게 뽑아야 한다. 튜닝 방향이 반대라 한 프롬프트에 섞으면 둘 다 어중간해진다.

## 자리를 짓게 하지 않는다

2026-08-22 아침까지 LLM 이 **경로를 직접 지었다**(ADR-0056 결정 2) — 하위 경로도
깊이도 이름도. 그 대가가 재현성이었다: 어느 파일을 먼저 올리느냐가 자리 이름을
정했다. 지금은 **표에서 번호를 고른다.** 지을 수 있는 것은 `{…}` 가 있는 자리
열일곱의 **인스턴스 이름뿐**이고(경쟁사 실명·특허 번호처럼 늘어나는 것), 그 이름도
문서에서 나온다.

## 서술은 문장 하나. 값에는 이름이 붙는다

    서술   text 하나                    개발 8명·영업 4명·운영 2명이다
    값     key + value + text          key="자본금"  value="120000000"

**`qualifier` 가 없다**(ADR-0059). `key` 가 그 일을 흡수한다 — `조달액`+`시드` 대신
**`시드 조달액`** 하나다. 실측에서
한정어가 제 일을 한 것이 71종 중 10종뿐이었고 그 열이 전부 이름으로 쓸 수 있었다.

## 이름을 값에만 주는 이유

[ADR-0058](../../../docs/adr/0058-자리표를-기획-트리로-고정하고-key-를-없앤다.md) 이
`key` 를 통째로 없앴다가 **하루 만에 이름이 `qualifier` 로 옮겨 앉았다**(한정어 81건에
71종). 이름이 필요한 곳이 있었기 때문이다.

**모호했던 것은 서술 쪽뿐이다.**

    서술   Company/팀  +  key="팀 구성"    ← 자리 이름과 겹친다.  모호
    값     Company/팀  +  key="경영 인원"   ← 안 겹친다.          모호하지 않다

그래서 서술에서는 이름을 안 받고 값에서만 받는다. **가르는 물음도 이것이다** —
「값 하나로 적을 수 있나」가 아니라 **「이 사실에 이름을 붙일 수 있나」**.

## 시점을 이름에서 뗀다 — 프롬프트가 아니라 코드로

한정어에서 **22종이 시점을 이름에 박았다**(`2024년 구독 매출`). 그러면 2024년 것과
2025년 것이 다른 이름이 되어 **이력이 안 쌓인다.** 프롬프트로 두 번 막아 봤고 두 번
다 돌아왔으므로 `bare_key()` 가 코드로 뗀다.

## 앵커 규칙은 안 바뀐다

원문에서 그대로 복사 · 못 찾으면 버린다(ADR-0014). 자리표가 고정이든 아니든 여기는
같다 — 근거 없는 값을 위키에 세우지 않는 것이 트랙의 문제가 아니라 제품의 문제라서다.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from finnect.config import settings
from finnect.wiki import port, profile, spots
from finnect.wiki.port import FileView, Known, UnknownFile

#: 픽스처의 옛 topic → 자리 경로. **스텁 전용 번역표다.**
#:
#: `facts.json` 은 옛 어휘(`topic`)로 적혀 있고 **그대로 둔다** — 앵커 118개가 원문에
#: 한 글자도 안 틀리게 박혀 있어서(`tests/test_wiki_extract.py`) 어휘를 바꾸려면 손으로
#: 다시 옮겨야 하고, 그러면 정답지가 정답지가 아니게 된다. 번역은 여기서 한다.
#:
#: **인스턴스 이름 셋이 박혀 있다.** `다시로`·`파일럿-12개소`·`출원-10-2025-0114882` 는
#: 지어낸 것이 아니라 그 코퍼스에서 읽은 값이다(회사명·파일럿 매장 12개소·출원번호).
#: **스텁 전용이다** — 진짜 추출기는 문서에서 이름을 읽는다.
FIXTURE_PATH: dict[str, str] = {
    "vision": "Company/비전",
    "team": "Company/팀",
    "service_overview": "Product/다시로/소개",
    "service_feature": "Product/다시로/기능",
    "service_differentiator": "Product/다시로/차별점",
    "development_status": "Product/다시로/개발현황",
    "market_size": "Market/시장규모",
    "market_trend": "Market/트렌드",
    #: 픽스처 2건이 둘 다 **경쟁의 축** 얘기다(「경쟁의 축은 기능 수가 아니라 도입
    #: 마찰이다」). 업체 하나를 다루는 것이 아니라 `비교축` 이 맞다
    "competitor": "Competitor/비교축",
    "target_customer": "Customer/타깃고객",
    "customer_problem": "Customer/고객문제",
    "customer_evidence": "Customer/검증/파일럿-12개소",
    "revenue_model": "BusinessModel/수익모델",
    "pricing": "BusinessModel/가격정책",
    "go_to_market": "BusinessModel/판매전략",
    "revenue": "Financial/매출",
    "cost": "Financial/비용",
    "funding": "Financial/자금계획",
    "patent": "Custom/특허/출원-10-2025-0114882",
    "roadmap": "Plan/일정",
}

#: 자리가 **없는** topic 과 그 이유. 검토 대기로 가고 화면에 이유가 적힌다.
#:
#: **조용히 REVIEW 로 흘리지 않는다.** `region_link` 8건은 「기획 트리에 지역 연계
#: 자리가 없다」는 사실을 드러내는 것이고, 그 8건이 검토 대기에 앉아 있는 것이
#: 정보다 — 지우면 표의 빈틈이 안 보인다.
FIXTURE_GAP: dict[str, str] = {
    "region_link": "기획 트리에 지역 연계 자리가 없어요",
    "certification": "픽스처에 인증명이 없어 자리 이름을 못 만들어요",
    "technology": "픽스처에 기술명이 없어 자리 이름을 못 만들어요",
}

#: 픽스처가 쓸 수 있는 topic. **자유 생성 금지**(구상도 ④).
#:
#: `company_profile` 과 `application_history` 는 매칭 정보의 재료라 자리가 없다 —
#: 서술로 오면 검토 대기로 간다.
FIXTURE_TOPICS: frozenset[str] = frozenset(FIXTURE_PATH) | frozenset(FIXTURE_GAP) | {
    "company_profile",
    "application_history",
}


@dataclass(frozen=True, slots=True)
class NodeFact:
    """자리에 앉을 사실 하나. **자리를 이미 알고 나온다.**

    `key` 와 `value` 가 **둘 다 있으면 값이고 없으면 서술이다.** 따로 `kind` 를 받지
    않는 이유는 그것이 있으면 「값이라고 했는데 값이 없는」 상태가 표현되기 때문이다.
    """

    #: 자리 경로. `Company/팀` · `Custom/특허/출원-10-2025-0114882`
    path: str
    #: 원문에 그대로 있는 조각. **이걸 담은 청크가 근거가 된다**
    anchor: str
    #: 사람이 읽는 문장. **서술은 이게 내용의 전부다**
    text: str = ""

    # --- 값일 때만 찬다. 둘 다 있으면 값이고 없으면 서술이다 ---
    #: 이 값의 이름. `자본금` · `시드 조달액`. **시점은 `bare_key` 가 떼고 온다**
    key: str | None = None
    #: 정규화된 값. `120000000`. **문서가 쓴 표현은 `text` 에 남는다**
    value: str | None = None

    #: 언제 기준 사실인가. **값 칸이 없어진 뒤에도 이건 남는다** — 자리 안에서
    #: 시점 내림차순으로 세우는 축이고(ADR-0057 결정 3), 문장에서 날짜를 다시 뽑아
    #: 정렬하면 「2025.08 기준」·「작년」·「도입 3개월 차」를 파싱하는 문제가 새로 생긴다
    as_of: dt.date | None = None

    #: 기획 §5 의 자료 등급. `1차` · `2차` · `가정`. **`실측` 과 `미정` 은 여기 안 온다** —
    #: 저 둘은 추출이 아니라 사용자 답변(ADR-0028)과 빈 자리가 정한다
    grade: str = ""
    #: `2차` 일 때 인용한 기관·자료 이름. 나머지는 빈 문자열
    source: str = ""

    #: 왜 검토 대기로 갔나. 제자리를 찾았으면 빈 문자열
    why: str = ""


class NodeExtractor(Protocol):
    """**포트.** 제공자가 정해지면 이것만 만족시키면 된다(ADR-0031 그대로).

    `known` 은 **인스턴스 이름 때문에 남아 있다.** 자리표가 고정이라 번호로 오는 것은
    갈릴 일이 없지만, `Competitor/{업체명}` 의 이름은 여전히 문서에서 나와서 같은
    업체가 두 자리로 갈릴 수 있다. 그 목록은 DB 에서 오고, 포트는 DB 를 모르므로
    인자로 받는다.
    """

    #: `stub/v1` · `llm/<모델>`. 어느 추출기가 만든 값인지 행에 남는다
    name: str

    def extract(self, view: FileView, known: Known) -> list[NodeFact]: ...


# ══════════════════════════════════════════════════════════════════
# 스텁 — 픽스처가 정답지다 (ADR-0031)
# ══════════════════════════════════════════════════════════════════
class StubNodes:
    """코퍼스에서 손으로 옮긴 사실을 돌려준다. **픽스처 밖에는 안 돈다.**"""

    name = "stub/v1"

    def __init__(self, facts_path: Path | None = None) -> None:
        self._path = facts_path or settings.wiki_stub_facts
        self._by_sha: dict[str, list[NodeFact]] | None = None

    @property
    def known(self) -> frozenset[str]:
        return frozenset(self._load())

    def extract(self, view: FileView, known: Known | None = None) -> list[NodeFact]:
        table = self._load()
        if view.sha256 not in table:
            raise UnknownFile(
                f"{view.filename}: 스텁이 모르는 파일이에요. "
                f"실제 추출기(LLM)가 아직 없어서 픽스처 {len(table)}건만 처리할 수 있어요 "
                f"— sha256 {view.sha256[:12]}"
            )
        return table[view.sha256]

    def _load(self) -> dict[str, list[NodeFact]]:
        if self._by_sha is not None:
            return self._by_sha
        if not self._path.exists():
            raise UnknownFile(
                f"스텁 사실 표가 없어요 — {self._path}. "
                "이 표는 코퍼스에서 손으로 옮긴 것이라 레포 밖에서는 돌지 않아요"
            )
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._by_sha = {
            e["sha256"]: [f for f in (from_fixture(d) for d in e["facts"]) if f is not None]
            for e in raw["files"]
        }
        return self._by_sha


def from_fixture(d: dict) -> NodeFact | None:
    """픽스처 사실 하나를 트랙 A 모양으로. **트랙 B 것이면 `None`.**

    `kind == "value"` 인데 항목 이름이 매칭 정보 열다섯 중 하나면 저쪽 것이라 여기서
    안 낸다 — 그 판정은 `profile.key_of` 하나가 한다. 나머지는 **값으로** 앉는다.

    **픽스처의 `qualifier` 는 안 읽는다**(ADR-0059) — 트랙 A 에 그 칸이 없다.

    등급은 전부 `1차` 다. **픽스처가 회사 자기 문서에서 옮긴 것이라서** 그렇고,
    스텁이 등급을 판정한다는 뜻이 아니다.
    """
    kind = d.get("kind")
    text = (d.get("text") or "").strip()
    anchor = (d.get("anchor") or "").strip()

    if kind == "value":
        if profile.key_of(d.get("key")) is not None:
            return None  # 트랙 B 가 낸다
        return NodeFact(
            path=spots.REVIEW.path,
            anchor=anchor,
            text=text,
            key=bare_key(d.get("key")) or None,
            value=d.get("value"),
            as_of=_date(d.get("as_of")),
            grade="1차",
            why=f"자리표에 없는 항목 — {d.get('key')!r}",
        )

    topic = d.get("topic") or ""
    path = FIXTURE_PATH.get(topic)
    why = "" if path else (FIXTURE_GAP.get(topic) or f"자리가 없는 topic — {topic}")
    return NodeFact(
        path=path or spots.REVIEW.path,
        anchor=anchor,
        text=text,
        #: **픽스처에는 하나도 없다**(event 64건 전부). 읽어 두는 것은 LLM 쪽과 규칙을
        #: 같게 두려는 것이지 스텁이 이력을 낼 수 있다는 뜻이 아니다
        as_of=_date(d.get("as_of")),
        grade="1차",
        why=why,
    )


#: 이름에서 뗄 시점 표현. **`as_of` 칸이 따로 있는데도 모델이 이름에 박는다** —
#: 한정어 시절 71종 중 22종이 그랬고 프롬프트로 두 번 막아 봤지만 두 번 다 돌아왔다.
#:
#: 떼면 `2024년 매출액` 과 `2025년 매출액` 이 **같은 이름**이 되고 `as_of` 가 가른다 —
#: 그래야 한 자리에 이력으로 쌓인다. `2024년 구독 매출` 은 `구독 매출` 이 되어
#: `매출액` 과 **여전히 다르다.**
_PERIOD = re.compile(
    r"(\d{4}\s*년도?|\d{4}-\d{2}(-\d{2})?|[1-4]\s*분기|[1-4]Q|FY\s*\d{2,4})"
    r"\s*(말|초|상반기|하반기)?"
)


def bare_key(key: str | None) -> str:
    """이름에서 시점을 뗀다. **전부 떼고 나면 원래 이름을 돌려준다.**

    `2024년` 처럼 시점뿐인 이름을 빈 문자열로 만들면 그 사실이 이름을 잃는다 —
    지우는 것보다 안 뗀 채 두는 것이 낫다.
    """
    bare = " ".join(_PERIOD.sub(" ", key or "").split()).strip()
    return bare or (key or "").strip()


def _date(s: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(s) if s else None
    except ValueError:
        # 날짜가 아니면 시점 없는 값으로 둔다. **지어내지 않는다**
        return None


# ══════════════════════════════════════════════════════════════════
# LLM 추출기 (ADR-0037)
# ══════════════════════════════════════════════════════════════════
_SYSTEM = """\
너는 한국 창업기업 문서를 읽고 **그 회사에 대한 사실**을 위키 자리표에 앉히는 추출기다.
요약하지 말고 문서에 적힌 것만 낸다.

## 자리표 — 이 밖으로 나가지 않는다

{spots}

## 답하는 법 — **번호로 답한다**

`spot` 에 위 번호를 적는다. **경로를 다시 쓰지 마라.**

`{{…}}` 가 있는 자리는 `instance` 에 그 이름을 채운다. 이름은 **문서에서 읽는다.**

    [18] Competitor/{{업체명}}              instance="배달의민족"
    [33] Custom/특허/{{상태}}-{{번호}}          instance="등록-10-2025-0114882"
    [23] Customer/인터뷰/{{세그먼트}}-{{인원}}-{{시점}}  instance="취준생-59명-2026Q1"
    [11] Product/{{서비스명}}/화면/{{화면명}}   instance="다시로/주문화면"

**구멍이 둘인 자리는 `/` 로 잇는다.** 위 `[11]` 이 그 하나뿐인 자리다.

`{{…}}` 가 없는 자리는 `instance` 를 비운다.

**`{{…}}` 가 있는 자리를 골랐으면 `instance` 를 반드시 채운다.** 비우면 그 사실은
자리를 잃고 검토 대기로 간다 — 문서에 서비스 이름이 한 번밖에 안 나와도 그것을 쓴다.

**이름에 값과 기준을 넣어라.** `인터뷰` 가 아니라 `취준생-59명-2026Q1` 이다 — 열지
않고도 인원수와 시점을 알 수 있어야 한다. **실명을 쓴다.** 경쟁사를 A사·B사로 가리지
마라.

## 이 자리에 이미 있는 이름

{known}

같은 대상이면 **그 자리에 이미 있는 이름을 그대로 쓴다.** `㈜다시로` 와 `다시로` 를
섞으면 한 업체가 자리 둘로 갈리고, 사용자는 어느 쪽이 진짜인지 알 방법이 없다.

**다른 자리의 이름을 가져다 쓰지 마라.** 위 목록은 자리마다 따로 적혀 있다 — 특허
번호를 페르소나 이름으로, 인터뷰 이름을 인증 이름으로 쓰면 그 사실은 엉뚱한 데
앉고 아무도 왜 거기 있는지 못 찾는다.

## 자리를 못 고르겠으면

**억지로 끼워 맞추지 마라.** `spot` 을 비우면 검토 대기로 가고 사람이 본다.
버려지지 않는다. **표에 없는 번호를 지어내지 마라** — 고를 수 있는 것은 위 자리표의
번호뿐이고, 그 밖의 번호는 자리를 안 고른 것과 같다.

## 서술인가 값인가 — **「이름을 붙일 수 있나」로 가른다**

- **값** — 붙일 수 있다. `key` 에 그 이름, `value` 에 값 하나, `text` 에 사람이 읽는 문장
- **서술** — 못 붙인다. `key` 와 `value` 를 **둘 다 비우고** `text` 만 낸다

```
자본금 1억 2,000만원          → 값    key="자본금"        value="120000000"
2025년 매출 8,640만원         → 값    key="매출"          value="86400000"
시드 라운드 3억원 유치         → 값    key="시드 조달액"    value="300000000"
경영 1명(대표이사)            → 값    key="경영 인원"      value="1"
개발 8명·영업 4명·운영 2명     → 서술  값이 하나가 아니다
진입 경로는 지역 상인회와 도매  → 서술  셀 것이 없다
```

**세는 것·재는 것은 거의 값이다.** 매장 수·인원·금액·비율·건수를 서술로 내면 그 값이
시간에 따라 어떻게 변했는지 아무도 못 본다.

한 문장이 둘 다이면 **사실을 둘로 낸다.**

## key — 값의 이름

**자리 이름을 되풀이하지 마라.** `Company/팀` 에 `key="팀"` 은 아무것도 안 말한다 —
`경영 인원`·`개발 인원` 처럼 **그 자리 안에서 무엇의 값인지**를 적는다.

**구체적으로 적는다.** 같은 자리에 비슷한 값이 여럿이면 이름으로 갈라라.

    조달액 (X)  →  시드 조달액 · 브리지 조달액 · 정책자금 조달액
    요금 (X)    →  기본 요금제 · 연동 요금제 · 통합 요금제

**시점을 이름에 넣지 마라.** `2024년 매출액` 이 아니라 `매출액` 이고 연도는 `as_of` 에
간다 — 넣으면 2024년 것과 2025년 것이 다른 이름이 되어 이력이 안 쌓인다.

## value — 숫자만 정규화한다

- 금액: `24,100천원` → `24100000` · `2,410만원` → `24100000` · `3억원` → `300000000`
- 날짜: `2024. 3. 5.` → `2024-03-05` · `2024년03월11일` → `2024-03-11`
- 수: `15명` → `15`

**이름·주소·등록번호는 숫자가 아니다. 표기를 바꾸지 마라.**
문서가 쓴 표현은 `text` 에 남긴다. **단위·쉼표·한글 수사를 `value` 에 넣지 마라.**

## text — 사람이 읽는 문장

값이든 서술이든 **문장 하나**를 낸다. 값일 때는 그 값을 품은 문장이다.

```
자본금은 1억 2,000만원이다.
2026년 1월 기준 유료 매장은 102곳이다.
```

**문서가 쓴 표현을 살린다.** `2,410만원` 을 문장에서까지 `24100000` 으로 고쳐 쓰지
마라 — 사용자가 자기 문서에서 못 찾는 문장이 된다. 고친 값은 `value` 에만 있다.

## anchor — 가장 중요하다

`anchor` 는 **원문에서 그대로 복사한 조각**이다. 한 글자도 바꾸지 마라.
띄어쓰기·조사·괄호·숫자 표기를 손대면 그 사실은 근거를 잃고 **버려진다.**
10~60자 정도로, 그 사실이 실제로 적힌 자리를 잡아라.

## as_of — 언제 기준 사실인가

`2024년 매출` 이면 `2024-12-31` · `2025. 08. 기준` 이면 `2025-08-31`.
값 옆에 더 구체적인 날짜가 있으면 그쪽이 이긴다.
어디에도 날짜가 없으면 비운다. **지어내지 마라.**

**서술에도 채운다.** 시점이 분명하면 값이든 서술이든 넣는다 — 채워야 같은 자리에
이력으로 쌓인다.

## grade — 이 사실을 어디서 얻었나

- `1차` — 회사 문서가 스스로 말한 것. 사업계획서·IR·재무제표에 적힌 우리 값
- `2차` — 문서가 **외부 출처를 밝히고** 인용한 것. `source` 에 그 기관·자료 이름을 적는다
- `가정` — 문서가 추정·전망·목표로 적은 것. 「예상」·「목표」·「전망」·「추정」·「(E)」

확신이 없으면 `1차` 다. **`source` 는 `2차` 일 때만 채운다** — 출처를 안 밝힌 인용은
`1차` 이고, 거기에 기관 이름을 지어 넣으면 심사에서 그 값이 통째로 깨진다.

## 안 하는 것

- 문서에 없는 것을 채우지 않는다. 추측·일반 상식 금지
- 목차·머리말·쪽 번호·표 머리글만 있는 조각에서는 아무것도 안 낸다
- 신뢰도 점수를 매기지 않는다
"""


def known_names(known: Known) -> str:
    """이미 쓰인 인스턴스 이름을 **자리별로 묶어서** 낸다.

    **경로를 통째로 안 보인다.** 2026-08-22 실측에서 이 목록이 평평한 경로 목록이라
    모델이 이름을 자리 건너 베꼈다 — `Customer/페르소나/출원-10-2025-0114882` ·
    `Custom/인증/성남·용인 소상공인-30명-…` · **`Competitor/검토 대기`**(오류 통
    이름을 업체명으로 썼다). 어느 자리의 이름인지 밝히면 그 길이 막힌다.

    **고정 자리는 안 싣는다.** 거기는 이름을 지을 일이 없어서 실어 봐야 프롬프트만
    길어진다. **검토 대기도 안 싣는다** — 자리 이름이 아니라 오류 통이다.
    """
    by_spot: dict[str, list[str]] = {}
    for path in known.spots.names:
        spot = spots.spot_of(path)
        if spot is None or spot.fixed or spot.path == spots.REVIEW.path:
            continue
        if name := spot.instance(path):
            by_spot.setdefault(spot.path, []).append(name)

    if not by_spot:
        return "(아직 없다)"
    return "\n".join(
        f"- `{tpl}` — {' · '.join(sorted(set(names)))}" for tpl, names in sorted(by_spot.items())
    )


def system_prompt(known: Known) -> str:
    """**자리표는 상수이고 「이미 있는 이름」만 회사마다 다르다.**

    **번호가 붙은 목록은 자리표 하나뿐이다.** 둘이면 모델이 이어 세어서 표 밖 번호를
    낸다 — `port.Roster.render` 첫 문단.
    """
    return _SYSTEM.format(spots=spots.render(), known=known_names(known))


#: **`spot` 이 정수 하나다.** 자리 마흔여섯을 문자열 enum 으로 실으면 모델이 경로를
#: 다시 쓰게 되고, 한 글자만 달라도 자리가 갈린다 — 번호로 받는 이유가 그것이다.
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["facts"],
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "spot", "instance", "key", "value",
                    "text", "as_of", "grade", "source", "anchor",
                ],
                "properties": {
                    "spot": {"type": ["integer", "null"]},
                    "instance": {"type": ["string", "null"]},
                    #: **`kind` 를 안 받는다.** 있으면 「값이라고 했는데 값이 없는」
                    #: 상태가 표현된다 — 둘 다 찼으면 값이고 아니면 서술이다
                    "key": {"type": ["string", "null"]},
                    "value": {"type": ["string", "null"]},
                    "text": {"type": "string"},
                    "as_of": {"type": ["string", "null"]},
                    "grade": {"type": "string", "enum": ["1차", "2차", "가정"]},
                    "source": {"type": ["string", "null"]},
                    "anchor": {"type": "string"},
                },
            },
        }
    },
}


@dataclass(slots=True)
class LlmNodes:
    """청크를 LLM 에 넘겨 자리 사실을 받는다 (ADR-0037).

    **자기 출력을 원문에 대조한다.** 앵커가 원문에 없으면 그 사실을 버리고 센다 —
    `build.py` 가 한 번 더 찾지만, 여기서 걸러야 무엇이 왜 사라졌는지 남는다.
    """

    client: object | None = None
    #: 앵커가 원문에 없어 버린 사실. **조용히 사라지면 '아무것도 안 나온 것' 과
    #: 구분이 안 된다**(ADR-0037 결정 5)
    dropped: list[tuple[str, str]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"llm/{self._c().model}"

    def _c(self):  # noqa: ANN202
        """**함수 안에서 임포트한다.** 최상단에 두면 `import finnect.api.app` 이
        `wiki.service → build → extract_nodes → llm` 을 타고 httpx 를 끌고 와
        **로컬은 통과하고 배포본만 죽는다**(CLAUDE.md 함정 · `tests/test_admin_api.py`).
        """
        from finnect import llm

        if self.client is None:
            self.client = llm.client()
        return self.client

    def extract(self, view: FileView, known: Known | None = None) -> list[NodeFact]:
        known = known or Known()
        out = self._c().json(
            system=system_prompt(known),
            user=_user_prompt(view),
            schema=SCHEMA,
            schema_name="wiki_spots",
        )
        #: **갈래를 뜬다.** 부르는 쪽의 `Known` 을 늘리지 않는다 — 이 호출에서만 자란다
        seen = known.spots.copy()

        facts: list[NodeFact] = []
        for d in out.get("facts") or []:
            anchor = (d.get("anchor") or "").strip()
            if not port.anchored(view, anchor):
                self.dropped.append((view.filename, anchor[:60]))
                continue
            facts.append(_resolve(d, anchor, seen))
        return facts


def _user_prompt(view: FileView) -> str:
    body = "\n\n".join(f"[{i}] {t}" for i, t in view.chunks)
    return f"파일 이름: {view.filename}\n\n--- 원문 ---\n{body}"


def _resolve(d: dict, anchor: str, seen: port.Roster) -> NodeFact:
    """번호와 인스턴스 이름을 자리 하나로 푼다.

    **번호가 표 밖이면 검토 대기다.** 없는 번호에 자리를 지어 주면 그 사실이 엉뚱한
    데 앉고, 앉은 뒤에는 왜 거기 있는지 아무도 못 찾는다.
    """
    text = (d.get("text") or "").strip()
    path, why = _path(d, seen)
    grade = d.get("grade") if d.get("grade") in ("1차", "2차", "가정") else "1차"
    #: **`source` 는 `2차` 일 때만 산다.** 다른 등급에 기관 이름이 붙으면 프론트매터가
    #: 「이 값은 KOSIS 것」이라고 말하는데 문서는 그런 적이 없게 된다
    source = ((d.get("source") or "").strip() if grade == "2차" else "")

    #: **둘 다 있어야 값이다.** 이름만 오면 무엇의 값인지 알 수 없고, 값만 오면
    #: 화면에 이름 없는 숫자가 뜬다 — 어느 쪽도 반쪽이라 서술로 떨어뜨린다
    key = bare_key(d.get("key"))
    value = (d.get("value") or "").strip()
    paired = bool(key and value)

    return NodeFact(
        path=path,
        anchor=anchor,
        text=text,
        key=key if paired else None,
        value=value if paired else None,
        as_of=_date(d.get("as_of")),
        grade=grade,
        source=source,
        why=why,
    )


def _path(d: dict, seen: port.Roster) -> tuple[str, str]:
    """자리 경로와 「왜 검토 대기인가」. **자리를 못 정해도 버리지 않는다.**"""
    spot = spots.by_number(d.get("spot"))
    if spot is None:
        return spots.REVIEW.path, f"자리를 못 골랐음 — spot={d.get('spot')!r}"

    path = spot.fill(d.get("instance"))
    if not path:
        #: 인스턴스가 필요한 자리인데 이름이 안 왔다. **`{업체명}` 이라는 리터럴 폴더를
        #: 만들지 않는다** — 그 이름이 그대로 사용자가 보는 자리가 된다
        return spots.REVIEW.path, f"{spot.path} 에 쓸 이름이 안 왔어요"
    return seen.fold(path), ""


def get_extractor() -> NodeExtractor:
    """설정이 고른 추출기. **트랙 B 와 같은 설정을 읽는다**(`WIKI_EXTRACTOR`).

    **`llm` 은 키가 있어야 돈다.** 없으면 `llm.MissingKey` 로 멈춘다 — 조용히 스텁으로
    물러나지 않는다(ADR-0037 결정 4).
    """
    choice = settings.wiki_extractor
    if choice == "stub":
        return StubNodes()
    if choice == "llm":
        return LlmNodes()
    raise NotImplementedError(
        f"추출기 '{choice}' 를 몰라요. `stub` 또는 `llm` 이에요 — ADR-0037"
    )
