"""트랙 A — 노드 추출(ADR-0056 결정 1·2 · plan/22 T-0126).

묻는 것은 **「이 문서가 우리 사업에 대해 뭐라고 말하나」** 하나다. 질문 수를 우리가
모르고 **문서가 정한다** — 그래서 넓게 뽑아야 하고, 정답지가 없어서 정확도를 못 잰다.
잘한 기준은 「풍부한가」이고 실패하면 위키가 얇아진다.

**트랙 B 와 호출을 나눈 이유가 이것이다.** 저쪽은 열넷 고정이라 빠뜨리면 안 되고,
여기는 열려 있어서 넓게 뽑아야 한다. 튜닝 방향이 반대라 한 프롬프트에 섞으면 둘 다
어중간해진다.

    category   Company · Custom/특허        열 중 하나. **이것만 고정이다**
      node     팀 · 등록-10-2025-0114882   .md 한 장 · 그래프 점 하나
        key    직원 수 · 팀 구성             VALUE 또는 EVENT

## 갈라짐은 `port.Roster` 가 막는다

번호로 답하게 하고, 그래도 새 이름이 오면 정규화 정확 일치로 접는다(T-0127).
**유사도를 안 쓴다.** 자세한 것은 `port.py` 첫 문단.

## 앵커 규칙은 안 바뀐다

원문에서 그대로 복사 · 못 찾으면 버린다(ADR-0014). 트랙이 갈려도 여기는 같다 —
근거 없는 값을 위키에 세우지 않는 것이 트랙의 문제가 아니라 제품의 문제라서다.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from finnect.config import settings
from finnect.wiki import port, profile, tree
from finnect.wiki.port import FileView, Known, UnknownFile

#: 픽스처의 옛 topic → 노드 경로. **스텁 전용 번역표다.**
#:
#: 2026-08-22 까지 이 표가 `tree.EVENT_PATH` 에 있었고 **제품이 라우팅에 썼다.** 지금은
#: LLM 이 경로를 직접 내므로 제품 코드에 이 표가 없다 — 남은 쓰임은 `facts.json` 의
#: 옛 어휘를 새 경로로 옮기는 것뿐이다.
#:
#: 마이그레이션 `c7f2a91b4d38` 이 쓴 것과 **같은 표여야 한다.** 갈리면 새로 세운 위키와
#: 옮겨진 위키가 다른 자리에 앉는다.
FIXTURE_PATH: dict[str, str] = {
    "vision": "Company/비전",
    "team": "Company/팀",
    "region_link": "Company/지역관계",
    "service_overview": "Product/소개",
    "service_feature": "Product/기능",
    "service_differentiator": "Product/차별점",
    "development_status": "Product/개발현황",
    "market_size": "Market/시장규모",
    "market_trend": "Market/트렌드",
    "competitor": "Competitor/경쟁사",
    "target_customer": "Customer/타깃고객",
    "customer_problem": "Customer/고객문제",
    "customer_evidence": "Customer/검증",
    "revenue_model": "BusinessModel/수익모델",
    "pricing": "BusinessModel/가격정책",
    "go_to_market": "BusinessModel/판매전략",
    "revenue": "Financial/매출",
    "cost": "Financial/비용",
    "funding": "Financial/자금계획",
    "patent": "Custom/특허",
    "certification": "Custom/인증",
    "technology": "Custom/기술",
    "roadmap": "Plan/일정",
}

#: 픽스처가 쓸 수 있는 topic. **자유 생성 금지**(구상도 ④).
#:
#: `company_profile` 과 `application_history` 는 매칭 정보의 재료라 노드 자리가 없다 —
#: 서술로 오면 `Custom/검토 대기` 로 간다.
FIXTURE_TOPICS: frozenset[str] = frozenset(FIXTURE_PATH) | {
    "company_profile",
    "application_history",
}


@dataclass(frozen=True, slots=True)
class NodeFact:
    """노드에 앉을 사실 하나. **자리를 이미 알고 나온다.**

    2026-08-22 까지 추출기가 `topic` 을 내고 `merge.place` 가 표를 봐서 자리를 정했다.
    이제 **추출기가 경로를 낸다**(ADR-0056 결정 2) — 그 표를 우리가 안 들고 있는 것이
    이 결정의 요점이라, 라우팅 단계가 통째로 없어졌다.
    """

    #: 노드 경로. `Company/팀` · `Custom/특허/등록-10-2025-0114882`
    path: str
    #: 이 노드 안에서 이 사실을 부르는 이름. **라벨이자 병합 열쇠다**(결정 3)
    key: str
    #: `value` 또는 `event`. **병합 규칙을 이게 정한다**
    kind: str
    #: 원문에 그대로 있는 조각. **이걸 담은 청크가 근거가 된다**
    anchor: str
    #: 사람이 읽는 문장. `event` 는 이게 내용이고 `value` 는 값의 설명이다
    text: str = ""

    # --- kind == "value" 일 때만 ---
    #: **정규화된 값이다.** 문서가 쓴 표현은 `text` 에 남는다
    value: str | None = None
    as_of: dt.date | None = None
    #: 같은 key 안의 종류. `시드` · `예비창업패키지`
    qualifier: str | None = None

    #: 왜 검토 대기로 갔나. 제자리를 찾았으면 빈 문자열
    why: str = ""


class NodeExtractor(Protocol):
    """**포트.** 제공자가 정해지면 이것만 만족시키면 된다(ADR-0031 그대로).

    `known` 이 늘었다. 지금 있는 노드·key·한정어를 번호와 함께 프롬프트에 실어야
    갈라짐을 막을 수 있고(ADR-0056 결정 6), **그 목록은 DB 에서 온다.** 포트가 DB 를
    모르는 채로 받으려면 인자로 받는 수밖에 없다.
    """

    #: `stub/v1` · `llm/<모델>`. 어느 추출기가 만든 값인지 행에 남는다
    name: str

    def extract(self, view: FileView, known: Known) -> list[NodeFact]: ...


# ══════════════════════════════════════════════════════════════════
# 스텁 — 픽스처가 정답지다 (ADR-0031)
# ══════════════════════════════════════════════════════════════════
class StubNodes:
    """코퍼스에서 손으로 옮긴 사실을 돌려준다. **픽스처 밖에는 안 돈다.**

    `facts.json` 은 **옛 어휘(`topic`)로 적혀 있고 그대로 둔다.** 앵커가 원문에 한 글자도
    안 틀리게 들어 있어야 하는 표라(`tests/test_wiki_extract.py`) 어휘를 바꾸려면 118건을
    다시 손으로 옮겨야 하고, 그러면 **정답지가 정답지가 아니게 된다.** 번역은 여기서 한다.

    **`key` 가 옛 `fact_key` 그대로다.** ADR-0056 결정 3 은 EVENT 의 key 도 사람이 읽는
    말이어야 한다고 적었는데(`pilot_retention_34_51` → `재구매율 상승`), 그 한국어 이름은
    코퍼스에 없는 값이라 여기서 지어내지 않는다 — 사람이 읽는 key 는 LLM 이 낸다.
    """

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

    `kind == "value"` 인데 항목 이름이 매칭 정보 열넷 중 하나면 저쪽 것이라 여기서
    안 낸다 — 그 판정은 `profile.key_of` 하나가 한다.

    이름을 모르는 값(`업력`)은 **버리지 않고 검토 대기 노드에 값으로 앉힌다.** 옛
    미분류는 트리에 자리가 없어서 화면 어디에도 안 나왔다.
    """
    kind = d.get("kind")
    text = (d.get("text") or "").strip()
    anchor = (d.get("anchor") or "").strip()

    if kind == "value":
        if profile.key_of(d.get("key")) is not None:
            return None  # 트랙 B 가 낸다
        return NodeFact(
            path=tree.REVIEW_PATH,
            key=(d.get("key") or "").strip() or _fallback_key(text),
            kind="value",
            anchor=anchor,
            text=text,
            value=d.get("value"),
            as_of=_date(d.get("as_of")),
            qualifier=d.get("qualifier"),
            why=f"모르는 항목 이름 — {d.get('key')!r}",
        )

    topic = d.get("topic") or ""
    path = FIXTURE_PATH.get(topic)
    return NodeFact(
        path=path or tree.REVIEW_PATH,
        key=(d.get("fact_key") or "").strip() or _fallback_key(text),
        kind="event",
        anchor=anchor,
        text=text,
        #: **픽스처에는 하나도 없다**(event 64건 전부). 읽어 두는 것은 LLM 쪽과 규칙을
        #: 같게 두려는 것이지 스텁이 이력을 낼 수 있다는 뜻이 아니다 — 스텁으로는
        #: ADR-0057 의 이력 경로가 안 밟힌다
        as_of=_date(d.get("as_of")),
        why="" if path else f"자리가 없는 topic — {topic}",
    )


