"""운영 경로의 HTTP Basic — [ADR-0067](
../docs/adr/0067-운영-화면을-basic-으로-막는다.md).

**막는 것이 화면이 아니라 자료다.** `/admin/*` 화면은 `web/proxy.ts` 가 막고 여기는
그 화면이 부르는 API 다 — 한 겹이 뚫려도 다른 겹이 남는다.

여기서 잠그는 것 다섯.

1. **자격이 없으면 운영 경로가 안 열린다**
2. **자격이 비어 있으면 503 이다** — `api_token` 처럼 조용히 검사를 끄지 않는다.
   이 경로는 사용자 것이 아니라서 잊고 비워 두면 닫히는 쪽이어야 한다
3. **`WWW-Authenticate` 가 나간다** — 없으면 브라우저가 물을 자리를 모른다
4. **제품 경로는 안 걸린다** — 걸면 테스터가 공고를 못 본다
5. **접두사로 판단한다** — 새 운영 경로를 더할 때 잊을 수가 없다

**`_basic_ok` 를 직접도 부른다.** 깨진 입력에서 401 이 아니라 500 이 나는 것을
HTTP 로만 보면 상태 코드가 같아서 안 갈린다.
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from finnect.api import app as api
from finnect.config import settings

USER = "운영자"
PASSWORD = "비밀!@#"
PATH = "/api/admin/attachments"


def _basic(user: str, password: str) -> dict[str, str]:
    raw = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"authorization": f"Basic {raw}"}


@pytest.fixture
def client(monkeypatch):  # noqa: ANN001, ANN201
    monkeypatch.setattr(settings, "admin_user", USER)
    monkeypatch.setattr(settings, "admin_password", PASSWORD)
    # 토큰 문은 이 파일의 관심사가 아니다. 켜져 있으면 Basic 을 보기도 전에 막힌다
    monkeypatch.setattr(settings, "api_token", "")
    with TestClient(app=api.app) as c:
        yield c


class Test운영_경로:
    def test_자격이_없으면_401_이다(self, client) -> None:  # noqa: ANN001
        """**이것이 이 커밋의 이유다.** 그전에는 누구나 수집 기록과 해독률을 봤다."""
        assert client.get(PATH).status_code == 401

    def test_비밀번호가_틀리면_401_이다(self, client) -> None:  # noqa: ANN001
        r = client.get(PATH, headers=_basic(USER, "틀림"))

        assert r.status_code == 401

    def test_아이디가_틀리면_401_이다(self, client) -> None:  # noqa: ANN001
        r = client.get(PATH, headers=_basic("남", PASSWORD))

        assert r.status_code == 401

    def test_맞으면_지나간다(self, client) -> None:  # noqa: ANN001
        """**200 을 안 본다.** 이 경로는 DB 를 읽어서 없으면 500 이다 — 여기서 볼 것은
        **문을 지났나**뿐이라 401·503 이 아니면 됐다."""
        r = client.get(PATH, headers=_basic(USER, PASSWORD))

        assert r.status_code not in (401, 503)

    def test_브라우저가_물을_자리를_알려_준다(self, client) -> None:  # noqa: ANN001
        """**`WWW-Authenticate` 가 없으면 브라우저가 창을 안 띄운다.** 그러면 화면이
        그냥 401 글자로 죽고 운영자가 들어갈 길이 없다."""
        r = client.get(PATH)

        assert r.headers["www-authenticate"].startswith("Basic ")


class Test설정이_비었을_때:
    def test_503_이고_열리지_않는다(self, client, monkeypatch) -> None:  # noqa: ANN001
        """**`api_token` 과 반대다.** 저건 비어 있으면 검사를 끄는데(로컬 편의) 이건
        막는다 — 운영 자료는 사용자 것이 아니라서 잊었을 때 닫히는 쪽이어야 한다."""
        monkeypatch.setattr(settings, "admin_password", "")
        r = client.get(PATH, headers=_basic(USER, PASSWORD))

        assert r.status_code == 503

    def test_아이디만_비어도_막힌다(self, client, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.setattr(settings, "admin_user", "")

        assert client.get(PATH).status_code == 503


class Test제품_경로:
    def test_안_걸린다(self, client) -> None:  # noqa: ANN001
        """**걸면 테스터가 공고를 못 본다.** 운영 문과 제품 문은 다른 자다."""
        assert client.get("/healthz").status_code == 200

    def test_위키도_안_걸린다(self, client) -> None:  # noqa: ANN001
        r = client.get("/api/wiki/c_없는회사/progress")

        assert r.status_code not in (401, 503)


class Test접두사:
    def test_운영_경로가_전부_접두사_아래에_있다(self) -> None:
        """**이것이 「잊을 수가 없다」를 만드는 성질이다.** 라우트마다 의존성을 달면
        새 운영 경로가 생긴 날 하나가 빠지고, 그 하나만 열려 있다.

        `tags=["admin"]` 이 붙은 경로가 전부 `_ADMIN_PREFIX` 아래인지 본다 — 태그만
        붙이고 경로를 다른 데 두면 여기서 걸린다."""
        stray = [
            r.path
            for r in api.app.routes
            if "admin" in getattr(r, "tags", [])
            and not r.path.startswith(api._ADMIN_PREFIX)
        ]

        assert stray == []

    def test_접두사_아래가_전부_운영_경로다(self) -> None:
        """반대 방향이다. **제품 경로가 실수로 `/api/admin/` 아래 서면** 테스터가
        그 경로에서 401 을 받는다."""
        untagged = [
            r.path
            for r in api.app.routes
            if r.path.startswith(api._ADMIN_PREFIX) and "admin" not in getattr(r, "tags", [])
        ]

        assert untagged == []


class Test깨진_입력:
    """**500 이 나면 안 된다.** 사람이 치는 값이라 실제로 들어온다 —
    `require_token` 이 바이트로 바꿔 넣는 것과 같은 자리다."""

    @pytest.mark.parametrize(
        "header",
        [
            "",
            "Basic",
            "Basic ???",  # base64 가 아니다
            "Basic " + base64.b64encode(b"\xff\xfe").decode(),  # utf-8 이 아니다
            "Basic " + base64.b64encode("콜론없음".encode()).decode(),
            "Bearer " + base64.b64encode(b"a:b").decode(),  # 다른 스킴
        ],
    )
    def test_던지지_않고_거절한다(self, header, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.setattr(settings, "admin_user", USER)
        monkeypatch.setattr(settings, "admin_password", PASSWORD)

        assert api._basic_ok(header) is False

    def test_한글_자격도_통과한다(self, monkeypatch) -> None:  # noqa: ANN001
        """**base64 안은 UTF-8 이라 비ASCII 가 실린다.** 헤더 자체가 ASCII 인
        `x-finnect-token` 과 다른 자리다 — 거기는 한글 토큰이 아예 못 오지만
        여기는 온다."""
        monkeypatch.setattr(settings, "admin_user", USER)
        monkeypatch.setattr(settings, "admin_password", PASSWORD)
        raw = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()

        assert api._basic_ok(f"Basic {raw}") is True
