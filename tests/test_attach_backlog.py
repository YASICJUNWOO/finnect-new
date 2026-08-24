"""첨부 받기 대상 — **이미 받아 둔 것은 대상에 안 들어간다**([ADR-0071](
../docs/adr/0071-첨부-받기를-운영-화면에-연다.md)).

예전에는 전량을 대상으로 잡고 루프 안에서 한 건씩 건너뛰었다. 결과는 같았지만
`report.total` 이 "전량" 을 말했고, 그래서

- `--limit 40` 이 "안 받은 것 40건" 이 아니라 "전량 앞에서 40건" 이었다.
  **이미 받은 것만 40번 건너뛰고 끝나는 실행이 가능했다.**
- 진행 막대의 분모가 3,354 라 2,827건이 끝난 상태에서 84% 에서 시작했다.

여기서 잠그는 것 넷.

1. 받아서 해독까지 된 것은 대상이 아니다
2. **받기가 실패한 것도 대상이 아니다** — 404 를 매번 다시 두드리지 않는다
3. **파일이 디스크에서 사라졌으면 다시 대상이다** — 컬럼만 보면 이걸 놓친다
4. `backlog()` 가 `run()` 이 고르는 것과 **같은 수**를 낸다
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finnect import db
from finnect.attach import service, store
from finnect.config import settings
from finnect.models import Attachment, AttachmentFile, Base, FetchStatus, ParseStatus

TABLES = (Attachment, AttachmentFile)


@pytest.fixture
def sqlite(monkeypatch, tmp_path):  # noqa: ANN001, ANN201
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[t.__table__ for t in TABLES])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(db, "SessionFactory", factory)
    monkeypatch.setattr(service, "SessionFactory", factory)
    monkeypatch.setattr(settings, "attachment_dir", tmp_path / "attachments")
    return factory


#: SQLite 는 BigInteger 를 자동 증가시키지 않는다. 번호를 손으로 준다(`test_dataset.py` 와 같다).
_seq = iter(range(1, 10_000))


def _listed(s, url: str, *, source: str = "bizinfo") -> None:  # noqa: ANN001
    """`attachment` — API 가 준 메타. 여기 있는 URL 이 모집단이다."""
    s.add(
        Attachment(
            id=next(_seq), source=source, external_id=url[-3:], position=0,
            kind="기타", filename=f"{url[-3:]}.hwp", ext="hwp", url=url,
        )
    )


def _stored(s, url: str, data: bytes = b"hwp", *, source: str = "bizinfo") -> str:  # noqa: ANN001
    """받아서 해독까지 끝낸 것. 파일도 실제로 디스크에 둔다."""
    settings.attachment_dir.mkdir(parents=True, exist_ok=True)
    rel = store.put(data)
    s.add(
        AttachmentFile(
            id=next(_seq), url=url, source=source,
            fetch_status=str(FetchStatus.OK), parse_status=str(ParseStatus.OK),
            sha256=store.digest(data), stored_path=rel,
        )
    )
    return rel


class Test대상에서_뺀다:
    def test_끝난_것은_안_센다(self, sqlite) -> None:  # noqa: ANN001
        with sqlite() as s:
            for i in range(5):
                _listed(s, f"http://x/{i:03d}")
            _stored(s, "http://x/000", b"a")
            _stored(s, "http://x/001", b"b")
            s.commit()

            got = service.backlog(s)

        assert got.urls == 5
        assert got.pending == 3, "끝난 둘이 대상에 남아 있다"

    def test_받기가_실패한_것도_안_센다(self, sqlite) -> None:  # noqa: ANN001
        """**404 를 다시 돌릴 때마다 두드리지 않는다.** 다시 보려면 `--redo` 다."""
        with sqlite() as s:
            _listed(s, "http://x/000")
            _listed(s, "http://x/001")
            s.add(
                AttachmentFile(
                    id=next(_seq), url="http://x/000", source="bizinfo",
                    fetch_status=str(FetchStatus.NOT_FOUND), http_status=404,
                )
            )
            s.commit()

            assert service.backlog(s).pending == 1

    def test_파일이_사라지면_다시_대상이다(self, sqlite) -> None:  # noqa: ANN001
        """**컬럼만 보면 이걸 놓친다.** `stored_path` 는 차 있는데 파일이 없다 —
        SQL 로만 세면 빠르지만 지운 파일이 영영 다시 안 받아진다."""
        with sqlite() as s:
            _listed(s, "http://x/000")
            rel = _stored(s, "http://x/000")
            s.commit()

            assert service.backlog(s).pending == 0
            store.abs_path(rel).unlink()
            assert service.backlog(s).pending == 1

    def test_출처로_좁힌다(self, sqlite) -> None:  # noqa: ANN001
        with sqlite() as s:
            _listed(s, "http://b/000", source="bizinfo")
            _listed(s, "http://k/000", source="kstartup")
            s.commit()

            assert service.backlog(s).pending == 2
            assert service.backlog(s, source="kstartup").pending == 1


class Test보고서가_받을_것을_센다:
    """**`run()` 과 `backlog()` 가 같은 수를 말해야 한다.** 화면이 527건이라고 했는데
    눌러 보니 3,354건이 돌면 그 화면은 없느니만 못하다."""

    def test_total_이_안_받은_것이다(self, sqlite, monkeypatch) -> None:  # noqa: ANN001
        with sqlite() as s:
            for i in range(5):
                _listed(s, f"http://x/{i:03d}")
            _stored(s, "http://x/000", b"a")
            _stored(s, "http://x/001", b"b")
            s.commit()
            want = service.backlog(s).pending

        # 네트워크를 안 탄다. **이 테스트가 보는 것은 대상 선정이지 내려받기가 아니다.**
        받은: list[str] = []

        def fake_process(client, s, row, url, source, filename, *, redo, report):  # noqa: ANN001, ANN202, ARG001, PLR0913
            받은.append(url)
            return AttachmentFile(url=url, source=source, fetch_status=str(FetchStatus.OK))

        monkeypatch.setattr(service, "_process", fake_process)
        report = service.run()

        assert report.total == want == 3
        assert report.skipped == 2, "이미 받아 둔 것은 total 밖에서 센다"
        assert 받은 == ["http://x/002", "http://x/003", "http://x/004"]

    def test_limit_이_안_받은_것_중_N건이다(self, sqlite, monkeypatch) -> None:  # noqa: ANN001
        """**예전에는 이미 받은 것만 세 번 건너뛰고 끝났다.**"""
        with sqlite() as s:
            for i in range(5):
                _listed(s, f"http://x/{i:03d}")
            _stored(s, "http://x/000", b"a")
            _stored(s, "http://x/001", b"b")
            _stored(s, "http://x/002", b"c")
            s.commit()

        받은: list[str] = []

        def fake_process(client, s, row, url, source, filename, *, redo, report):  # noqa: ANN001, ANN202, ARG001, PLR0913
            받은.append(url)
            return AttachmentFile(url=url, source=source, fetch_status=str(FetchStatus.OK))

        monkeypatch.setattr(service, "_process", fake_process)
        service.run(limit=2)

        assert 받은 == ["http://x/003", "http://x/004"]

    def test_redo_는_전량이다(self, sqlite, monkeypatch) -> None:  # noqa: ANN001
        with sqlite() as s:
            for i in range(3):
                _listed(s, f"http://x/{i:03d}")
            _stored(s, "http://x/000", b"a")
            s.commit()

        받은: list[str] = []

        def fake_process(client, s, row, url, source, filename, *, redo, report):  # noqa: ANN001, ANN202, ARG001, PLR0913
            받은.append(url)
            return AttachmentFile(url=url, source=source, fetch_status=str(FetchStatus.OK))

        monkeypatch.setattr(service, "_process", fake_process)
        report = service.run(redo=True)

        assert report.total == 3
        assert report.skipped == 0
        assert len(받은) == 3

    def test_only_를_건_뒤에_센다(self, sqlite, monkeypatch) -> None:  # noqa: ANN001
        """**먼저 세면 목록 밖의 끝난 것까지 「건너뜀」에 들어간다.** 40건짜리 목록을
        준 사람이 「2,827건 건너뜀」을 보게 된다."""
        with sqlite() as s:
            for i in range(5):
                _listed(s, f"http://x/{i:03d}")
            _stored(s, "http://x/000", b"a")
            _stored(s, "http://x/001", b"b")
            _stored(s, "http://x/002", b"c")
            s.commit()

        monkeypatch.setattr(
            service, "_process",
            lambda client, s, row, url, source, filename, *, redo, report: AttachmentFile(  # noqa: ANN001, ARG005, PLR0913
                url=url, source=source, fetch_status=str(FetchStatus.OK)
            ),
        )
        report = service.run(only={"http://x/002", "http://x/003"})

        assert report.total == 1, "목록 안에서 안 받은 것은 하나다"
        assert report.skipped == 1, "목록 밖의 끝난 둘은 여기 안 들어간다"


class Test버튼_뒤:
    def test_실패가_자국을_남긴다(self) -> None:
        """**표가 없어서 여기가 유일한 자국이다.** 실패가 '아무 일도 없었음' 과
        구분되지 않으면 버튼은 없느니만 못하다."""
        import time

        from finnect.ingest import jobs

        key = "attach-test-실패"

        def work() -> str:
            raise RuntimeError("디스크가 찼다")

        assert jobs.launch(key, work).started is True
        for _ in range(200):
            if not jobs.running(key):
                break
            time.sleep(0.01)

        got = jobs.outcome_of(key)
        assert got is not None
        assert got.ok is False
        assert "디스크가 찼다" in got.detail

    def test_맛보기의_분모가_받을_것_전부가_아니다(self) -> None:
        """**`--limit 2` 를 건 실행이 0% 에서 끝나면 안 된다.** 386건이 남았어도
        이번에 받기로 한 것이 2건이면 막대의 분모는 2다(`jobs.Progress.goal` 과 같다)."""
        p = service.AttachProgress(total=386, done=2, target=2)
        assert p.goal == 2
        assert p.percent == 100

        전량 = service.AttachProgress(total=386, done=2)
        assert 전량.goal == 386
        assert 전량.percent == 1

    def test_받을_것이_없으면_분모가_없다(self) -> None:
        """**0% 로 그리지 않는다.** 「아직 세는 중」과 「받을 게 없다」는 다르다."""
        assert service.AttachProgress().percent is None

    def test_첫_보고_전에는_진행이_없다(self) -> None:
        """**빈 진행을 깔지 않는다.** 대상을 세는 동안 「0 / 0건」이 서면 그건
        「받을 게 없다」로 읽힌다."""
        import threading

        from finnect.ingest import jobs

        key = "attach-test-진행"
        hold = threading.Event()
        seen: list[object] = []

        def work() -> str:
            seen.append(jobs.progress_of(key))
            hold.wait(timeout=5)
            return "끝"

        assert jobs.launch(key, work).started is True
        for _ in range(200):
            if seen:
                break
            import time

            time.sleep(0.01)
        hold.set()

        assert seen == [None], "수집의 빈 Progress 가 첨부 자리에 깔려 있다"
