"""공고 정규화 (plan/17 T-0070).

네트워크를 안 쓴다. **LLM 은 가짜를 넣는다** — 여기서 보는 것은 뽑은 값이 좋은지가
아니라 **자기 출력을 원문에 대조하는가**다.

1. `bsnsSumryCn` 은 HTML 이고 `☞` 로 절이 갈린다
2. 앵커가 원문에 없으면 그 공고를 **버리고 센다**
3. `body_hash` 가 조회수에 안 흔들린다
4. `전국` 같은 말이 `regions` 에 안 들어간다
"""

from __future__ import annotations

from finnect.match import bodies
from finnect.match import normalize as nz


class 가짜클라이언트:
    model = "gpt-5.6-luna"

    def __init__(self, out: dict) -> None:
        self._out = out
        self.calls: list[dict] = []

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        return self._out


class 행:
    """`bizinfo_notice` 한 행 흉내. `getattr` 만 쓴다."""

    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)


# ─────────────────────────── 절 나누기 ───────────────────────────

# 실제 응답이다 — 기업마당 `[충청권] 내일이음 취업박람회`
_실물 = (
    "<p>&nbsp;☞ 지원대상 : 채용을 희망하는 충북 소재 구인기업, 채용을 희망하는 "
    "충청남도, 대전광역시, 세종특별자치시 내 바이오헬스, 미래모빌리티 기업</p>"
    "<p>☞ 지원내용 : 박람회 참가비 전액 무료, 직접채용, 간접채용</p>"
)


def test_HTML_을_지우고_절을_나눈다() -> None:
    sm = bodies.clean_summary(_실물)
    assert "<p>" not in sm and "&nbsp;" not in sm
    first = bodies.first_clause(sm)
    assert "충북 소재 구인기업" in first
    assert "바이오헬스" in first
    # 2절이 1절에 안 섞인다
    assert "박람회 참가비" not in first
    assert "박람회 참가비" in bodies.second_clause(sm)


def test_절이_안_갈리면_요약_전체를_지원대상에_넣는다() -> None:
    """**빈 채로 넘기지 않는다.** 지역·업종이 거기 있다."""
    b = bodies.from_bizinfo(
        행(pblancId="X", pblancNm="제목", bsnsSumryCn="☞ 없는 공고 본문이다", trgetNm="중소기업")
    )
    assert b.target


def test_기업마당과_kstartup_이_같은_모양으로_나온다() -> None:
    a = bodies.from_bizinfo(행(pblancId="A", pblancNm="가", bsnsSumryCn=_실물, trgetNm=""))
    b = bodies.from_kstartup(
        행(
            pbanc_sn="175689",
            biz_pbanc_nm="나",
            aply_trgt_ctnt="· 하드웨어 관련 제조 분야(국내외 중소벤처기업)\r\n· 프로토타입 필요",
            pbanc_ctnt="본문",
        )
    )
    assert (a.source, b.source) == ("bizinfo", "kstartup")
    assert "하드웨어" in b.target
    # 줄바꿈이 접혀 한 줄이 된다 — 프롬프트에 그대로 들어간다
    assert "\r" not in b.target and "\n" not in b.target


# ─────────────────────────── 캐시 키 ───────────────────────────


def test_body_hash_가_조회수에_안_흔들린다() -> None:
    """`content_hash` 를 쓰면 기업마당이 재수집마다 전량 '변경' 이다."""
    a = bodies.from_bizinfo(
        행(pblancId="A", pblancNm="가", bsnsSumryCn=_실물, trgetNm="", inqireCo="100")
    )
    b = bodies.from_bizinfo(
        행(pblancId="A", pblancNm="가", bsnsSumryCn=_실물, trgetNm="", inqireCo="99999")
    )
    assert a.body_hash == b.body_hash


def test_본문이_바뀌면_body_hash_가_바뀐다() -> None:
    a = bodies.from_bizinfo(행(pblancId="A", pblancNm="가", bsnsSumryCn=_실물, trgetNm=""))
    b = bodies.from_bizinfo(
        행(pblancId="A", pblancNm="가", bsnsSumryCn=_실물.replace("충북", "경기"), trgetNm="")
    )
    assert a.body_hash != b.body_hash


# ─────────────────────────── 앵커 대조 ───────────────────────────


def _본문() -> nz.NoticeBody:
    return bodies.from_bizinfo(
        행(pblancId="A", pblancNm="충청권 취업박람회", bsnsSumryCn=_실물, trgetNm="")
    )


def test_앵커가_원문에_있으면_받는다() -> None:
    n = nz.LlmNormalizer(
        client=가짜클라이언트(
            {
                "regions": ["충북", "충남", "대전", "세종"],
                "industries": ["바이오헬스", "미래모빌리티"],
                "conditions": ["채용 계획 보유"],
                "keywords": ["채용", "박람회"],
                "purpose": "구인기업의 채용을 돕는다",
                "anchor": "충북 소재 구인기업",
            }
        )
    )
    got = n.read(_본문())
    assert got is not None
    assert got.regions == ("충북", "충남", "대전", "세종")
    assert not n.dropped


