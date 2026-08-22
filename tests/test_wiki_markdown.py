"""마크다운 조각 — plan/14 · plan/20.

**마크다운은 저장소가 아니라 뷰다**(plan/12 `구상도와의 차이`). 그래서 여기서 보는 것은
"저장된 글이 맞나"가 아니라 **"같은 DB 에서 항상 같은 글이 나오나"** 다. 시각이 들어가면
그 성질이 깨지고, 깨지면 바이트로 비교할 수 없다.

**장 한 장을 만드는 것은 이제 `export.py` 다**(ADR-0052). 여기 남은 것은 어느 뷰든 쓰는
조각 셋이고, 장 단위 검증은 `test_wiki_export.py` 에 있다.

DB 도 파일도 안 쓴다 — 값과 사실을 손으로 만들어 넣는다.
"""

from __future__ import annotations

from finnect.wiki import markdown, topics
from finnect.wiki.markdown import Evidence, Statement, Value
from finnect.wiki.merge import Status

E1 = Evidence("사업계획서.docx", None, "시드 투자 3억원")
E2 = Evidence("재무제표.xlsx", None, "자본잉여금 3억원은 2025.09 시드 라운드 유치액입니다")
E3 = Evidence("피치덱.pptx", 11, "시드 라운드 2.8억원")


def _lines(parts: list[str]) -> str:
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────
# 값 블록
# ─────────────────────────────────────────────────────────────────


def test_충돌은_둘_다_적고_말로_알린다():
    """**다수결로 안 푼다.** 3억이 근거 둘이어도 2.8억을 지우지 않는다."""
    out = _lines(
        markdown.render_values(
            [
                Value(
                    "funding",
                    "조달액",
                    "300000000",
                    "시드",
                    "2025-09-30",
                    Status.CONFLICT,
                    (E1, E2),
                ),
                Value(
                    "funding", "조달액", "280000000", "시드", "2025-09-30", Status.CONFLICT, (E3,)
                ),
            ]
        )
    )
    assert markdown.CONFLICT_NOTE in out
    assert "**300,000,000원**" in out
    assert "**280,000,000원**" in out


def test_이전_값은_접어서_아래_적는다():
    """지우지 않는다(F1-1-7). 현재값이 먼저 오고 이력이 뒤에 온다."""
    out = _lines(
        markdown.render_values(
            [
                Value("headcount", "직원 수", "7", None, "2025-08-22", Status.SUPERSEDED, (E1,)),
                Value("headcount", "직원 수", "15", None, "2026-08-31", Status.CURRENT, (E3,)),
            ]
        )
    )
    assert out.index("**15명**") < out.index("이전 값")
    assert "- 7명 · 2025-08-22" in out


def test_한정어가_제목에_붙는다():
    """시드와 정책자금은 같은 슬롯이지만 다른 것이다."""
    out = _lines(
        markdown.render_values(
            [
                Value(
                    "funding", "조달액", "300000000", "시드", "2025-09-30", Status.CURRENT, (E1,)
                ),
                Value(
                    "funding", "조달액", "50000000", "정책자금", "2025-04-30", Status.CURRENT, (E2,)
                ),
            ]
        )
    )
    assert "## 조달액 [시드]" in out
    assert "## 조달액 [정책자금]" in out


def test_단위가_붙는다():
    """`120000000` 을 그대로 두면 1억 2천만과 1천 2백만이 눈으로 구분되지 않는다."""
    assert topics.display("capital", "120000000") == "120,000,000원"
    assert topics.display("headcount", "15") == "15명"
    #: 저장값이 숫자가 아니면 손대지 않는다. **추출기가 못 고친 값을 여기서 꾸미지 않는다**
    assert topics.display("capital", "1억 2천") == "1억 2천"
    #: 시점·이름은 단위가 없다
    assert topics.display("founded_on", "2024-03-11") == "2024-03-11"


# ─────────────────────────────────────────────────────────────────
# 사실 블록과 근거
# ─────────────────────────────────────────────────────────────────


def test_근거가_쪽까지_적힌다():
    """`회사소개서.pdf` 가 아니라 `회사소개서.pdf 3쪽` 이어야 한다(ADR-0014)."""
    assert "피치덱.pptx 11쪽" in _lines(markdown.render_facts([Statement("사실", "cost", (E3,))]))
    #: 쪽이 없는 포맷에는 안 붙인다 — **없는 번호를 만들어 붙이면 근거가 거짓이 된다**
    assert "사업계획서.docx 쪽" not in _lines(
        markdown.render_facts([Statement("사실", "cost", (E1,))])
    )


def test_한_사실에_근거_여럿이_한_줄로_붙는다():
    out = _lines(markdown.render_facts([Statement("같은 말", "cost", (E1, E2, E3))]))
    assert "> 근거 3 — 사업계획서.docx · 재무제표.xlsx · 피치덱.pptx 11쪽" in out


def test_근거_파일_목록이_같은_파일을_한_줄로_모은다():
    """**어느 파일을 지우면 무엇이 사라지는지** 보이는 자리다."""
    out = _lines(markdown.render_sources([E1, E1, E3]))
    assert "- 사업계획서.docx" in out and "- 피치덱.pptx" in out
    assert out.count("사업계획서.docx") == 1


def test_근거에_sha256_이_따라온다():
    """기획 문서 §5 의 `source_path` 가 이 값에서 나온다 — 원본이 콘텐츠 주소다(ADR-0029).

    **없어도 된다.** 옛 코드가 만든 `Evidence` 는 세 인자짜리라 빈 문자열이 온다.
    """
    assert Evidence("a.pdf", 1, "인용").sha256 == ""
    assert Evidence("a.pdf", 1, "인용", "abc123").sha256 == "abc123"


# ─────────────────────────────────────────────────────────────────
# 어휘 — ADR-0048 · ADR-0052
# ─────────────────────────────────────────────────────────────────


def test_topic_한국어_이름이_event_topic_전부에_있다():
    """**하나라도 없으면 화면에 영문 키가 나간다.**"""
    assert topics.EVENT_TOPICS - set(topics.TOPIC_LABELS) == set()


def test_topic_이름이_orbit_이름과_안_겹친다():
    """겹치면 `# X` 밑에 `## X` 가 서서 DESIGN.md §10 을 어긴다."""
    assert set(topics.TOPIC_LABELS.values()) & {o.label for o in topics.ORBIT.values()} == set()


def test_event_어휘가_orbit_과_한_벌이다():
    """**event topic 이름은 orbit 키와 같다.** ADR-0048 결정 3 이 마이그레이션을 안 하는 근거다."""
    assert set(topics.EVENT_ORBITS) == {k for k, o in topics.ORBIT.items() if o.event}
    assert all(topics.EVENT_ORBITS[k] == topics.ORBIT[k].label for k in topics.EVENT_ORBITS)
    assert all(o.event == k for k, o in topics.ORBIT.items() if o.event)


def test_sector_어휘가_없어졌다():
    """**ADR-0052 결정 3.** 구획은 각도의 이름이었고 궤도 그래프와 같이 사라졌다.

    되살리려는 코드가 생기면 여기서 걸린다 — `Orbital` 에 자리가 없다.
    """
    assert not hasattr(topics, "SECTORS")
    assert "sector" not in topics.Orbital.__slots__