def _fallback_key(text: str) -> str:
    """key 가 안 왔을 때. **문장 자체가 키라 안 묶인다** — 잘못 묶는 것보다 낫다."""
    head = (text or "").strip().split("\n", 1)[0].strip()
    return head[:60] or "사실"


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
너는 한국 창업기업 문서를 읽고 **그 회사에 대한 사실**을 노드 트리에 앉히는 추출기다.
요약하지 말고 문서에 적힌 것만 낸다.

## 트리는 세 층이고 고정은 맨 위 하나뿐이다

    category   회사 · 지식 재산            아래 열 중 하나. **이것만 고정이다**
      node     팀 · 등록-10-2025-0114882   .md 한 장 · 그래프 점 하나
        key    직원 수 · 팀 구성             이 사실을 부르는 이름

### category — 아래 열 중 하나를 고른다

{categories}

아홉에 안 맞는 것은 **전부 `Custom` 으로 온다.** 억지로 끼워 맞추지도, 버리지도 마라.

## 지금 있는 노드

{nodes}

## 지금 있는 key

{keys}

## 지금 있는 한정어

{qualifiers}

## 답하는 법 — **번호로 답한다**

같은 자리면 번호를 적는다. **경로를 다시 쓰지 마라** — 한 글자만 달라도 자리가 갈라져서
같은 얘기가 노드 둘에 흩어지고, 사용자는 어느 쪽이 진짜인지 알 방법이 없다.

    있으면  node_ref=3     node_category=null   node_path=null
    없으면  node_ref=null  node_category="Market"  node_path="시장규모"

