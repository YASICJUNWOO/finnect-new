"""구축 진행 표시 — plan/15 (SPEC F1-1-9).

**이 파일이 지키는 것은 셋이다.**

1. **`chunked` 하나가 두 가지 뜻을 갖는다.** 파일을 막 넣었을 때는 "사실을 뽑을 차례"이고
   빌드가 끝난 뒤에도 `chunked` 면 "추출기가 몰라서 되돌려놨다"다(`build._shelve`).
   행만 봐서는 구분이 안 돼서 `running` 을 같이 본다 — **이게 `wiki/progress.py` 의
   존재 이유이고, 여기가 깨지면 화면이 영원히 도는 중으로 남는다.**
2. **아무것도 안 올렸어도 단계 다섯과 자리 열다섯이 온다.** 처음 온 사람도 무엇이
   일어날지 먼저 볼 수 있어야 한다(DESIGN.md §7-5).
3. **올리기가 배포본을 죽이지 않는다.** `api/app.py` 가 파서를 최상단에서 끌고 오면
   로컬은 통과하고 배포본만 `ModuleNotFoundError` 로 죽는다.

DB 가 필요한 것은 갈라 뒀다.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from finnect.api.wiki_schemas import ProgressOut
from finnect.models import UserFileStatus
from finnect.wiki import progress, topics

SRC = Path(__file__).resolve().parents[1] / "src" / "finnect"


# ─────────────────────────────────────────────────────────────────
# 단계 표 — DB 도 파서도 없이 돈다
# ─────────────────────────────────────────────────────────────────


def test_단계가_다섯이고_순서가_고정이다():
    """**순서가 곧 진행 순서다.** 앞 칸이 뒤 칸의 재료라 뒤섞이면 뜻이 없어진다."""
    assert [s.key for s in progress.STEPS] == ["receive", "parse", "chunk", "extract", "link"]
    assert all(s.label for s in progress.STEPS)


def test_모든_상태가_표에_있다():
    """**모르는 상태로 떨어지는 값이 있으면 화면이 "모르는 상태예요"를 띄운다.**

    `UserFileStatus` 에 값을 더하고 여기를 안 고치면 그 파일이 0칸에 갇힌다.
    """
    covered = set(progress._MID) | set(progress._END)
    assert covered == set(UserFileStatus), f"표에 없는 상태: {set(UserFileStatus) - covered}"


def test_chunked_가_도는_중과_멈춤에서_다른_말을_한다():
    """**이 모듈이 있는 이유다.** 같은 행이 상황에 따라 다른 뜻이다."""
    going = progress.stage_of(UserFileStatus.CHUNKED, running=True)
    stopped = progress.stage_of(UserFileStatus.CHUNKED, running=False)

    assert going.moving is True
    assert stopped.moving is False
    assert going.label != stopped.label
    # 칸 수는 같다 — 실제로 조각까지는 됐다. 달라지는 것은 "더 갈 것인가"뿐이다
    assert going.reached == stopped.reached == 3


def test_끝난_상태는_running_과_무관하다():
    """다 됐거나 못 읽은 파일은 빌드가 도는 중이어도 움직이지 않는다."""
    for status in (UserFileStatus.DONE, UserFileStatus.NEEDS_REVIEW, UserFileStatus.FAILED):
        for running in (True, False):
            assert progress.stage_of(status, running=running).moving is False


def test_다_된_것만_ok_다():
    """**움직이는 중에는 ok 가 아니다** — 아직 모르는 것을 됐다고 말하지 않는다."""
    assert progress.stage_of(UserFileStatus.DONE, running=False).ok is True
    for status in set(UserFileStatus) - {UserFileStatus.DONE}:
        assert progress.stage_of(status, running=True).ok is False
        assert progress.stage_of(status, running=False).ok is False


def test_다_된_것이_마지막_칸이다():
    assert progress.stage_of(UserFileStatus.DONE, running=False).reached == len(progress.STEPS)


def test_칸_수가_범위를_안_넘는다():
    for status in set(UserFileStatus):
        for running in (True, False):
            reached = progress.stage_of(status, running=running).reached
            assert 0 <= reached <= len(progress.STEPS)


def test_모르는_상태는_아는_척하지_않는다():
    """**0칸이고 이름을 그대로 보여 준다.** 조용히 done 으로 떨어뜨리면 거짓말이 된다."""
    stage = progress.stage_of("무언가새로운상태", running=True)
    assert stage.reached == 0
    assert stage.ok is False
    assert stage.moving is False
    assert "무언가새로운상태" in stage.label


def test_진행_모듈이_순수하다():
    """**배포본에도 올라간다.** 파서나 httpx 가 끼면 서버리스 함수가 죽는다."""
    tree = ast.parse((SRC / "wiki" / "progress.py").read_text(encoding="utf-8"))
    got = {
        n.module
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module
    } | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m.startswith(("finnect.attach", "httpx", "sqlalchemy")) for m in got), got


def test_올리기가_파서를_최상단에서_안_끌고_온다():
    """**로컬은 통과하고 배포본만 죽는 종류다**(CLAUDE.md 함정).

    `wiki.service` 는 `attach.extract`(파서)를 쓴다. `api/app.py` 가 그걸 모듈 최상단에서
    임포트하면 `import finnect.api.app` 이 pdfplumber 를 끌고 온다. 함수 안에서 부르는
    것은 괜찮다 — 그때는 이미 로컬이다.
    """
    tree = ast.parse((SRC / "api" / "app.py").read_text(encoding="utf-8"))
    top = {
        n.module
        for n in tree.body
        if isinstance(n, ast.ImportFrom) and n.module
    } | {a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names}
    bad = {"finnect.wiki.service", "finnect.wiki.build", "finnect.attach.extract", "httpx"}
    assert not (top & bad), f"최상단에서 끌고 온다: {top & bad}"


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


def test_아무것도_안_올려도_단계와_자리가_온다(client) -> None:  # noqa: ANN001
    """**빈 화면을 "데이터 없음"으로 끝내지 않는다**(DESIGN.md §7-5).

    화면이 이 응답 하나로 "던지면 이렇게 돼요"를 그린다.
    """
    r = client.get("/api/wiki/c_없는회사/progress")
    assert r.status_code == 200
    body = ProgressOut.model_validate(r.json())

    assert body.total == 0
    assert body.files == []
    assert [s.key for s in body.steps] == [s.key for s in progress.STEPS]
    assert body.slots == 15
    assert body.running is False


def test_자리_라벨을_전부_준다(client) -> None:  # noqa: ANN001
    """**화면이 이름을 짓지 않는다.** `files[].nodes` 가 키라서 이게 없으면 영문이 뜬다."""
    body = ProgressOut.model_validate(client.get("/api/wiki/c_없는회사/progress").json())
    assert set(body.places) == set(topics.ORBIT)
    assert all(v for v in body.places.values())


def test_셈이_파일_수와_맞는다(client) -> None:  # noqa: ANN001
    """`done`·`moving`·`needs_review`·`stuck` 이 **겹치지도 새지도 않는다.**

    겹치면 "7개 중 9개가 끝났어요"가 나오고, 새면 어디에도 안 세어진 파일이 생긴다.
    """
    body = ProgressOut.model_validate(client.get("/api/wiki/c_dasiro/progress").json())
    assert body.done + body.moving + body.needs_review + body.stuck == body.total
