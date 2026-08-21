"""`--only` — 후보를 목록 파일로 좁힌다 (plan/17).

`attach --only` 와 같은 경계다. **층0 은 이 계획 밖에 산다** — `notice-filter/` 가
기업마당 1,524 → 542 · K-Startup 29,789 → 15,643 을 내는데 그 폴더는 제품 코드가
아니다. 이쪽은 목록만 읽고 **누가 골랐는지 모른다.**

그래야 그 폴더가 바뀌거나 사라져도 이 코드가 안 바뀐다.
"""

from __future__ import annotations

import pathlib

import pytest

from finnect.match import __main__ as cli
from finnect.match import service


@pytest.fixture
def 목록(tmp_path):  # noqa: ANN001, ANN201
    p = tmp_path / "후보.txt"
    p.write_text("PBLN-1\n\nPBLN-2\n  \nPBLN-3\n", encoding="utf-8")
    return p


def test_목록_파일을_읽어_넘긴다(monkeypatch, 목록) -> None:  # noqa: ANN001
    """빈 줄과 공백 줄은 버린다. 손으로 만든 목록에 섞이기 쉽다."""
    받은: dict = {}

    def 가짜_run(company_id, **kw):  # noqa: ANN001, ANN003, ANN202
        받은["company"] = company_id
        받은.update(kw)
        return service.MatchReport()

    monkeypatch.setattr(service, "run", 가짜_run)
    monkeypatch.setattr(service, "report", lambda **_: "")
    cli.main(["--company", "c_x", "--only", str(목록)])

    assert 받은["company"] == "c_x"
    assert 받은["only"] == {"PBLN-1", "PBLN-2", "PBLN-3"}


def test_안_주면_열린_공고_전량이다(monkeypatch) -> None:  # noqa: ANN001
    """**기본이 전량이다.** 목록을 안 주면 층0 이 없는 것과 같다 — 뗄 수 있다는 뜻이다."""
    받은: dict = {}

    def 가짜_run(company_id, **kw):  # noqa: ANN001, ANN003, ANN202
        받은.update(kw)
        return service.MatchReport()

    monkeypatch.setattr(service, "run", 가짜_run)
    monkeypatch.setattr(service, "report", lambda **_: "")
    cli.main(["--company", "c_x"])
    assert 받은["only"] is None


def test_match_가_필터를_모른다() -> None:
    """`match/` 어디에서도 `notice-filter` 를 임포트하지 않는다.

    이게 깨지면 필터를 지울 때 제품 코드가 같이 죽는다. **절 나누기 정규식이
    두 곳에 사는 대가를 치르는 이유가 이것이다**(`match/bodies.py`).
    """
    src = pathlib.Path(service.__file__).parent
    for f in src.glob("*.py"):
        t = f.read_text(encoding="utf-8")
        assert "notice_filter" not in t, f
        assert "import filter" not in t, f


def test_인자를_안_주면_무엇을_할지_묻는다() -> None:
    """조용히 아무것도 안 하지 않는다."""
    with pytest.raises(SystemExit):
        cli.main([])
