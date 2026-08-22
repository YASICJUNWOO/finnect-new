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

from finnect.wiki import markdown, profile, tree
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


def _value(key: str, value: str, text: str, ev=(E1,), **kw) -> Statement:  # noqa: ANN001, ANN003
    return Statement(text, key, ev, kind="value", value=value, **kw)


def test_절_제목이_key_다():
    """**이 파일이 오래 못 보던 것이다.** `key` 가 라벨이자 병합 열쇠인데 찍는 자리가
    없어서, 한 장에 사실 셋이 있으면 이름 없는 문단 셋으로 섰다.
    """
    out = _lines(markdown.render_facts([Statement("개발 8명, 영업 4명이다.", "팀 구성", (E1,))]))
    assert "## 팀 구성" in out
    assert "개발 8명, 영업 4명이다." in out


def test_값과_시점이_절_제목이_아니라_사실_줄에_붙는다():
    """**제목에 넣으면 한 절에 사실이 여럿일 때 하나만 실린다**(ADR-0057 결정 4)."""
    out = _lines(
        markdown.render_facts(
            [
                _value(
                    "직원 수", "15", "2026년 8월 기준 임직원 15명입니다", as_of=dt.date(2026, 8, 31)
                )
            ]
        )
    )
    assert "## 직원 수" in out
    assert "**15** · 2026-08-31 기준" in out
    #: **단위를 안 붙인다.** 트랙 A 의 key 는 자유 문자열이라 아는 단위가 없다.
    #: 본문의 `15명` 은 문서가 쓴 말이라 그대로 남는다 — 우리가 붙인 것이 아니다
    assert "**15명**" not in out


def test_서술이_시점_내림차순으로_쌓인다():
    """**이력은 상태 컬럼이 아니라 정렬이 만든다**(ADR-0057 결정 3).

    `team_roles_2026_08` / `team_roles_2025_11` 로 갈려 있던 것이 `팀 구성` 한 절이 된다.
    """
    out = _lines(
        markdown.render_facts(
            [
                Statement(
                    "2025년 11월 기준 개발 4명", "팀 구성", (E1,), as_of=dt.date(2025, 11, 30)
                ),
                Statement(
                    "2026년 8월 기준 개발 8명", "팀 구성", (E3,), as_of=dt.date(2026, 8, 31)
                ),
            ]
        )
    )
    assert out.count("## 팀 구성") == 1, "한 절이어야 한다"
    #: **최신이 위다.** 넣은 순서(2025 → 2026)를 뒤집어야 한다
    assert out.index("2026년 8월 기준 개발 8명") < out.index("2025년 11월 기준 개발 4명")


def test_시점_없는_서술이_뒤로_간다():
    """**언제 것인지 모르는 서술이 아는 것을 밀어내면 안 된다** — `merge` 와 같은 규칙."""
    out = _lines(
        markdown.render_facts(
            [
                Statement("언제인지 모르는 말", "팀 구성", (E1,)),
                Statement("2026년 8월 기준", "팀 구성", (E3,), as_of=dt.date(2026, 8, 31)),
            ]
        )
    )
    assert out.index("2026년 8월 기준") < out.index("언제인지 모르는 말")


def test_뷰는_같은_key_의_사실_여럿을_다_낸다():
    """**뷰가 접지 않는다.** 무엇을 하나로 볼지는 `merge.node_key` 가 이미 정했고, 여기까지
    온 사실은 전부 다른 행이다 — 여기서 또 접으면 병합 규칙이 두 곳에 살게 된다.
    """
    out = _lines(
        markdown.render_facts(
            [
                Statement("구조조정으로 10명 감소", "팀 변동", (E1,), as_of=dt.date(2025, 9, 30)),
                Statement("신입사원 채용", "팀 변동", (E3,), as_of=dt.date(2026, 3, 31)),
            ]
        )
    )
    assert out.count("## 팀 변동") == 1
    assert "구조조정으로 10명 감소" in out and "신입사원 채용" in out


def test_같은_key_에_값이_둘이면_한_절에_나란히_선다():
    """**충돌을 접지 않는다.** 같은 자리에 값이 둘인 것이 곧 충돌이라(`merge.decide`)
    하나로 접으면 값 하나가 사라진다. 절 안에서 둘이 보이는 것이 그 상태의 표현이다.
    """
    day = dt.date(2025, 9, 30)
    out = _lines(
        markdown.render_facts(
            [
                _value("조달액", "300000000", "시드 3억원", qualifier="시드", as_of=day),
                _value("조달액", "280000000", "시드 2.8억원", (E3,), qualifier="시드", as_of=day),
            ]
        )
    )
    assert out.count("## 조달액") == 1
    assert "**300000000** — 시드 · 2025-09-30 기준" in out
    assert "**280000000** — 시드 · 2025-09-30 기준" in out


def test_key_순서가_처음_나온_순서다():
    """가나다순으로 다시 세우면 **문서가 말한 순서가 사라진다.**"""
    keys = [
        k
        for k, _ in markdown.group(
            [
                Statement("ㄴ", "하늘", (E1,)),
                Statement("ㄱ", "가람", (E1,)),
                Statement("ㄷ", "하늘", (E1,)),
            ]
        )
    ]
    assert keys == ["하늘", "가람"]


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
# 어휘 — ADR-0056
# ─────────────────────────────────────────────────────────────────


def test_카테고리가_열이고_경로의_첫_마디다():
    """**고정은 이것뿐이다.** 나머지는 문서가 정한다."""
    assert len(tree.CATEGORIES) == 10
    assert tree.FALLBACK in tree.CATEGORIES
    assert tree.category_of("Custom/특허/등록-10-2025-0114882") == "Custom"


def test_경로가_마디마다_정규화된다():
    """통째로 지우면 `A/BC` 와 `AB/C` 가 같아진다 — **다른 자리인데 하나로 묶인다.**"""
    assert tree.norm_path("Company/기 능") == tree.norm_path("Company/기능")
    assert tree.norm_path("A/BC") != tree.norm_path("AB/C")
    #: 유사도가 아니다. 다른 말은 다른 자리다
    assert tree.norm_path("Product/기능") != tree.norm_path("Product/주요기능")


def test_조상을_얕은_것부터_전부_준다():
    """**뼈대가 없으면 트리가 안 선다** — 노드를 만들 때 이 목록을 다 만든다."""
    assert tree.ancestors("Custom/특허/등록-1") == ["Custom", "Custom/특허", "Custom/특허/등록-1"]


def test_카테고리_밖의_경로는_Custom_밑으로_민다():
    """LLM 이 enum 을 어겨도 **사실이 안 사라진다.**"""
    assert tree.clean("모르는것/어디") == "Custom/모르는것/어디"
    assert tree.clean("") == tree.REVIEW_PATH


def test_매칭_정보가_열넷이고_별칭이_그리로_모인다():
    assert len(profile.PROFILE_KEYS) == 14
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
