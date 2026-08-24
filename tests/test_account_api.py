"""베타 입장 게이트 — [ADR-0066](
../docs/adr/0066-베타-테스터를-이름과-비밀번호로-가른다.md).

**이 게이트가 하는 일 하나는 「사람마다 다른 `company_id`」다.** 그 하나가 깨지면
테스터 둘이 같은 위키에 파일을 쌓거나, 같은 사람이 다시 들어왔을 때 어제 올린 것을
잃는다. 여기서 잠그는 것 넷.

1. **같은 이름 + 같은 비밀번호는 늘 같은 `company_id` 다** — 아니면 재방문이 새 회사가 된다
2. **다른 이름은 다른 `company_id` 다** — 아니면 격리가 없는 것과 같다
3. **발급된 값이 `wiki/storage.py` 의 `_COMPANY_ID` 를 통과한다** — 아니면 올리기가
   `IsolationError` 로 죽는다. **그 실패는 입장에서 안 보이고 파일을 던질 때 나온다**
4. **틀린 비밀번호가 남의 위키를 안 연다**

`storage._COMPANY_ID` 를 임포트해서 실제로 대조한다 — 정규식을 여기 베껴 적으면
저쪽이 바뀔 때 이 테스트가 옛 규칙을 지키고 통과한다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from finnect.api import app as api
from finnect.models import Base, CompanyAccount
from finnect.wiki.storage import _COMPANY_ID

NAME = "다시로"
PASSWORD = "베타비번"


@pytest.fixture
def client(monkeypatch):  # noqa: ANN001, ANN201
    # `StaticPool` 이 필요한 이유는 `test_draft_start.py` 와 같다 — 메모리 SQLite 는
    # 연결마다 다른 DB 라 라우트가 새 세션을 열면 빈 DB 를 본다.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[CompanyAccount.__table__])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(api, "SessionFactory", factory)

    with TestClient(app=api.app) as c:
        yield c


def _enter(c, name: str = NAME, password: str = PASSWORD):  # noqa: ANN001, ANN202
    return c.post("/api/account", json={"name": name, "password": password})


class Test입장:
    def test_처음_보는_이름이면_만든다(self, client) -> None:  # noqa: ANN001
        """**가입 화면을 따로 안 만든다**(ADR-0066 결정 1). 처음 온 사람이 폼 하나로 들어간다."""
        r = _enter(client)

        assert r.status_code == 200
        assert r.json()["name"] == NAME
        assert r.json()["company_id"]

    def test_같은_이름과_비번은_같은_위키다(self, client) -> None:  # noqa: ANN001
        """**이것이 이 게이트의 존재 이유다.** 쿠키를 지우고 다시 온 사람이 어제
        올린 파일을 그대로 봐야 한다 — 여기가 갈리면 위키가 매번 새로 선다."""
        first = _enter(client).json()["company_id"]
        second = _enter(client).json()["company_id"]

        assert first == second

    def test_다른_이름은_다른_위키다(self, client) -> None:  # noqa: ANN001
        """**격리가 여기서 시작된다.** 같으면 테스터 둘이 한 위키에 파일을 쌓는다."""
        a = _enter(client, "다시로").json()["company_id"]
        b = _enter(client, "나린데이터").json()["company_id"]

        assert a != b

    def test_앞뒤_공백은_같은_이름이다(self, client) -> None:  # noqa: ANN001
        """사람이 손으로 치는 값이라 공백이 붙는다. **안 떼면 " 다시로" 가 새 회사가 된다.**"""
        first = _enter(client, NAME).json()["company_id"]
        second = _enter(client, f"  {NAME} ").json()["company_id"]

        assert first == second


class Test발급된_값:
    def test_경로에_쓸_수_있는_모양이다(self, client) -> None:  # noqa: ANN001
        """**`wiki/storage.py` 가 이 값으로 디렉터리를 만든다.** 통과 못 하면
        `IsolationError` 인데, **그 실패가 입장이 아니라 파일을 던질 때 나온다** —
        사용자는 들어와 놓고 올리기에서 죽는 것을 본다.

        그래서 한글 이름을 그대로 `company_id` 로 안 쓴다."""
        company_id = _enter(client, "한글 회사명 주식회사").json()["company_id"]

        assert _COMPANY_ID.match(company_id)

    def test_이름이_값에_안_들어간다(self, client) -> None:  # noqa: ANN001
        """**관계없는 값을 발급한다**(ADR-0066 결정 3). 이름에서 만들면 두 이름이
        한 자리로 접히는 날이 오고, 그날 남의 위키가 열린다."""
        company_id = _enter(client, "dasiro").json()["company_id"]

        assert "dasiro" not in company_id


class Test거절:
    def test_틀린_비번은_401_이다(self, client) -> None:  # noqa: ANN001
        """**남의 위키를 열면 안 된다.** 이 게이트가 막는 유일한 것이다."""
        _enter(client)
        r = _enter(client, NAME, "틀린비번")

        assert r.status_code == 401

    def test_이름이_있는지를_안_알려_준다(self, client) -> None:  # noqa: ANN001
        """**「없는 이름」과 「틀린 비번」을 구분해 주지 않는다.** 나누면 어떤 이름이
        이미 쓰이는지가 새어 나간다 — `require_token` 이 "헤더가 없다" 와 "값이
        다르다" 를 안 가르는 것과 같은 이유다.

        **없는 이름은 401 이 아니라 200 이다**(만들어 준다). 그래서 여기서 잠그는 것은
        401 응답이 이름을 안 적는다는 것뿐이다."""
        _enter(client)
        body = _enter(client, NAME, "틀린비번").json()

        assert NAME not in body["detail"]

    def test_빈_값은_400_이다(self, client) -> None:  # noqa: ANN001
        """**공백만 친 것도 빈 이름이다.** 통과시키면 `company_id` 하나가
        「이름이 공백인 회사」로 서고 다음 사람이 그리로 들어간다."""
        assert _enter(client, "", PASSWORD).status_code == 400
        assert _enter(client, "   ", PASSWORD).status_code == 400
        assert _enter(client, NAME, "").status_code == 400