def test_앵커가_원문에_없으면_버리고_센다() -> None:
    """조용히 비면 **'아무것도 안 나온 것' 과 구분이 안 된다**(ADR-0031)."""
    n = nz.LlmNormalizer(
        client=가짜클라이언트(
            {
                "regions": ["서울"],
                "industries": [],
                "conditions": [],
                "keywords": ["창업"],
                "purpose": "지어낸 것",
                "anchor": "이 문장은 원문에 없다",
            }
        )
    )
    assert n.read(_본문()) is None
    assert len(n.dropped) == 1


def test_공백만_다른_앵커는_통과한다() -> None:
    n = nz.LlmNormalizer(
        client=가짜클라이언트(
            {
                "regions": [],
                "industries": [],
                "conditions": [],
                "keywords": ["채용"],
                "purpose": "가",
                "anchor": "충북  소재\n구인기업",
            }
        )
    )
    assert n.read(_본문()) is not None


def test_전국을_지역으로_안_받는다() -> None:
    """`regions` 가 비어야 '제한 없음' 이다. `전국` 이 들어오면 제한이 생긴다."""
    n = nz.LlmNormalizer(
        client=가짜클라이언트(
            {
                "regions": ["전국", "제한없음", "충북"],
                "industries": ["무관"],
                "conditions": [],
                "keywords": ["채용", "채용"],
                "purpose": "가",
                "anchor": "충북 소재 구인기업",
            }
        )
    )
    got = n.read(_본문())
    assert got is not None
    assert got.regions == ("충북",)
    assert got.industries == ()
    # 중복 키워드가 한 번만 남는다
    assert got.keywords == ("채용",)


# ─────────── 앵커 대조 대상이 프롬프트와 같다 (실측 수정) ───────────


def test_보내는_것과_대조하는_것이_같다() -> None:
    """**2026-08-20 손 라벨 15건에서 잡은 결함이다.**

    둘을 따로 만들었더니 모델이 구역 둘을 걸쳐 인용했을 때 대조가 실패했다 —
    앵커에 `--- 지원내용 ---` 이 들어 있는데 대조 대상에는 그 줄이 없었다.
    """
    b = _본문()
    assert nz.user_prompt(b) == b.text


def test_구분선을_넘는_앵커가_통과한다() -> None:
    b = _본문()
    # **`b.text` 에서 잘라 온다.** 구분선을 걸치도록 자리를 고른다
    자리 = b.text.index("--- 지원내용 ---")
    걸친앵커 = b.text[자리 - 30 : 자리 + 40]
    assert "--- 지원내용 ---" in 걸친앵커
    n = nz.LlmNormalizer(
        client=가짜클라이언트({
            "regions": ["충북"], "industries": [], "conditions": [],
            "keywords": ["채용"], "purpose": "가", "anchor": 걸친앵커,
        })
    )
    assert n.read(b) is not None
    assert not n.dropped


def test_구분선을_요약한_앵커도_통과한다() -> None:
    """**2026-08-20 실측 — 150건 중 8건(5.3%)이 이걸로 버려졌다.**

    모델이 두 구역을 걸쳐 인용하면서 구분선을 **요약해 버린다.** 우리가 넣은
    표시라 우리가 지우는 것이 맞다 — 공고 본문에는 원래 없던 글자다.
    """
    b = _본문()
    대상끝 = b.target[-20:]
    내용앞 = b.body[:20]
    n = nz.LlmNormalizer(
        client=가짜클라이언트({
            "regions": [], "industries": [], "conditions": [],
            "keywords": ["채용"], "purpose": "가",
            # 구분선 자리에 줄바꿈 하나만 넣었다 — 실제 응답이 이 모양이다
            "anchor": f"{대상끝}\n{내용앞}",
        })
    )
    assert n.read(b) is not None
    assert not n.dropped


def test_구역_표시가_대조에서_빠진다() -> None:
    assert nz.squash("제목: 가\n\n--- 지원대상 ---\n나") == "가나"


def test_HTML_엔티티를_전부_푼다() -> None:
    """**2026-08-20 실측 — `R&amp;D역량` 이 남아 앵커 대조가 깨졌다.**

    모델은 `R&D역량` 으로 정직하게 인용했는데 우리 원문이 이스케이프된 채였다.
    `notice-filter` 는 `&nbsp;` 하나만 풀지만 여기서는 전부 푼다.
    """
    sm = bodies.clean_summary("☞ 지원대상 : R&amp;D역량을 보유한 기업&nbsp;&amp; 예비창업자")
    assert "&amp;" not in sm and "&nbsp;" not in sm
    assert "R&D역량" in sm
    assert "& 예비창업자" in sm
