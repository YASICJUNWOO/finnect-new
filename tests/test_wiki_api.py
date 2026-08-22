"""사업 위키 API(S7) — plan/14.

**두 가지를 잠근다.**

1. **위키가 없어도 궤도 열다섯이 온다.** 화면이 빈 자리를 보여 줘야 무엇을 올려야 하는지
   알 수 있다(DESIGN.md §7-5). 404 나 빈 목록으로 답하면 화면이 "데이터 없음"으로 끝난다.
2. **배포본에서 죽지 않는다.** `api/wiki_service.py` 가 `attach.service` 나 `ingest.service`
   를 끌고 오면 로컬은 통과하고 배포본만 죽는다 — 저 둘이 httpx 와 파서를 들고 오는데
   `requirements.txt` 가 그것들을 뺐다. `tests/test_admin_api.py` 가 같은 것을 막고 있다.

DB 가 필요한 것은 건너뛸 수 있게 갈라 뒀다.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from finnect.api.wiki_schemas import ProfileOut, WikiOut
from finnect.wiki import profile, spots

SRC = Path(__file__).resolve().parents[1] / "src" / "finnect"


def _imports(path: Path) -> set[str]:
    """그 파일이 임포트하는 모듈 이름 전부. **부르지 않고 읽는다** — 임포트 자체가 위험하다."""
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
            out |= {f"{node.module}.{a.name}" for a in node.names}
    return out


# ─────────────────────────────────────────────────────────────────
# 배포본에서 죽지 않는가 — DB 없이 돈다
# ─────────────────────────────────────────────────────────────────


def test_해독_모듈을_끌고_오지_않는다():
    """**임포트하면 로컬은 통과하고 배포본만 죽는다.**

    `wiki.service` 는 `attach.extract`(파서)를 쓰고 `attach.service` 는 httpx 를 쓴다.
    읽기 경로만 올라가므로(ADR-0026) 서버리스 함수에는 둘 다 없다.
    """
    bad = {"finnect.attach.service", "finnect.ingest.service", "finnect.wiki.service", "httpx"}
    got = _imports(SRC / "api" / "wiki_service.py")
    assert not (got & bad), f"배포본에 없는 모듈을 끌고 온다: {got & bad}"


def test_마크다운과_라우팅이_순수_파이썬이다():
    """`wiki.build` 를 타고 들어오는 것들. 여기 파서가 끼면 위 테스트가 무의미해진다."""
    for name in ("markdown.py", "merge.py", "tree.py", "profile.py"):
        got = _imports(SRC / "wiki" / name)
        assert not any(m.startswith("finnect.attach") for m in got), name


def test_자리표가_한_곳에만_있다():
    """**표가 `spots.py` 하나다**(ADR-0058).

    2026-08-22 아침까지 이 표가 없었고(추출기가 경로를 지었다), 그 전에는
    `export.TREE` 와 `tree.EVENT_PATH` 두 곳에 있었다. 둘로 갈리면 화면이 세운 자리와
    추출이 앉히는 자리가 어긋나고, **어긋나면 사실이 화면에 없는 자리에 앉는다.**
    """
    from finnect.wiki import export, tree

    assert not hasattr(tree, "EVENT_PATH")
    assert not hasattr(tree, "CATEGORIES")
    assert not hasattr(export, "TREE")


def test_고정된_것이_셋이다():
    """**폴더 열 · 자리 마흔여섯 · 매칭 정보 열넷**(ADR-0058).

    자리 안에서 문서가 정하는 것은 `{…}` 열일곱의 인스턴스 이름뿐이다.
    """
    assert len(spots.FOLDERS) == 10
    assert len(spots.SPOTS) == 46
    assert len(profile.PROFILE_KEYS) == 14


def test_옛_어휘가_없어졌다():
    """`sector`·`orbit`·`topic`·`place_kind`·`key` 는 되살리지 않는다."""
    import importlib

    for name in ("finnect.wiki.topics",):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"{name} 이 되살아났다")
    from finnect import models

    assert not hasattr(models, "WikiPlace")
    assert not hasattr(models.WikiFact, "place")


# ─────────────────────────────────────────────────────────────────
# 실제 응답 — DB 가 있어야 한다
# ─────────────────────────────────────────────────────────────────


@pytest.fixture
def client():  # noqa: ANN201
    from fastapi.testclient import TestClient

    from finnect.api.app import app
    from finnect.db import SessionFactory

    try:
        with SessionFactory() as s:
            s.execute(__import__("sqlalchemy").text("select 1"))
    except OperationalError:
        pytest.skip("DB 가 없다. `docker compose up -d db` 뒤에 다시 돈다")
    return TestClient(app)


def test_위키가_없어도_카테고리_열이_온다(client) -> None:  # noqa: ANN001
    """**빈 화면을 '데이터 없음'으로 끝내지 않는다**(DESIGN.md §7-5)."""
    r = client.get("/api/wiki/c_없는회사")
    assert r.status_code == 200
    body = WikiOut.model_validate(r.json())
    assert body.total == len(spots.FOLDERS)
    assert {n.path for n in body.nodes} == set(spots.FOLDERS)
    assert body.filled == 0
    assert all(n.depth == 0 for n in body.nodes)
    #: 카테고리 라벨이 같이 온다 — **화면이 이름을 짓지 않는다**
    assert set(body.categories) == set(spots.FOLDERS)


def test_마크다운은_없으면_404다(client) -> None:  # noqa: ANN001
    """빈 문서를 내려 주지 않는다 — 화면이 빈 `<pre>` 를 그리게 된다."""
    assert client.get("/api/wiki/c_없는회사/markdown").status_code == 404


def test_사실이_붙은_노드만_마크다운을_갖는다(client) -> None:  # noqa: ANN001
    """**빈 뼈대는 장이 없다**(ADR-0056 결정 4). 볼트에 빈 파일을 만들지 않는다."""
    body = WikiOut.model_validate(client.get("/api/wiki/c_없는회사").json())
    for n in body.nodes:
        assert n.markdown == "" if not n.filled else n.markdown.startswith("---")


def test_회사_정보가_열넷_다_온다(client) -> None:  # noqa: ANN001
    """**빈 칸이 물어볼 자리다**(ADR-0028). 열넷이 고정이라 셀 수 있다."""
    r = client.get("/api/company/c_없는회사")
    assert r.status_code == 200
    body = ProfileOut.model_validate(r.json())
    assert body.total == 14
    assert len(body.keys) == 14
    assert body.filled == 0
    #: 자격 판별 입력이 표시된다 — 비면 물어야 한다
    assert sum(1 for k in body.keys if k.eligibility) == len(profile.ELIGIBILITY_KEYS)
