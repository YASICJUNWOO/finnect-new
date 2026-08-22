"""기획이 넘긴 폴더 트리로 내보내기 — **뷰 둘 중 트리 뷰**(ADR-0048 결정 4).

궤도 뷰(`markdown.py`)는 orbit 열다섯 장이고 화면이 쓴다. 이쪽은 기획 문서
`20_지식베이스구조.md` 가 그린 폴더 트리이고 **내보낼 때만 쓴다**(F1-6).

저장 모델을 이 모양으로 바꾸지 않는다. 마크다운을 저장하지 않기로 한 것과 같은
이유다 — 사실이 `wiki_fact` 에 있는데 파일 트리로도 들고 있으면 둘 중 하나가 먼저
낡는다. 여기는 **읽을 때마다 만든다.**

## 자리 마흔여섯 중 스물일곱이 닿는다

기획 트리는 `.md` 자리 46개다(고정 29 · 폴더만 동적 5 · 파일 동적 12). 우리 topic 37 을
얹으면 25 가 채워지고 21 이 빈다. **빈 것을 지우지 않는다** — 비어 있다는 것도 사실이고 물어야 할
자리다(ADR-0028). 대조표는
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

from finnect.wiki import markdown, topics


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
    """내보낼 파일 하나."""

    spot: Spot
    body: str
    values: list[markdown.Value] = field(default_factory=list)
    statements: list[markdown.Statement] = field(default_factory=list)


def render(nodes: list[markdown.NodeView]) -> list[Page]:
    """궤도 뷰를 트리 뷰로 옮긴다. **자리 마흔일곱 전부 돌려준다.**

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
        out.append(
            Page(
                spot=spot,
                body=_page(spot, company, values, statements),
                values=values,
                statements=statements,
            )
        )
    return out


def _page(
    spot: Spot,
    company: str,
    values: list[markdown.Value],
    statements: list[markdown.Statement],
) -> str:
    lines = [
        "---",
        f"path: {spot.path}",
        f"title: {spot.title}",
        f"company: {company}",
    ]
    if spot.ours:
        lines.append("added_by: finnect")
    if spot.instanced or spot.folded:
        #: **접혔다는 것을 적는다.** 조용히 접으면 트리를 지원한다는 말이 거짓이 된다
        lines.append(f"collapsed: {spot.path}")
    if values:
        lines.append(f"values: {len(values)}")
    if statements:
        lines.append(f"statements: {len(statements)}")
    lines.append("---")

    out = ["\n".join(lines), "", f"# {spot.title}", ""]

    if not spot.filled:
        out += [f"이 자리는 아직 안 채워요. {spot.gap}.", ""]
        return "\n".join(out).rstrip() + "\n"
    if not values and not statements:
        out += ["아직 비어 있어요. 이 자리를 채우려면 관련된 파일을 더 올리면 돼요.", ""]
        return "\n".join(out).rstrip() + "\n"

    if values:
        out += markdown._values(tuple(values))
    if statements:
        out += _by_topic(spot, statements)

    evidence = [e for v in values for e in v.evidence] + [
        e for s in statements for e in s.evidence
    ]
    out += markdown._sources(evidence)
    return "\n".join(out).rstrip() + "\n"


def _by_topic(spot: Spot, statements: list[markdown.Statement]) -> list[str]:
    """event topic 이 둘 이상이면 절로 가른다. **궤도 뷰와 같은 규칙이다**(ADR-0048 결정 5)."""
    if len(spot.events) < 2:
        return markdown._facts(statements)
    out: list[str] = []
    for topic in spot.events:
        items = [s for s in statements if s.topic == topic]
        if not items:
            continue
        out += [f"## {topics.TOPIC_LABELS.get(topic, topic)}", ""]
        out += markdown._facts(items)
    return out
