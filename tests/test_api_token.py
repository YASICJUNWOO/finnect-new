"""API 토큰 가드 — ADR-0035.

**이 파일이 지키는 것은 문 하나다.** API 가 Vercel 에서 이 서버로 내려오면서
Vercel Authentication 이 없어졌고, 그 자리를 토큰이 받았다. 가드가 조용히 꺼지면
`POST /api/wiki/{company_id}/files` 가 **인터넷에 열린 업로드 창구**가 된다 —
아무나 아무 회사 이름으로 파일을 밀어 넣고 디스크와 OCR 을 태울 수 있다.

DB 를 안 쓴다. 미들웨어는 라우트에 닿기 전에 끝나므로 **없는 경로로 두드려도** 검사가
증명된다. 그래서 이 테스트는 DB 없이 어디서나 돈다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from finnect.api.app import app
from finnect.config import settings

TOKEN = "test-token-abc123"  # ASCII 다 — HTTP 헤더가 비ASCII 를 못 싣는다

#: 라우트가 없는 경로다. **일부러다** — 미들웨어가 라우팅보다 앞이라 여기서 401 이
#: 나오면 검사가 모든 경로에 걸린다는 뜻이고, 통과하면 404 라 DB 를 안 건드린다.
PROBE = "/api/__없는경로__"


@pytest.fixture
def client_with_token(monkeypatch):
    """토큰을 켠 클라이언트. **`settings` 를 되돌리는 것이 fixture 의 일이다** —
    전역이라 안 되돌리면 뒤따르는 테스트가 통째로 401 을 받는다."""
    monkeypatch.setattr(settings, "api_token", TOKEN)
    with TestClient(app) as c:
        yield c


def test_토큰이_비면_검사하지_않는다(monkeypatch):
    """기본값이다. **로컬은 지금까지처럼 그냥 돈다.**"""
    monkeypatch.setattr(settings, "api_token", "")
    with TestClient(app) as c:
        assert c.get(PROBE).status_code == 404  # 401 이 아니다 — 문을 안 지킨다


def test_토큰이_켜지면_헤더_없이_막힌다(client_with_token):
    r = client_with_token.get(PROBE)
    assert r.status_code == 401
    assert "토큰" in r.json()["detail"]


def test_틀린_토큰도_막힌다(client_with_token):
    r = client_with_token.get(PROBE, headers={"x-finnect-token": "wrong-token"})
    assert r.status_code == 401


def test_맞는_토큰은_통과한다(client_with_token):
    """404 면 통과다. 미들웨어를 지나 라우팅까지 갔다는 뜻이다."""
    assert client_with_token.get(PROBE, headers={"x-finnect-token": TOKEN}).status_code == 404


def test_올리기도_같은_문을_지난다(client_with_token):
    """**이 파일이 있는 이유다.** 읽기만 막고 쓰기를 흘리면 막은 의미가 없다."""
    r = client_with_token.post("/api/wiki/c_test/files")
    assert r.status_code == 401


def test_healthz_는_토큰_없이_열려_있다(client_with_token):
    """systemd 와 리버스 프록시가 두드리는 자리다. 아무것도 흘리지 않는다."""
    r = client_with_token.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