`node_path` 는 **category 아래의 경로**다. `Market/시장규모` 가 아니라 `시장규모` 다.
깊이는 자유이고 마디를 `/` 로 잇는다 — `특허/등록-10-2025-0114882`.

`key` 와 `한정어`도 같은 장치다(`key_ref`/`key_new` · `qualifier_ref`/`qualifier_new`).
번호가 있으면 번호가 이긴다.

## kind — value 인가 event 인가

**「이 사실을 숫자·날짜·이름 하나로 적을 수 있나」로 가른다.**

- `value` — 적을 수 있다. `value` 에 그 값 하나, `text` 에 사람이 읽는 문장
- `event` — 못 적는다. `text` 가 내용이고 `value` 는 비운다

```
유료 매장 102곳 (2026년 1월)        → value   value="102"      as_of=2026-01-31
2025년 매출 8,640만원               → value   value="86400000" as_of=2025-12-31
특허 출원 10-2025-0114882           → value   value="10-2025-0114882"
개발 8명·영업 4명·운영 2명·경영 1명   → event   값이 하나가 아니다
진입 경로는 지역 상인회와 도매 유통사  → event   셀 것이 없다
```

**세는 것·재는 것은 거의 value 다.** 매장 수·인원·금액·비율·건수를 `event` 로 내면
그 값이 시간에 따라 어떻게 변했는지 아무도 못 본다.

