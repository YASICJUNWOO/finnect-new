"""`--only` — 받을 URL 을 목록 파일로 좁힌다 (plan/13 T-0050).

**K-Startup 전량이 55.3GB 인데 이 서버 여유가 24GB 다.** 골라 받아야 하고,
고르는 규칙은 `notice-filter/` 에 따로 산다.

여기서 검증하는 것은 **경계 하나**다 — 다운로더는 목록만 읽고 **누가 골랐는지 모른다.**
그래야 규칙이 바뀌거나 사라져도 이 코드가 안 바뀐다.
"""

from __future__ import annotations

import pytest

from finnect.attach import __main__ as cli
from finnect.attach import service


@pytest.fixture
def 목록(tmp_path):  # noqa: ANN001, ANN201
    p = tmp_path / "urls.txt"
    p.write_text("https://a.example/1\n\nhttps://b.example/2\n  \nhttps://c.example/3\n")
    return p


def test_목록_파일을_읽어_넘긴다(monkeypatch, 목록) -> None:  # noqa: ANN001
    """빈 줄과 공백 줄은 버린다. 손으로 만든 목록에 섞이기 쉽다."""
    받은: dict = {}

    def 가짜_run(**kw):  # noqa: ANN003, ANN202
        받은.update(kw)
        return service.AttachReport()

    monkeypatch.setattr(service, "run", 가짜_run)
    monkeypatch.setattr(service, "coverage", lambda s: {})
    monkeypatch.setattr(cli, "render_coverage", lambda c: "")
    cli.main(["--only", str(목록), "--source", "kstartup"])

    assert 받은["only"] == {
        "https://a.example/1",
        "https://b.example/2",
        "https://c.example/3",
    }


def test_안_주면_전량이다(monkeypatch) -> None:  # noqa: ANN001
    """**기본이 전량이다.** 목록을 안 주면 필터가 없는 것과 같다 — 뗄 수 있다는 뜻이다."""
    받은: dict = {}
    monkeypatch.setattr(service, "run", lambda **kw: (받은.update(kw), service.AttachReport())[1])
    monkeypatch.setattr(service, "coverage", lambda s: {})
    monkeypatch.setattr(cli, "render_coverage", lambda c: "")
    cli.main([])
    assert 받은["only"] is None


def test_다운로더가_필터를_모른다() -> None:
    """`attach` 어디에서도 `notice-filter` 를 임포트하지 않는다.

    이게 깨지면 필터를 지울 때 제품 코드가 같이 죽는다.
    """
    import pathlib

    src = pathlib.Path(service.__file__).parent
    for f in src.glob("*.py"):
        t = f.read_text(encoding="utf-8")
        assert "notice_filter" not in t, f
        assert "import filter" not in t, f
