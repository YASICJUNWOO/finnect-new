"""마크다운 조각 — plan/14 · plan/20.

**마크다운은 저장소가 아니라 뷰다**(plan/12 `구상도와의 차이`). 그래서 여기서 보는 것은
"저장된 글이 맞나"가 아니라 **"같은 DB 에서 항상 같은 글이 나오나"** 다. 시각이 들어가면
그 성질이 깨지고, 깨지면 바이트로 비교할 수 없다.

**장 한 장을 만드는 것은 `export.py` 다**(ADR-0056). 여기 남은 것은 사실 블록과 근거
목록이고, 값 블록은 트랙 B(`company_value`)로 나갔다.

DB 도 파일도 안 쓴다 — 값과 사실을 손으로 만들어 넣는다.
"""

from __future__ import annotations

import datetime as dt

from finnect.wiki import markdown, profile, spots, tree
from finnect.wiki.markdown import Evidence, Statement

E1 = Evidence("사업계획서.docx", None, "시드 투자 3억원")
E2 = Evidence("재무제표.xlsx", None, "자본잉여금 3억원은 2025.09 시드 라운드 유치액입니다")
E3 = Evidence("피치덱.pptx", 11, "시드 라운드 2.8억원")


def _lines(parts: list[str]) -> str:
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────
# 값 블록
# ─────────────────────────────────────────────────────────────────


def test_단위가_붙는다():
    """`120000000` 을 그대로 두면 1억 2천만과 1천 2백만이 눈으로 구분되지 않는다.

    **값은 트랙 B 로 갔다**(ADR-0056). 단위를 붙이는 자리는 `wiki/profile.py` 하나다.
    """
    assert profile.display("capital", "120000000") == "120,000,000원"
    assert profile.display("headcount", "15") == "15명"
    #: 저장값이 숫자가 아니면 손대지 않는다. **추출기가 못 고친 값을 여기서 꾸미지 않는다**
    assert profile.display("capital", "1억 2천") == "1억 2천"
    #: 시점·이름은 단위가 없다
    assert profile.display("founded_on", "2024-03-11") == "2024-03-11"


# ─────────────────────────────────────────────────────────────────
# 사실 블록과 근거
# ─────────────────────────────────────────────────────────────────


def test_사실이_절_제목_없이_선다():
    """**`key` 가 없어지면서 절도 없어졌다**(ADR-0058)."""
    out = _lines(markdown.render_facts([Statement("개발 8명, 영업 4명이다.", (E1,))]))
    assert "개발 8명, 영업 4명이다." in out
    assert "## " not in out


def test_값도_문장으로만_뜬다():
    """**값 칸이 없어졌다**(ADR-0059). 숫자는 문서가 쓴 표현 그대로 문장 안에 있다.

    옛날에는 `**15** · 2026-08-31 기준` 처럼 값을 뽑아 굵게 찍었다. 그러려면 추출기가
    `2,410만원` 을 `24100000` 으로 고쳐 써야 했고, **읽는 코드가 하나도 없는데** 고쳐
    쓴 값이 화면에 뜨는 상태였다.
    """
    out = _lines(
        markdown.render_facts(
            [Statement("2026년 8월 기준 임직원 15명입니다", (E1,), as_of=dt.date(2026, 8, 31))]
        )
    )
    assert "2026년 8월 기준 임직원 15명입니다" in out
    assert "*2026-08-31 기준*" in out
    #: **우리가 뽑아 굵게 찍는 값이 없다**
    assert "**15**" not in out


def test_서술이_시점_내림차순으로_쌓인다():
    """**이력은 상태 컬럼이 아니라 정렬이 만든다**(ADR-0057 결정 3)."""
    out = _lines(
        markdown.render_facts(
            [
                Statement("2025년 11월 기준 개발 4명", (E1,), as_of=dt.date(2025, 11, 30)),
                Statement("2026년 8월 기준 개발 8명", (E3,), as_of=dt.date(2026, 8, 31)),
            ]
        )
    )
    #: **최신이 위다.** 넣은 순서(2025 → 2026)를 뒤집어야 한다
    assert out.index("2026년 8월 기준 개발 8명") < out.index("2025년 11월 기준 개발 4명")


def test_시점_없는_서술이_뒤로_간다():
    """**언제 것인지 모르는 서술이 아는 것을 밀어내면 안 된다** — `merge` 와 같은 규칙."""
    out = _lines(
        markdown.render_facts(
            [
                Statement("언제인지 모르는 말", (E1,)),
                Statement("2026년 8월 기준", (E3,), as_of=dt.date(2026, 8, 31)),
            ]
        )
    )
    assert out.index("2026년 8월 기준") < out.index("언제인지 모르는 말")


def test_뷰가_접지_않는다():
    """무엇을 하나로 볼지는 `merge.node_key` 가 이미 정했고, 여기까지 온 사실은 전부
    다른 행이다 — 여기서 또 접으면 규칙이 두 곳에 살게 된다.
    """
    out = _lines(
        markdown.render_facts(
            [
                Statement("구조조정으로 10명 감소", (E1,), as_of=dt.date(2025, 9, 30)),
                Statement("신입사원 채용", (E3,), as_of=dt.date(2026, 3, 31)),
            ]
        )
    )
    assert "구조조정으로 10명 감소" in out and "신입사원 채용" in out