한 문장이 둘 다이면 **사실을 둘로 낸다.**

## key 는 사람이 읽는 말이다

`pilot_retention_34_51` 이 아니라 `재구매율 상승` 이다. 화면에 그대로 뜨고, 같은 노드
안에서 **같은 key 면 같은 사실**이라 근거만 쌓인다 — 같은 내용이 문서 여럿에 다른
문장으로 있으면 같은 key 를 줘라. 확신이 없으면 새 key 를 만든다. 잘못 묶는 것보다
안 묶는 것이 낫다.

## anchor — 가장 중요하다

`anchor` 는 **원문에서 그대로 복사한 조각**이다. 한 글자도 바꾸지 마라.
띄어쓰기·조사·괄호·숫자 표기를 손대면 그 사실은 근거를 잃고 **버려진다.**
10~60자 정도로, 그 사실이 실제로 적힌 자리를 잡아라.

## value — 숫자만 정규화한다 (value 일 때만)

- 금액: `24,100천원` → `24100000` · `2,410만원` → `24100000` · `3억원` → `300000000`
- 날짜: `2024. 3. 5.` → `2024-03-05` · `2024년03월11일` → `2024-03-11`
- 수: `15명` → `15`

**이름·주소·등록번호는 숫자가 아니다. 표기를 바꾸지 마라.**
문서가 쓴 표현은 `text` 에 남긴다. **단위·쉼표·한글 수사를 value 에 넣지 마라.**

## as_of — 언제 기준 사실인가 (value · event 둘 다)

`2024년 매출` 이면 `2024-12-31` · `2025. 08. 기준` 이면 `2025-08-31`.
값 옆에 더 구체적인 날짜가 있으면 그쪽이 이긴다.
어디에도 날짜가 없으면 비운다. **지어내지 마라.**

**서술에도 채운다.** `2026년 8월 기준 개발 8명, 영업 4명` 은 값이 하나가 아니라 `event`
이지만 시점은 분명히 있다. 시점을 채우면 같은 `key` 아래 이력으로 쌓인다 —
**`팀 구성_2026_08` 처럼 시점을 이름에 박지 마라.** key 는 `팀 구성` 하나면 된다.

## 안 하는 것

- 문서에 없는 것을 채우지 않는다. 추측·일반 상식 금지
- 목차·머리말·쪽 번호·표 머리글만 있는 조각에서는 아무것도 안 낸다
- 신뢰도 점수를 매기지 않는다
"""


def _categories() -> str:
    """`tree.CATEGORIES` 에서 만든다. **손으로 적으면 표와 어긋난다.**"""
    return "\n".join(f"- `{k}` {v}" for k, v in tree.CATEGORIES.items())


def system_prompt(known: Known) -> str:
    """**현재 상태가 프롬프트에 들어간다**(ADR-0056 결정 6).

    회사마다 다르고 파일마다 자란다 — 상수가 아니다.
    """
    return _SYSTEM.format(
        categories=_categories(),
        nodes=known.nodes.render(),
        keys=known.keys.render(),
        qualifiers=known.qualifiers.render(),
    )


#: **`node_new` 를 객체로 안 받고 두 칸으로 편다.** `strict: true` 스키마에서
#: nullable 한 중첩 객체(`{"type": ["object", "null"]}`)는 제공자가 받아 주는지가
#: 불확실하고, 여기서 틀리면 호출 전체가 400 이다. 뜻은 같다 —
#: `node_category` 와 `node_path` 가 함께 `node_new` 다.
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
                    "node_ref", "node_category", "node_path",
                    "key_ref", "key_new",
                    "qualifier_ref", "qualifier_new",
                    "kind", "text", "value", "as_of", "anchor",
                ],
                "properties": {
                    "node_ref": {"type": ["integer", "null"]},
                    "node_category": {
                        "type": ["string", "null"],
                        "enum": [*tree.CATEGORIES, None],
                    },
                    "node_path": {"type": ["string", "null"]},
                    "key_ref": {"type": ["integer", "null"]},
                    "key_new": {"type": ["string", "null"]},
                    "qualifier_ref": {"type": ["integer", "null"]},
                    "qualifier_new": {"type": ["string", "null"]},
                    "kind": {"type": "string", "enum": ["value", "event"]},
                    "text": {"type": ["string", "null"]},
                    "value": {"type": ["string", "null"]},
                    "as_of": {"type": ["string", "null"]},
                    "anchor": {"type": "string"},
                },
            },
        }
    },
}


@dataclass(slots=True)
class LlmNodes:
    """청크를 LLM 에 넘겨 노드 사실을 받는다 (ADR-0037).

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
            schema_name="wiki_nodes",
        )
        #: **갈래를 뜬다.** 부르는 쪽의 `Known` 을 늘리지 않는다 — 이 호출에서만 자란다
        nodes, keys, quals = known.nodes.copy(), known.keys.copy(), known.qualifiers.copy()

        facts: list[NodeFact] = []
        for d in out.get("facts") or []:
            anchor = (d.get("anchor") or "").strip()
            if not port.anchored(view, anchor):
                self.dropped.append((view.filename, anchor[:60]))
                continue
            facts.append(_resolve(d, anchor, nodes, keys, quals))
        return facts


