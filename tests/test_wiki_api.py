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

from finnect.api.wiki_schemas import WikiOut
from finnect.wiki import topics

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
    for name in ("markdown.py", "merge.py", "topics.py"):
        got = _imports(SRC / "wiki" / name)
        assert not any(m.startswith("finnect.attach") for m in got), name


def test_궤도가_슬롯과_노드를_하나도_안_빠뜨린다():
    """**표에 구멍이 있으면 사실이 화면에서 통째로 사라진다.** 여기서 잡는다."""
    used_slots = {s for o in topics.ORBIT.values() for s in o.slots}
    used_nodes = {o.node for o in topics.ORBIT.values() if o.node}
    assert used_slots == set(topics.SLOTS)
    assert used_nodes == set(topics.EVENT_ORBITS)


def test_궤도가_SPEC_의_열다섯이다():
    """정체성 1 + 사업체 정보 5 + 사업 내용 9(SPEC F1-2). **셈이 맞아야 배치가 선다.**"""
    kinds = [o.kind for o in topics.ORBIT.values()]
    assert (kinds.count("identity"), kinds.count("company"), kinds.count("content")) == (1, 5, 9)
    assert len(topics.ORBIT) == 15


def test_구획이_전부_이름을_갖는다():
    """이름 없는 구획이 있으면 궤도에 키 문자열이 그대로 뜬다."""
    assert {o.sector for o in topics.ORBIT.values()} == set(topics.SECTORS)


def test_구획이_궤도에서_흩어지지_않는다():
    """**서버가 준 순서가 곧 배치 순서다**(ADR-0017). 같은 구획이 이웃해 있어야
    프론트가 각도를 묶어 나눈다 — 흩어져 있으면 구획이 원을 한 바퀴 돈다."""
    for kind in ("company", "content"):
        seen: list[str] = []
        for o in topics.ORBIT.values():
            if o.kind != kind:
                continue
            if not seen or seen[-1] != o.sector:
                seen.append(o.sector)
        assert len(seen) == len(set(seen)), f"{kind} 구획이 흩어져 있다: {seen}"


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


def test_위키가_없어도_궤도_열다섯이_온다(client) -> None:  # noqa: ANN001
    """**빈 화면을 '데이터 없음'으로 끝내지 않는다**(DESIGN.md §7-5)."""
    r = client.get("/api/wiki/c_없는회사")
    assert r.status_code == 200
    body = WikiOut.model_validate(r.json())
    assert body.total == 15
    assert len(body.nodes) == 15
    assert body.filled == 0
    assert all(not n.filled for n in body.nodes)


def test_마크다운은_없으면_404다(client) -> None:  # noqa: ANN001
    """빈 문서를 내려 주지 않는다 — 화면이 빈 `<pre>` 를 그리게 된다."""
    assert client.get("/api/wiki/c_없는회사/markdown").status_code == 404


def test_모든_자리가_제_마크다운을_들고_온다(client) -> None:  # noqa: ANN001
    """화면이 자리마다 원문을 보여 줄 수 있어야 한다. **빈 자리도 한 장이 나온다.**"""
    body = WikiOut.model_validate(client.get("/api/wiki/c_없는회사").json())
    for n in body.nodes:
        assert n.markdown.startswith("---"), n.key
        assert f"# {n.label}" in n.markdown


def test_topic_묶음을_서버가_만들고_절을_보일지도_서버가_정한다():
    """**규칙을 화면에 한 번 더 적으면 두 곳이 된다**(ADR-0048 결정 5).

    `groups` 는 표 순서 그대로이고 빈 것도 온다 — 화면이 «무엇이 없는지» 를 말할 수
    있어야 한다. `grouped` 가 false 인 자리에서는 화면이 `statements` 를 통째로 뿌린다.
    """
    from finnect.api.wiki_service import _node
    from finnect.wiki.markdown import Evidence, NodeView, Statement

    e = Evidence("사업계획서.hwp", 3, "ㅇ")
    solution = _node(
        NodeView(
            key="solution",
            label="솔루션과 기술",
            kind="content",
            sector="problem_solution",
            company_id="c_t",
            values=(),
            statements=(Statement("출원번호 10-2025-0012345.", "patent", (e,)),),
        )
    )
    assert solution.grouped is True
    assert [g.topic for g in solution.groups] == list(topics.ORBIT_TOPICS["solution"])
    assert [g.label for g in solution.groups][:2] == ["서비스 소개", "기능"]
    #: 빈 topic 도 온다
    assert sum(1 for g in solution.groups if not g.statements) == 6

    customer = _node(
        NodeView(
            key="customer",
            label="목표 고객",
            kind="content",
            sector="market_customer",
            company_id="c_t",
            values=(),
            statements=(Statement("소상공인이다.", "target_customer", (e,)),),
        )
    )
    assert customer.grouped is False
    assert len(customer.groups) == 1