def test_같은_자리에_어긋난_값이_둘이면_나란히_선다():
    """**어긋남을 접지 않는다.** 하나로 접으면 값 하나가 조용히 사라진다(F1-1-7)."""
    day = dt.date(2025, 9, 30)
    out = _lines(
        markdown.render_facts(
            [
                Statement("시드 라운드 3억원을 유치했다", (E1,), as_of=day),
                Statement("시드 라운드 2.8억원을 유치했다", (E3,), as_of=day),
            ]
        )
    )
    assert "3억원" in out and "2.8억원" in out


def test_등급은_1차가_아닐_때만_적힌다():
    """`1차` 가 기본값이라 전부 적으면 **정작 눈에 띄어야 할 `가정` 이 안 보인다.**"""
    plain = _lines(markdown.render_facts([Statement("우리 값이다", (E1,), grade="1차")]))
    assert "1차" not in plain

    guess = _lines(markdown.render_facts([Statement("2027년 목표다", (E1,), grade="가정")]))
    assert "가정" in guess

    cited = _lines(
        markdown.render_facts(
            [Statement("시장이 3조다", (E1,), grade="2차", source="중소벤처기업부")]
        )
    )
    assert "2차 · 중소벤처기업부" in cited


def test_근거가_쪽까지_적힌다():
    """`회사소개서.pdf` 가 아니라 `회사소개서.pdf 3쪽` 이어야 한다(ADR-0014)."""
    assert "피치덱.pptx 11쪽" in _lines(markdown.render_facts([Statement("사실", (E3,))]))
    #: 쪽이 없는 포맷에는 안 붙인다 — **없는 번호를 만들어 붙이면 근거가 거짓이 된다**
    assert "사업계획서.docx 쪽" not in _lines(
        markdown.render_facts([Statement("사실", (E1,))])
    )


def test_한_사실에_근거_여럿이_한_줄로_붙는다():
    out = _lines(markdown.render_facts([Statement("같은 말", (E1, E2, E3))]))
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
# 어휘 — ADR-0056
# ─────────────────────────────────────────────────────────────────


def test_폴더가_열이고_경로의_첫_마디다():
    """**폴더는 기획 문서 §2 의 것이고 우리가 늘리지 않는다.**"""
    assert len(spots.FOLDERS) == 10
    assert tree.category_of("Custom/특허/등록-10-2025-0114882") == "Custom"
    assert {s.folder for s in spots.SPOTS} == set(spots.FOLDERS)


def test_자리가_마흔여섯이고_열일곱이_동적이다():
    """기획 §2 트리 그대로다. **개수가 바뀌면 표를 손댄 것이다.**"""
    assert len(spots.SPOTS) == 46
    assert sum(1 for s in spots.SPOTS if not s.fixed) == 17
    #: 자리 이름이 겹치면 딥링크가 둘을 가리킨다
    assert len({s.path for s in spots.SPOTS}) == 46


def test_검토_대기는_기획_표_밖이다():
    """**우리가 더한 하나다.** 표 안에 넣으면 LLM 이 그 번호를 고를 수 있게 된다."""
    assert spots.REVIEW not in spots.SPOTS
    assert spots.REVIEW.folder in spots.FOLDERS


def test_경로가_마디마다_정규화된다():
    """통째로 지우면 `A/BC` 와 `AB/C` 가 같아진다 — **다른 자리인데 하나로 묶인다.**"""
    assert tree.norm_path("Competitor/배달의 민족") == tree.norm_path("Competitor/배달의민족")
    assert tree.norm_path("A/BC") != tree.norm_path("AB/C")
    #: 유사도가 아니다. 다른 말은 다른 자리다
    assert tree.norm_path("Competitor/배민") != tree.norm_path("Competitor/배달의민족")


def test_조상을_얕은_것부터_전부_준다():
    """**뼈대가 없으면 트리가 안 선다** — 노드를 만들 때 이 목록을 다 만든다."""
    assert tree.ancestors("Custom/특허/등록-1") == ["Custom", "Custom/특허", "Custom/특허/등록-1"]


def test_표_밖의_경로는_자리로_안_풀린다():
    """옛 `tree.clean` 이 하던 「Custom 밑으로 민다」가 여기로 왔다 — 이제 표가 답이다."""
    assert spots.spot_of("모르는것/어디") is None
    assert spots.by_number(99) is None


def test_매칭_정보가_열다섯이고_별칭이_그리로_모인다():
    assert len(profile.PROFILE_KEYS) == 15
    for name in ("상시 근로자", "종업원 수", "구성원", "임직원", "직원 수", "상시근로자", "직원수"):
        assert profile.key_of(name) == "headcount", name
    #: 표에 없으면 **추측하지 않는다**
    assert profile.key_of("업력") is None


def test_시점을_안_갖는_key_는_시점을_뗀다():
    """**병합 규칙이다.** 안 떼면 같은 사업자등록번호가 문서 수만큼 행이 된다."""
    day = dt.date(2026, 8, 31)
    assert profile.as_of_for("headcount", day) == day
    assert profile.as_of_for("business_no", day) is None


def test_sector_와_topics_가_없어졌다():
    """**ADR-0056.** 되살리려는 코드가 생기면 여기서 걸린다."""
    import importlib

    for name in ("finnect.wiki.topics",):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"{name} 이 되살아났다")
