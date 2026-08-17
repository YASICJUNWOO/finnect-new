"""본문 정리 — **원문이 HTML 통째로 온다.**

기업마당 `bsnsSumryCn` 은 `<p>`, `<br>`, `style=` 속성, `&nbsp;` 가 섞인 HTML 이다.
그대로 화면에 두면 태그가 보이고, 태그만 지우면 문단이 한 줄로 붙는다.
DB 도 네트워크도 안 탄다.
"""

from __future__ import annotations

import pytest

from finnect.api.text import to_text


@pytest.mark.parametrize("value", [None, "", "   ", "<p></p>", "<p><br></p>", "&nbsp;"])
def test_내용이_없으면_None(value: str | None) -> None:
    """빈 문자열이 아니라 None 이다. 화면이 '내용이 없다'를 알아야 빈 문단을 안 그린다."""
    assert to_text(value) is None


def test_태그를_지우고_엔티티를_푼다() -> None:
    assert to_text("<p>중소기업 &amp; 소상공인&nbsp;지원</p>") == "중소기업 & 소상공인 지원"


def test_문단이_붙지_않는다() -> None:
    """`</p>` 를 줄바꿈으로 바꾸지 않으면 두 문장이 한 줄로 붙는다."""
    assert to_text("<p>첫째 줄</p><p>둘째 줄</p>") == "첫째 줄\n둘째 줄"


def test_br_도_줄바꿈이다() -> None:
    assert to_text("가<br>나<br/>다") == "가\n나\n다"


def test_속성이_붙은_태그도_지운다() -> None:
    """실물이 `<p style=\"line-height: 1.8\">` 형태로 온다."""
    assert to_text('<p style="line-height: 1.8">본문</p>') == "본문"


def test_빈_문단_반복이_뭉쳐진다() -> None:
    """원문에 `<p><br></p>` 가 연달아 온다. 그대로 두면 빈 줄이 대여섯 줄 쌓인다."""
    assert to_text("<p>가</p><p><br></p><p><br></p><p>나</p>") == "가\n\n나"


def test_엔티티를_태그보다_나중에_푼다() -> None:
    """먼저 풀면 `&lt;p&gt;` 가 태그로 되살아나 지워진다. 이건 본문에 든 글자다."""
    assert to_text("<p>태그는 &lt;p&gt; 로 씁니다</p>") == "태그는 <p> 로 씁니다"


def test_script_는_내용까지_버린다() -> None:
    assert to_text("<p>본문</p><script>var x = 1;</script>") == "본문"


def test_평문은_그대로_통과한다() -> None:
    """K-Startup `pbanc_ctnt` 는 대체로 평문이다. 건드릴 이유가 없다."""
    assert to_text("모집 대상: 예비창업자") == "모집 대상: 예비창업자"
