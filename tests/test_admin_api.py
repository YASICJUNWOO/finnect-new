"""운영 API — **집계 질의가 정본과 같은 답을 내는지**.

`api/admin_service.py` 가 `attach/service.py` 의 `coverage()` · `ocr_candidates()` 를
**다시 쓴 것이다.** 임포트하지 않은 이유는 저 모듈이 `httpx` 와 파서를 끌고 오는데
`requirements.txt` 가 서버리스 함수에서 그것들을 뺐기 때문이다(ADR-0027).

베낀 질의는 갈린다. 갈리면 로컬 `attach --report` 와 배포 화면의 숫자가 달라지고,
**둘 다 그럴듯해서 어느 쪽이 틀렸는지 알 수 없다.** 그래서 여기서 잠근다.

DB 가 필요한 테스트다. 없으면 건너뛴다 — CI 에 DB 를 붙이는 것은 아직 안 정했다.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from finnect.api import admin_service
from finnect.db import SessionFactory


@pytest.fixture
def session():  # noqa: ANN201
    try:
        with SessionFactory() as s:
            s.execute(__import__("sqlalchemy").text("select 1"))
            yield s
    except OperationalError:
        pytest.skip("DB 가 없다. `docker compose up -d db` 뒤에 다시 돈다")


class Test정본과_같은_답을_낸다:
    """`attach/service.py` 를 직접 불러 나란히 놓고 본다.

    이 테스트만은 `attach.service` 를 임포트한다. **로컬 개발 의존성에는 httpx 가 있고**,
    비교 대상이 정본이어야 비교가 성립한다.
    """

    def test_coverage_가_같다(self, session) -> None:  # noqa: ANN001
        from finnect.attach import service as canonical

        want = canonical.coverage(session)
        got = admin_service.attachments(session).coverage

        assert got.listed == want["listed"]
        assert got.urls == want["urls"]
        assert got.files == want["files"]
        assert got.unaccounted == want["unaccounted"]

        assert [(r.status, r.count) for r in got.fetch] == list(want["fetch"])
        assert [(r.status, r.count) for r in got.parse] == list(want["parse"])

        assert [
            {"ext": r.ext, "status": r.status, "count": r.count, "avg_chars": r.avg_chars}
            for r in got.by_ext
        ] == want["by_ext"]

    def test_ocr_후보가_같다(self, session) -> None:  # noqa: ANN001
        from finnect.attach import service as canonical

        want = canonical.ocr_candidates(session)
        got = admin_service.attachments(session).ocr

        assert got.pdf_empty == want["pdf_empty"]
        assert got.images == want["images"]
        assert got.image_notices == want["image_notices"]


class Test배포_의존성만으로_돈다:
    """**API 가 수집기와 파서 없이 임포트돼야 한다.**

    `requirements.txt` 가 httpx·pdfplumber·olefile 을 뺐다. 실수로 `attach.service` 를
    임포트하면 로컬에서는 통과하고 **배포본만 `ModuleNotFoundError` 로 죽는다** —
    가장 늦게, 가장 안 좋은 자리에서 터지는 종류다.
    """

    def test_admin_service_는_수집기를_안_끌고_온다(self) -> None:
        import sys

        # 이미 다른 테스트가 올려 뒀을 수 있으니 모듈 그래프를 직접 본다.
        import finnect.api.admin_service  # noqa: F401

        seen = set(sys.modules)
        # admin_service 가 import 하는 것들만 따라가면 되지만, 그 판정 자체가 이 테스트의
        # 대상이라 손으로 적지 않는다. 대신 **금지 모듈이 admin_service 의 참조에 없는지** 본다.
        blocked = {"httpx", "pdfplumber", "olefile"}
        refs = {
            v.__name__
            for v in vars(finnect.api.admin_service).values()
            if isinstance(v, type(sys)) and hasattr(v, "__name__")
        }
        assert not (refs & blocked), f"금지 모듈을 참조한다: {refs & blocked}"
        assert "finnect.attach.service" not in refs
        del seen

    def test_api_app_이_httpx_없이_로드된다(self) -> None:
        """실제로 막아 놓고 import 해 본다. 참조 검사보다 이게 진짜 시험이다."""
        import builtins
        import importlib
        import sys

        blocked = {"httpx", "pdfplumber", "olefile"}
        real = builtins.__import__

        def guard(name: str, *args: object, **kwargs: object):  # noqa: ANN202
            if name.split(".")[0] in blocked:
                raise ModuleNotFoundError(f"배포본에 없는 모듈이다: {name}")
            return real(name, *args, **kwargs)

        # 이미 sys.modules 에 있으면 import 문이 guard 를 안 타서 시험이 헛돈다.
        dropped = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("finnect")}
        builtins.__import__ = guard
        try:
            mod = importlib.import_module("finnect.api.app")
            paths = {r.path for r in mod.app.routes}  # type: ignore[attr-defined]
            assert "/api/admin/notices" in paths
            assert "/api/admin/attachments" in paths
            assert "/api/admin/ingest" in paths
        finally:
            builtins.__import__ = real
            sys.modules.update(dropped)


class Test목록:
    def test_마감된_공고를_빼지_않는다(self, session) -> None:  # noqa: ANN001
        """제품 목록은 기본이 `open_only=True` 다. **여기는 전량이 모집단이다.**"""
        from sqlalchemy import func, select

        from finnect.views import Notice

        everything = session.scalar(select(func.count()).select_from(Notice)) or 0
        got = admin_service.list_notices(session, page=1)
        assert got.total == everything

    def test_모르는_정렬은_마감순으로_떨어진다(self, session) -> None:  # noqa: ANN001
        """URL 을 손으로 고친 사람에게 500 을 주지 않는다."""
        got = admin_service.list_notices(session, sort="없는정렬")
        assert got.sort == "deadline"

    def test_페이지_크기가_50이다(self, session) -> None:  # noqa: ANN001
        got = admin_service.list_notices(session, page=1)
        assert got.page_size == 50
        assert len(got.items) <= 50


class Test상세:
    def test_모르는_출처는_None_이다(self, session) -> None:  # noqa: ANN001
        assert admin_service.get_notice(session, "youth", "1") is None

    def test_없는_공고는_None_이다(self, session) -> None:  # noqa: ANN001
        assert admin_service.get_notice(session, "bizinfo", "없는-것") is None

    def test_extra_는_ours_에_두_번_안_나온다(self, session) -> None:  # noqa: ANN001
        """`extra` 는 전용 자리가 있다. 컬럼 표에도 나오면 같은 값을 두 번 그린다."""
        got = admin_service.list_notices(session, source="bizinfo", page=1)
        if not got.items:
            pytest.skip("기업마당 공고가 없다")
        d = admin_service.get_notice(session, "bizinfo", got.items[0].external_id)
        assert d is not None
        assert "extra" not in {f.name for f in d.ours}

    def test_인증키가_원문_url_에_안_남는다(self, session) -> None:  # noqa: ANN001
        """`ingest/base.py` `mask()` 가 저장 전에 지운다. **화면까지 새면 안 된다.**"""
        got = admin_service.list_notices(session, source="bizinfo", page=1)
        if not got.items:
            pytest.skip("기업마당 공고가 없다")
        d = admin_service.get_notice(session, "bizinfo", got.items[0].external_id)
        assert d is not None
        if d.raw is None:
            pytest.skip("raw_fetch 가 없는 공고다")
        assert "crtfcKey=***" in d.raw.request_url or "crtfcKey" not in d.raw.request_url