def _user_prompt(view: FileView) -> str:
    body = "\n\n".join(f"[{i}] {t}" for i, t in view.chunks)
    return f"파일 이름: {view.filename}\n\n--- 원문 ---\n{body}"


def _resolve(
    d: dict, anchor: str, nodes: port.Roster, keys: port.Roster, quals: port.Roster
) -> NodeFact:
    """번호와 새 이름을 자리 하나로 푼다. **여기가 코드 그물이다**(T-0127).

    번호가 이긴다. 번호가 없거나 범위 밖이면 새 이름을 쓰고, 그 새 이름도 정규화해서
    기존과 정확히 같으면 조용히 기존으로 돌린다.
    """
    kind = d.get("kind") if d.get("kind") in ("value", "event") else "event"
    text = (d.get("text") or "").strip()

    path, why = _path(d, nodes)
    #: `_fallback_key` 가 최소 `사실` 을 돌려주므로 `fold` 결과가 빌 수 없다
    key = keys.fold(
        keys.ref(d.get("key_ref")) or (d.get("key_new") or "").strip() or _fallback_key(text)
    )
    qualifier = quals.fold(quals.ref(d.get("qualifier_ref")) or d.get("qualifier_new") or "")

    return NodeFact(
        path=path,
        key=key,
        kind=kind,
        anchor=anchor,
        text=text,
        # **서술에 값 필드가 붙으면 병합 키가 어긋난다**
        value=(d.get("value") or None) if kind == "value" else None,
        qualifier=(qualifier or None) if kind == "value" else None,
        #: **시점은 서술도 받는다**(ADR-0057 결정 2). 값 필드와 달리 병합 키의 일부라
        #: 여기서 떨어뜨리면 이력이 안 서고 추출기가 시점을 key 이름에 박게 된다
        as_of=_date(d.get("as_of")),
        why=why,
    )


def _path(d: dict, nodes: port.Roster) -> tuple[str, str]:
    """노드 경로와 「왜 검토 대기인가」. **자리를 못 정해도 버리지 않는다.**"""
    got = nodes.ref(d.get("node_ref"))
    if got is not None:
        return got, ""

    cat = (d.get("node_category") or "").strip()
    rest = (d.get("node_path") or "").strip()
    if not cat and not rest:
        return nodes.fold(tree.REVIEW_PATH), "자리를 안 골랐음"
    #: **`clean` 이 카테고리 밖을 `Custom` 밑으로 민다.** LLM 이 enum 을 어겨도 안 사라진다
    return nodes.fold(tree.clean(f"{cat}/{rest}" if cat else rest)), ""


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
