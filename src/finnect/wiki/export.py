"""기획이 넘긴 폴더 트리 — **위키의 유일한 뷰다**(ADR-0052).

기획 문서 `20_지식베이스구조.md` 가 그린 폴더 열과 `.md` 자리 46개를 자리 하나까지
옮겨 놓은 것이다. **2026-08-22 부터 화면도 이걸 본다** — 그전까지는 궤도 열다섯 장이 화면이었고
이쪽은 `--export` 플래그 뒤에만 있었다(ADR-0052 가 ADR-0048 결정 4 를 대체).

**저장 모델을 이 모양으로 바꾸지 않는다.** 마크다운을 저장하지 않기로 한 것과 같은
이유다 — 사실이 `wiki_fact` 에 있는데 파일 트리로도 들고 있으면 둘 중 하나가 먼저
낡는다. 여기는 **읽을 때마다 만든다.** 화면의 단위가 된 것이지 저장의 단위가 된 것이
아니다.

## 자리 마흔여섯 중 스물다섯이 닿는다

기획 트리는 `.md` 자리 46개다(고정 29 · 폴더만 동적 5 · 파일 동적 12). 우리 topic 37 을
얹으면 25 가 채워지고 21 이 빈다. 우리가 더한 `Company/지역관계.md` 를 합쳐 **47 중 26** 이다.
**빈 것을 지우지 않는다** — 비어 있다는 것도 사실이고 물어야 할 자리다(ADR-0028). 대조표는
[`docs/adr/evidence/2026-08-21-위키-자리-구조/04-기획-트리-대조표.md`](../../../docs/adr/evidence/2026-08-21-위키-자리-구조/04-기획-트리-대조표.md)
에 있고 **이 파일의 `TREE` 에서 만든다.** 손으로 세지 않는다.

## 동적 자리를 지금은 한 장으로 접는다

`Competitor/{업체명}.md` 처럼 회사마다 개수가 다른 자리가 12개다. 진짜로 가르려면
사실마다 인스턴스 이름(업체명·특허번호)을 알아야 하는데 **`fact_key` 가 컬럼으로
없다** — `dedupe_key` 안에 `event|market|<fact_key>` 로 묶여 들어가 있고, `fact_key`
가 없으면 정규화된 문장이 그 자리를 채워서 둘을 구분할 수 없다.

그래서 지금은 폴더 하나에 파일 하나로 접는다(`Competitor/경쟁사.md`). 컬럼을 붙이는
것은 [plan/19](../../../docs/plan/19-위키-자리-구조.md) 태스크다. **접혔다는 것을
프론트매터에 적는다** — 조용히 접으면 기획 트리를 지원한다는 말이 거짓이 된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from finnect.models import SourceType
from finnect.wiki import markdown, storage, topics

#: 기획 문서 §2 의 최상위 폴더 열과 화면에 쓰는 이름.
#:
#: **자리 제목과 겹치면 안 된다.** 겹치면 `# 경쟁 상대` 밑에 `## 경쟁사` 가 서서
#: `DESIGN.md` §10("제목이 말한 것을 부제에서 반복하지 않는다")을 어긴다 —
#: `TOPIC_LABELS` 를 orbit 라벨과 안 겹치게 고른 것과 같은 규율이고 테스트가 막아 둔다.
#: `Competitor` 가 「경쟁사」가 아니라 「경쟁 상대」인 이유가 그것이다.
#:
#: **폴더 이름(키)은 기획 문서 것 그대로다.** 경로가 곧 자리의 이름이라(기획 §4-3)
#: 여기서 한 번 더 번역하면 집필 에이전트가 부르는 이름과 갈린다. `Custom` 이 내용을
#: 안 가리킨다는 것은 기획도 알고 있고(§7-4) **그 이름을 우리가 먼저 고치지 않는다.**
FOLDERS: dict[str, str] = {
    "Company": "회사",
    "Product": "제품",
    "Market": "시장",
    "Competitor": "경쟁 상대",
    "Customer": "고객",
    "BusinessModel": "사업 모델",
    "Financial": "재무",
    "Custom": "지식 재산",
    "Plan": "계획",
    "Events": "기록",
}


#: 기획 문서 §5 의 자료 등급 다섯. **우리가 내는 것은 앞 둘과 마지막뿐이다.**
#:
#: `2차`(외부 인용)와 `가정`(추정)을 안 내는 이유는 **추출기가 그것을 판정하지 않기**
#: 때문이다(ADR-0052 결정 4). 「이 시장 규모가 KOSIS 인용인가 대표가 어림한 값인가」는
#: 문서 안에 답이 있을 때도 없을 때도 있는데 지금 프롬프트가 묻지 않는다. 없는 판정을
#: 그럴듯한 등급으로 채우면 `Market/` 값이 전부 `2차` 로 보이고, **기획이 이 필드를 만든
#: 목적(심사에서 산출 근거를 대는 것)이 정확히 거기서 깨진다.**
GRADES: tuple[str, ...] = ("실측", "1차", "2차", "가정", "미정")

#: 사용자가 직접 답한 값(ADR-0028). 문서보다 세다
GRADE_MEASURED = "실측"
#: 사용자가 올린 문서에서 나왔다. **자기 자료가 1차 자료다**
GRADE_PRIMARY = "1차"
#: 자리가 비었다
GRADE_UNKNOWN = "미정"


@dataclass(frozen=True, slots=True)
class Spot:
    """기획 트리의 `.md` 자리 하나."""

    #: 기획 문서가 적은 경로 그대로. `{}` 가 있으면 동적이다. **대조용이라 안 고친다**
    path: str
    #: 화면과 제목에 쓰는 이름
    title: str
    #: 이 자리에 오는 value topic
    values: tuple[str, ...] = ()
    #: 이 자리에 오는 event topic
    events: tuple[str, ...] = ()
    #: 우리가 더한 자리. **기획 문서에 없다**
    ours: bool = False
    #: 왜 비는가. 채울 topic 이 없는 자리에만 적는다
    gap: str = ""

    @property
    def folder(self) -> str:
        """최상위 폴더. **묶는 축이 이것이다**(ADR-0052 결정 3 이 `sector` 를 대신한다)."""
        return self.path.split("/", 1)[0]

    @property
    def instanced(self) -> bool:
        """**파일 이름**에 `{}` 가 있나. 있으면 사실마다 파일이 갈린다 — 기획 문서의 동적 열둘.

        폴더만 동적인 것(`Product/{서비스명}/소개.md`)은 여기 안 든다. 저기는 파일
        개수가 고정이고 **묶는 단위가 하나뿐인** 것이라 성질이 다르다.
        """
        return "{" in self.path.rsplit("/", 1)[-1]

    @property
    def folded(self) -> bool:
        """폴더에 `{}` 가 있나. 서비스를 여러 개 세울 수 없으므로 폴더를 접는다."""
        return "{" in self.path.rsplit("/", 1)[0]

    @property
    def file(self) -> str:
        """실제로 내보내는 경로. **접힌 자리는 이름이 다르다.**

        `{}` 있는 폴더는 지우고, `{}` 있는 파일 이름은 제목으로 갈아 낀다.
        """
        parts = self.path.split("/")
        dirs = [d for d in parts[:-1] if "{" not in d]
        name = f"{self.title}.md" if "{" in parts[-1] else parts[-1]
        return "/".join([*dirs, name])

    @property
    def filled(self) -> bool:
        return bool(self.values or self.events)


#: 기획 트리. **순서가 문서 2장 순서다** — 대조할 때 눈으로 따라갈 수 있어야 한다.
#:
#: `Product/{서비스명}/` 은 폴더가 동적인데 그 안의 파일 다섯은 고정이다. 서비스를
#: 여러 개 세울 수 없으므로 **폴더를 접고 파일 이름만 남긴다**(`Product/소개.md`).
TREE: tuple[Spot, ...] = (
    # ── Company ──────────────────────────────────────────────
    Spot(
        "Company/회사소개.md",
        "회사 소개",
        values=(
            "company_name",
            "business_no",
            "corp_no",
            "founded_on",
            "location",
            "industry",
            "industry_item",
        ),
    ),
    Spot("Company/비전.md", "비전", events=("vision",)),
    Spot("Company/팀.md", "팀", values=("headcount",), events=("team",)),
    Spot("Company/대표자.md", "대표자", values=("ceo_name", "ceo_birth")),
    Spot("Company/창업계기.md", "창업 계기", gap="topic 이 없다. 사업계획서에 그 절이 없다"),
    #: **기획 문서에 없는 자리다.** 우리가 더했고 지자체 공고 매칭에 직결된다
    Spot("Company/지역관계.md", "지역 관계", events=("region_link",), ours=True),
    # ── Product ──────────────────────────────────────────────
    Spot("Product/{서비스명}/소개.md", "소개", events=("service_overview",)),
    Spot(
        "Product/{서비스명}/문제와해결.md",
        "문제와 해결",
        gap="문제-해결 짝을 topic 으로 안 들고 있다. 문제는 Customer/고객문제.md 에 있다",
    ),
    Spot("Product/{서비스명}/기능.md", "기능", events=("service_feature",)),
    Spot("Product/{서비스명}/차별점.md", "차별점", events=("service_differentiator",)),
    Spot("Product/{서비스명}/개발현황.md", "개발 현황", events=("development_status",)),
    Spot("Product/{서비스명}/화면/{화면명}.md", "화면", gap="와이어프레임을 안 읽는다"),
    # ── Market ───────────────────────────────────────────────
    Spot("Market/시장규모.md", "시장 규모", events=("market_size",)),
    Spot("Market/산출식-TAM.md", "산출식 TAM", gap="곱셈 과정을 자리 텍스트로 못 담는다"),
    Spot("Market/산출식-SAM.md", "산출식 SAM", gap="같음"),
    Spot("Market/산출식-SOM.md", "산출식 SOM", gap="같음"),
    Spot("Market/트렌드.md", "트렌드", events=("market_trend",)),
    Spot("Market/통계/{항목}-{값}.md", "통계", gap="인용 통계를 낱개로 안 세운다"),
    # ── Competitor ───────────────────────────────────────────
    Spot("Competitor/{업체명}.md", "경쟁사", events=("competitor",)),
    Spot("Competitor/비교축.md", "비교축", gap="2x2 축을 topic 으로 안 들고 있다"),
    # ── Customer ─────────────────────────────────────────────
    Spot("Customer/타깃고객.md", "타깃 고객", events=("target_customer",)),
    Spot("Customer/고객문제.md", "고객 문제", events=("customer_problem",)),
    Spot("Customer/페르소나/{이름}.md", "페르소나", gap="인구통계를 낱개로 안 세운다"),
    Spot("Customer/인터뷰/{세그먼트}-{인원}-{시점}.md", "인터뷰", gap="답변 원문을 안 읽는다"),
    Spot("Customer/인용문/{세그먼트}-{주제}.md", "인용문", gap="발언 하나를 자리로 안 둔다"),
    Spot("Customer/검증/{활동}-{결과}.md", "검증", events=("customer_evidence",)),
    # ── BusinessModel ────────────────────────────────────────
    Spot("BusinessModel/수익모델.md", "수익 모델", events=("revenue_model",)),
    Spot("BusinessModel/가격정책.md", "가격 정책", events=("pricing",)),
    Spot("BusinessModel/판매전략.md", "판매 전략", events=("go_to_market",)),
    # ── Financial ────────────────────────────────────────────
    Spot("Financial/매출.md", "매출", values=("revenue",), events=("revenue",)),
    Spot("Financial/비용.md", "비용", events=("cost",)),
    Spot("Financial/자금계획.md", "자금 계획", values=("capital", "funding"), events=("funding",)),
    Spot("Financial/집행계획.md", "집행 계획", gap="지원금 항목별 배분을 안 다룬다"),
    # ── Custom ───────────────────────────────────────────────
    Spot("Custom/특허/{상태}-{번호}.md", "특허", events=("patent",)),
    Spot("Custom/인증/{인증명}.md", "인증", events=("certification",)),
    Spot("Custom/기술/{기술명}.md", "기술", events=("technology",)),
    # ── Plan ─────────────────────────────────────────────────
    Spot("Plan/일정.md", "일정", events=("roadmap",)),
    Spot("Plan/KPI.md", "KPI", gap="시점별 목표값을 topic 으로 안 들고 있다"),
    Spot("Plan/마케팅.md", "마케팅", gap="같음"),
    Spot("Plan/채용.md", "채용", gap="같음"),
    Spot("Plan/고객확장.md", "고객 확장", gap="같음"),
    Spot("Plan/기술고도화.md", "기술 고도화", gap="같음"),
    Spot("Plan/사회적가치.md", "사회적 가치", gap="같음"),
    # ── Events ───────────────────────────────────────────────
    Spot("Events/meetings/{날짜}.md", "회의", gap="일부러 뺐다 — topics.py 문서 2번"),
    Spot("Events/decisions.md", "결정", gap="일부러 뺐다 — 같음"),
    Spot("Events/actions.md", "할 일", gap="일부러 뺐다 — 같음"),
    Spot(
        "Events/applications/{공고명}-{연도}-{결과}.md",
        "지원 이력",
        values=("gov_program",),
    ),
)


@dataclass(slots=True)
class Page:
    """자리 한 장. **저장된 것이 아니라 매번 만든 것이다.**"""

    spot: Spot
    body: str
    values: list[markdown.Value] = field(default_factory=list)
    statements: list[markdown.Statement] = field(default_factory=list)

    #: --- 기획 문서 §5 의 파일 머리 (ADR-0052 결정 4) ---
    #: `실측` · `1차` · `미정`. **`2차`·`가정` 은 안 나온다** — `GRADES` 주석 참고
    grade: str = GRADE_UNKNOWN
    #: 근거가 된 파일 이름들. 정렬돼 있다
    sources: tuple[str, ...] = ()
    #: 그 파일들의 저장 위치. `sources` 와 같은 순서다
    source_paths: tuple[str, ...] = ()
    #: 값들의 `as_of` 중 가장 늦은 것. 시점 없는 자리는 `None`
    base_date: str | None = None
    #: 사실들의 `updated_at` 중 가장 늦은 것. **만든 시각이 아니다**
    updated_at: str | None = None

    @property
    def filled(self) -> bool:
        return bool(self.values or self.statements)


def grade_of(values: list[markdown.Value], statements: list[markdown.Statement]) -> str:
    """자리 하나의 자료 등급. **판정할 수 없는 등급을 지어내지 않는다**(ADR-0052 결정 4).

    비었으면 `미정`, 사실이 전부 사용자 답변이면 `실측`, 그 밖에는 `1차` 다. `2차` 와
    `가정` 은 추출기가 출처를 판정하는 날 생긴다 — **그날까지 이 함수는 그 둘을 안 낸다.**
    """
    kinds = [f.source_type for f in (*values, *statements)]
    if not kinds:
        return GRADE_UNKNOWN
    if all(k == SourceType.USER_STATED for k in kinds):
        return GRADE_MEASURED
    return GRADE_PRIMARY


def render(nodes: list[markdown.NodeView]) -> list[Page]:
    """저장 묶음을 트리 자리로 옮긴다. **자리 마흔일곱 전부 돌려준다.**

    빈 자리를 빼면 사용자가 무엇이 없는지 모른다. 화면에서 자리를 지우지 않는 것과
    같은 규칙이다(`DESIGN.md` §7-5).
    """
    by_value: dict[str, list[markdown.Value]] = {}
    by_topic: dict[str, list[markdown.Statement]] = {}
    for n in nodes:
        for v in n.values:
            by_value.setdefault(v.slot, []).append(v)
        for s in n.statements:
            by_topic.setdefault(s.topic, []).append(s)

    company = nodes[0].company_id if nodes else ""
    out = []
    for spot in TREE:
        values = [v for s in spot.values for v in by_value.get(s, [])]
        statements = [st for t in spot.events for st in by_topic.get(t, [])]
        page = Page(
            spot=spot,
            body="",
            values=values,
            statements=statements,
            grade=grade_of(values, statements),
            base_date=_latest(v.as_of for v in values),
            updated_at=_latest(
                f.updated_at.isoformat() for f in (*values, *statements) if f.updated_at
            ),
        )
        page.sources, page.source_paths = _sources_of(company, values, statements)
        page.body = _page(page, company)
        out.append(page)
    return out


def _latest(items: object) -> str | None:
    """ISO 날짜 문자열 중 가장 늦은 것. **문자열로 비교한다** — ISO 라 사전순이 곧 시간순이다."""
    seen = sorted(x for x in items if x)  # type: ignore[union-attr]
    return seen[-1] if seen else None


def _sources_of(
    company: str, values: list[markdown.Value], statements: list[markdown.Statement]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """근거 파일 이름과 저장 위치. **둘의 순서가 같다** — 짝이 어긋나면 위치가 거짓말이 된다.

    같은 파일이 근거 여럿에 걸리므로 파일명으로 묶는다. `sha256` 이 없는 근거는 위치를
    빈 문자열로 둔다 — **없는 경로를 지어내지 않는다.**
    """
    by_name: dict[str, str] = {}
    for f in (*values, *statements):
        for e in f.evidence:
            by_name.setdefault(e.filename, e.sha256)
    names = tuple(sorted(by_name))
    paths = tuple(
        storage.source_path(company, by_name[n]) if by_name[n] and company else ""
        for n in names
    )
    return names, paths


def _page(page: Page, company: str) -> str:
    """자리 한 장의 마크다운. 머리는 **기획 문서 §5 모양**이다(ADR-0052 결정 4).

    **만든 시각을 안 넣는다.** `updated_at` 은 `wiki_fact` 의 값이라 같은 DB 면 같다 —
    그래서 두 번 내보낸 결과를 바이트로 비교할 수 있다(`markdown.py` 문서 참고).
    """
    spot = page.spot
    lines = [
        "---",
        f"path: {spot.path}",
        f"title: {spot.title}",
        f"company: {company}",
        f"grade: {page.grade}",
    ]
    if page.sources:
        lines.append(f"source: {' · '.join(page.sources)}")
    if any(page.source_paths):
        lines.append(f"source_path: {' · '.join(p for p in page.source_paths if p)}")
    if page.base_date:
        lines.append(f"base_date: {page.base_date}")
    if page.updated_at:
        lines.append(f"updated_at: {page.updated_at}")
    if spot.ours:
        lines.append("added_by: finnect")
    if spot.instanced or spot.folded:
        #: **접혔다는 것을 적는다.** 조용히 접으면 트리를 지원한다는 말이 거짓이 된다
        lines.append(f"collapsed: {spot.path}")
    if page.values:
        lines.append(f"values: {len(page.values)}")
    if page.statements:
        lines.append(f"statements: {len(page.statements)}")
    lines.append("---")

    out = ["\n".join(lines), "", f"# {spot.title}", ""]

    if not spot.filled:
        out += [f"이 자리는 아직 안 채워요. {spot.gap}.", ""]
        return "\n".join(out).rstrip() + "\n"
    if not page.filled:
        out += ["아직 비어 있어요. 이 자리를 채우려면 관련된 파일을 더 올리면 돼요.", ""]
        return "\n".join(out).rstrip() + "\n"

    if page.values:
        out += markdown.render_values(page.values)
    if page.statements:
        out += _by_topic(spot, page.statements)

    evidence = [e for v in page.values for e in v.evidence] + [
        e for s in page.statements for e in s.evidence
    ]
    out += markdown.render_sources(evidence)
    return "\n".join(out).rstrip() + "\n"


def _by_topic(spot: Spot, statements: list[markdown.Statement]) -> list[str]:
    """event topic 이 둘 이상이면 절로 가른다(ADR-0048 결정 5).

    **표가 정하고 데이터가 정하지 않는다.** 실제로 나온 사실 수로 판단하면 파일을 하나
    더 올릴 때 절 제목이 생겼다 없어진다.
    """
    if len(spot.events) < 2:
        return markdown.render_facts(statements)
    out: list[str] = []
    for topic in spot.events:
        items = [s for s in statements if s.topic == topic]
        if not items:
            continue
        out += [f"## {topics.TOPIC_LABELS.get(topic, topic)}", ""]
        out += markdown.render_facts(items)
    return out


def bundle(pages: list[Page], company: str) -> str:
    """자리 전부를 한 덩어리로. 화면에서 통째로 보거나 복사할 때 쓴다.

    **F1-6(밖으로 꺼내기)이 아니다.** 저기는 자리마다 `.md` 파일 하나로 떨어져 옵시디언
    볼트가 되는 것이고(`__main__.py --export`), 여기는 한 덩어리다.

    **빈 자리도 넣는다.** 무엇이 없는지가 이 문서의 절반이다(ADR-0028).

    폴더가 바뀔 때 이름을 한 줄 세운다. 자리가 47개라 표지가 없으면 어디를 읽고 있는지
    알 수 없다. **제목 층이 자리 제목과 겹치는데** 그대로 둔다 — 낱장으로 열려야 하는
    문서를 이어 붙인 것이라 낱장이 정본이고, 맞추려면 저쪽을 `##` 로 내려야 한다.
    """
    out: list[str] = [f"# 사업 위키 — {company}", ""]
    last = ""
    for page in pages:
        if page.spot.folder != last:
            last = page.spot.folder
            out += [f"# {FOLDERS.get(last, last)}", ""]
        out += [page.body, ""]
    return "\n".join(out).rstrip() + "\n"
