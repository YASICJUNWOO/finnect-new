"""데이터셋 초기화·솎기 — docs/dataset.md.

여기서 잠그는 것 다섯.

1. **표본이 멱등하다.** 같은 공고번호는 몇 번을 물어도 같은 답이다
2. **`--yes` 없이는 아무것도 안 지운다.** 되돌릴 수 없는 삭제라 기본이 미리보기다
3. **두 번 솎아도 같다.** 초기화를 다시 돌려도 같은 DB 가 선다
4. **공유하는 원본 파일을 안 지운다.** 저장소가 콘텐츠 주소라 URL 둘이 한 파일을 본다
5. **백업이 왕복한다.** 뜬 것을 되돌리면 행 수가 같다

Postgres 없이 돈다 — 필요한 표만 SQLite 에 만든다.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from finnect import db
from finnect.config import settings
from finnect.dataset import service, store
from finnect.dataset.sample import bucket, keeps
from finnect.dataset.tables import PURGED
from finnect.models import (
    Attachment,
    AttachmentFile,
    Base,
    BizinfoNotice,
    FetchStatus,
    KstartupNotice,
)

TODAY = dt.date(2026, 8, 22)


# ── 표본 ──────────────────────────────────────────────────────────────


class Test표본:
    def test_나머지가_0_이면_남는다(self) -> None:
        assert keeps("174036", 3)  # 174036 % 3 == 0
        assert not keeps("174037", 3)
        assert not keeps("174038", 3)

    def test_modulus_1_이면_전부_남는다(self) -> None:
        """표본을 끄는 값이 None 이 아니라 1 인 것이 이 함수의 계약이다."""
        assert all(keeps(str(n), 1) for n in range(100))

    def test_몇_번을_물어도_같다(self) -> None:
        """**멱등하다.** 무작위 시드를 안 쓴다."""
        ids = [str(n) for n in range(1000, 1100)]
        first = {i: keeps(i, 3) for i in ids}
        for _ in range(5):
            assert {i: keeps(i, 3) for i in ids} == first

    def test_숫자가_아니어도_돈다(self) -> None:
        """출처가 늘어 ID 규칙이 바뀌어도 조용히 틀리지 않게. 지금 이 경로는 안 탄다."""
        assert bucket("PBLN-000-abc", 3) == bucket("PBLN-000-abc", 3)
        assert 0 <= bucket("PBLN-000-abc", 3) < 3

    def test_대략_삼분의_일이_남는다(self) -> None:
        kept = sum(keeps(str(n), 3) for n in range(100_000, 103_000))
        assert kept == 1000

    @pytest.mark.parametrize("bad", [0, -1])
    def test_modulus_가_0_이하면_거절한다(self, bad: int) -> None:
        with pytest.raises(ValueError, match="1 이상"):
            bucket("1", bad)

    def test_빈_공고번호를_거절한다(self) -> None:
        with pytest.raises(ValueError, match="빈 공고번호"):
            bucket("  ", 3)


# ── 목록 파일 ─────────────────────────────────────────────────────────


class Test목록파일:
    def test_빈_줄과_주석을_버린다(self, tmp_path) -> None:  # noqa: ANN001
        p = tmp_path / "keep.txt"
        p.write_text("# 남길 것\n125069\n\n  125477  \n", encoding="utf-8")
        assert service.read_list(p) == {"125069", "125477"}

    def test_출처_접두를_떼어_낸다(self, tmp_path) -> None:  # noqa: ANN001
        p = tmp_path / "keep.txt"
        p.write_text("bizinfo:125069\nkstartup:174036\n", encoding="utf-8")
        assert service.read_list(p) == {"125069", "174036"}

    def test_한_줄도_없으면_거절한다(self, tmp_path) -> None:  # noqa: ANN001
        """**빈 목록으로 솎으면 전량 삭제다.** 사고를 여기서 막는다."""
        p = tmp_path / "keep.txt"
        p.write_text("# 주석뿐\n\n", encoding="utf-8")
        with pytest.raises(ValueError, match="하나도 없다"):
            service.read_list(p)


# ── DB ────────────────────────────────────────────────────────────────


def _biz(ext: str) -> BizinfoNotice:
    return BizinfoNotice(pblancId=ext, pblancNm=f"공고 {ext}", content_hash=f"h{ext}")


def _ks(ext: str) -> KstartupNotice:
    return KstartupNotice(pbanc_sn=ext, biz_pbanc_nm=f"공고 {ext}", content_hash=f"h{ext}")


def _file(i: int, url: str, stored: str) -> AttachmentFile:
    return AttachmentFile(
        id=i, url=url, source="bizinfo", fetch_status=str(FetchStatus.OK),
        sha256=stored.split("/")[-1], stored_path=stored,
    )


@pytest.fixture
def sqlite(monkeypatch, tmp_path):  # noqa: ANN001, ANN201
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[m.__table__ for m in PURGED])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(db, "SessionFactory", factory)
    monkeypatch.setattr(settings, "attachment_dir", tmp_path / "attachments")
    return factory


@pytest.fixture
def 채운다(sqlite):  # noqa: ANN001, ANN201
    """기업마당 6 · K-Startup 6. K-Startup 번호는 3으로 나눈 나머지가 0,1,2 를 돈다."""
    with sqlite() as s:
        for n in range(100, 106):
            s.add(_biz(str(n)))
        for n in (300, 301, 302, 303, 304, 305):
            s.add(_ks(str(n)))
        s.commit()
    return sqlite


class Test초기화:
    def test_yes_가_없으면_안_지운다(self, 채운다) -> None:  # noqa: ANN001
        rep = service.purge(apply=False)
        assert rep.applied is False
        assert rep.tables["bizinfo_notice"] == 6
        with 채운다() as s:
            assert len(list(s.scalars(select(BizinfoNotice)))) == 6

    def test_yes_면_비운다(self, 채운다) -> None:  # noqa: ANN001
        service.purge(apply=True)
        with 채운다() as s:
            assert list(s.scalars(select(BizinfoNotice))) == []
            assert list(s.scalars(select(KstartupNotice))) == []

    def test_첨부_원본_디렉터리를_통째로_지운다(self, 채운다) -> None:  # noqa: ANN001
        """옛 레이아웃 잔재가 남지 않게. 표를 따라가면 `attachment_file` 0행일 때 못 지운다."""
        root = settings.attachment_dir
        (root / "bizinfo" / "0").mkdir(parents=True)
        (root / "bizinfo" / "0" / "123.hwpx").write_bytes(b"x" * 10)
        assert service.counts().files == 1

        service.purge(apply=True)
        assert service.counts().files == 0
        assert root.exists()  # 디렉터리 자체는 다시 만든다


class Test솎기:
    def test_목록에_없으면_지운다(self, 채운다) -> None:  # noqa: ANN001
        rep = service.prune("bizinfo", {"100", "101"}, apply=True)
        assert (rep.before, rep.kept, rep.by_list) == (6, 2, 4)
        with 채운다() as s:
            assert sorted(s.scalars(select(BizinfoNotice.pblancId))) == ["100", "101"]

    def test_표본_밖도_지운다(self, 채운다) -> None:  # noqa: ANN001
        keep = {"300", "301", "302", "303", "304", "305"}
        rep = service.prune("kstartup", keep, samples=3, apply=True)
        # 300 · 303 만 3으로 나누어떨어진다
        assert (rep.by_list, rep.by_sample, rep.kept) == (0, 4, 2)
        with 채운다() as s:
            assert sorted(s.scalars(select(KstartupNotice.pbanc_sn))) == ["300", "303"]

    def test_두_번_솎아도_같다(self, 채운다) -> None:  # noqa: ANN001
        """**멱등하다.** 초기화를 다시 돌려도 같은 DB 가 선다."""
        keep = {str(n) for n in range(300, 306)}
        service.prune("kstartup", keep, samples=3, apply=True)
        second = service.prune("kstartup", keep, samples=3, apply=True)
        assert second.removed == 0
        with 채운다() as s:
            assert sorted(s.scalars(select(KstartupNotice.pbanc_sn))) == ["300", "303"]

    def test_yes_가_없으면_세기만_한다(self, 채운다) -> None:  # noqa: ANN001
        rep = service.prune("bizinfo", {"100"}, apply=False)
        assert (rep.applied, rep.kept) == (False, 1)
        with 채운다() as s:
            assert len(list(s.scalars(select(BizinfoNotice)))) == 6

    def test_다른_출처를_안_건드린다(self, 채운다) -> None:  # noqa: ANN001
        """두 출처의 공고번호가 같은 자릿수라 `--source` 없이는 섞인다."""
        service.prune("bizinfo", {"100"}, apply=True)
        with 채운다() as s:
            assert len(list(s.scalars(select(KstartupNotice)))) == 6

    def test_모르는_출처를_거절한다(self, 채운다) -> None:  # noqa: ANN001
        with pytest.raises(ValueError, match="모르는 출처"):
            service.prune("kstartups", {"1"}, apply=True)


class Test원본파일:
    def test_딸린_첨부와_파일을_지운다(self, 채운다) -> None:  # noqa: ANN001
        root = settings.attachment_dir
        (root / "ab").mkdir(parents=True)
        (root / "ab" / "abc").write_bytes(b"x")
        with 채운다() as s:
            s.add(Attachment(id=1, source="bizinfo", external_id="105", position=1,
                             kind="attachment", filename="양식.hwp", url="u105"))
            s.add(_file(1, "u105", "ab/abc"))
            s.commit()

        rep = service.prune("bizinfo", {"100"}, apply=True)
        assert (rep.attachments, rep.files) == (1, 1)
        assert not (root / "ab" / "abc").exists()
        with 채운다() as s:
            assert list(s.scalars(select(AttachmentFile))) == []

    def test_살아남은_공고가_쓰는_파일은_안_지운다(self, 채운다) -> None:  # noqa: ANN001
        """저장소가 콘텐츠 주소라 URL 이 달라도 같은 파일을 본다.

        그냥 지우면 **행은 있고 파일은 없는** 상태가 된다 — 해독은 성공으로 남고
        원문만 사라져서, 근거를 열 때가 되어서야 걸린다.
        """
        root = settings.attachment_dir
        (root / "ab").mkdir(parents=True)
        (root / "ab" / "same").write_bytes(b"x")
        with 채운다() as s:
            for i, (ext, url) in enumerate([("100", "keep-url"), ("105", "doom-url")], 1):
                s.add(Attachment(id=i, source="bizinfo", external_id=ext, position=1,
                                 kind="attachment", filename="양식.hwp", url=url))
                s.add(_file(i, url, "ab/same"))
            s.commit()

        rep = service.prune("bizinfo", {"100"}, apply=True)
        assert rep.files == 0
        assert (root / "ab" / "same").exists()


class Test백업:
    def test_뜨고_되돌리면_행_수가_같다(self, 채운다, tmp_path) -> None:  # noqa: ANN001
        with 채운다() as s:
            s.add(Attachment(id=1, source="bizinfo", external_id="100", position=1,
                             kind="attachment", filename="양식.hwp", url="u100"))
            s.commit()

        path = tmp_path / "backup.jsonl"
        dumped = store.dump(path)
        assert dumped.rows["bizinfo_notice"] == 6
        assert dumped.rows["kstartup_notice"] == 6
        assert dumped.rows["attachment"] == 1

        service.purge(apply=True)
        assert service.counts().tables["bizinfo_notice"] == 0

        back = store.restore(path)
        assert back.rows == dumped.rows
        assert back.dropped == 0
        with 채운다() as s:
            assert sorted(s.scalars(select(BizinfoNotice.pblancId))) == [
                str(n) for n in range(100, 106)
            ]

    def test_날짜가_왕복한다(self, 채운다, tmp_path) -> None:  # noqa: ANN001
        """JSON 에는 날짜 타입이 없다. 문자열로 나갔다가 날짜로 돌아와야 한다."""
        with 채운다() as s:
            row = s.get(BizinfoNotice, "100")
            row.derived_apply_end = TODAY
            s.commit()

        path = tmp_path / "backup.jsonl"
        store.dump(path)
        service.purge(apply=True)
        store.restore(path)

        with 채운다() as s:
            assert s.get(BizinfoNotice, "100").derived_apply_end == TODAY

    def test_모르는_키를_버리고_센다(self, 채운다, tmp_path) -> None:  # noqa: ANN001
        """백업 이후 컬럼이 줄어도 옛 백업이 통째로 못 쓰게 되지 않는다."""
        path = tmp_path / "backup.jsonl"
        store.dump(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[1] = lines[1].replace('{"pblancId"', '{"없던컬럼":1,"pblancId"')
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        service.purge(apply=True)
        back = store.restore(path)
        assert back.dropped == 1
        assert back.rows["bizinfo_notice"] == 6
