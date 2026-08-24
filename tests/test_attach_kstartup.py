"""K-Startup 상세 페이지 첨부 긁기 — plan/13.

**API 가 첨부 필드를 안 준다.** 공고 31,327건 중 29,789건(95.1%)에 첨부가 0건이었고,
평가 정보가 공고 본문에 0% 라 그 95% 는 자격 요건도 양식도 없는 상태다.

여기서 검증하는 것은 넷이다 — 마감 우회, 파일명 추출, **재수집이 안 지운다는 것**,
**`ids` 로 좁히면 그 밖은 안 본다는 것**(2026-08-24 — `ingest.service.execute()` 가
모집중만 받은 직후 이걸로 부른다).
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finnect.attach import kstartup
from finnect.ingest import kstartup as ingest_kstartup
from finnect.models import Attachment, Base, KstartupNotice, Source

ONGOING = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn=1"

#: 실물 구조를 줄인 것. 파일명은 `file_bg` 의 title 에 있고 링크 텍스트는 `다운로드` 다.
HTML = """
<div class="board_file">
  <div class="div_downAll">
    <button class="btn_down btn_downAll" onclick="fn_downloadAll();">첨부파일 일괄 다운로드</button>
  </div>
  <ul>
    <li class="clear">
      <a class="file_bg" style="cursor: auto;"
         title="[첨부파일] 200401_모집공고(연장).hwp">200401_모집공고(연장).hwp</a>
      <div class="btn_wrap"><ul>
        <li><a href="javascript:void(0)" onclick="fnPdfView('0FOmn')"
               class="btn_view"><span>바로보기</span></a></li>
        <li><a href="/afile/fileDownload/0FOmn" class="btn_down"
               name="downloadBtn"><span>다운로드</span></a></li>
      </ul></div>
    </li>
    <li class="clear">
      <a class="file_bg"
         title="[첨부파일] 붙임2. 사업계획서 양식.hwpx">붙임2. 사업계획서 양식.hwpx</a>
      <div class="btn_wrap"><ul>
        <li><a href="/afile/fileDownload/WFOmn"
               class="btn_down"><span>다운로드</span></a></li>
      </ul></div>
    </li>
  </ul>
</div>
"""


def test_마감_공고는_deadline_주소로_바꾼다() -> None:
    """**29,789건 중 29,515건(99.1%)이 마감이라 사실상 전부에 필요하다.**

    안 바꾸면 18KB 짜리 빈 껍데기가 온다 — 실측 4/4 에서 첨부 링크가 0개였다.
    """
    assert "bizpbanc-deadline.do" in kstartup.detail_url(ONGOING, "N")
    assert "bizpbanc-ongoing.do" not in kstartup.detail_url(ONGOING, "N")


def test_모집중_공고는_주소를_안_바꾼다() -> None:
    assert kstartup.detail_url(ONGOING, "Y") == ONGOING


def test_상태를_모르면_마감으로_친다() -> None:
    """모르는 값에 ongoing 을 주면 껍데기가 오고 첨부가 조용히 0개가 된다."""
    for unknown in (None, "", "X"):
        assert "bizpbanc-deadline.do" in kstartup.detail_url(ONGOING, unknown)


def test_낡은_모집중_상태를_주소로_되짚는다() -> None:
    """**`rcrt_prgs_yn` 은 적재 시점의 값이라 그 뒤에 마감된 공고는 `Y` 로 남는다.**

    2026-08-19 실측에서 모집중 50건 중 7건이 그랬다. `178876` 은 접수마감이
    `20260817` 인데 `Y` 였고, ongoing 은 18,783자 껍데기 · deadline 은 108,876자에
    첨부 1개였다. 껍데기가 오면 반대쪽을 한 번 더 봐야 그 일곱을 잃지 않는다.
    """
    assert kstartup.flip_url(ONGOING) == kstartup.detail_url(ONGOING, "N")
    assert kstartup.flip_url(kstartup.detail_url(ONGOING, "N")) == ONGOING


def test_파일명을_title_에서_가져온다() -> None:
    """**링크 텍스트로 잡으면 전부 '다운로드' 가 된다.**"""
    pairs = kstartup.parse_attachments(HTML)

    assert [n for n, _ in pairs] == ["200401_모집공고(연장).hwp", "붙임2. 사업계획서 양식.hwpx"]
    assert all("다운로드" not in n for n, _ in pairs)


def test_주소를_절대경로로_만든다() -> None:
    pairs = kstartup.parse_attachments(HTML)

    assert [u for _, u in pairs] == [
        "https://www.k-startup.go.kr/afile/fileDownload/0FOmn",
        "https://www.k-startup.go.kr/afile/fileDownload/WFOmn",
    ]


def test_바로보기_링크를_첨부로_세지_않는다() -> None:
    """`fnPdfView` 는 미리보기라 파일이 아니다. 세면 첨부 수가 두 배가 된다."""
    assert len(kstartup.parse_attachments(HTML)) == 2


def test_첨부가_없는_페이지는_빈_목록이다() -> None:
    assert kstartup.parse_attachments("<html><body>없어요</body></html>") == []


def test_재수집이_긁은_첨부를_안_지운다() -> None:
    """**이게 가장 비싼 성질이다.**

    `ingest/runner.py` 의 `_flush` 가 갱신 시 `attachment` 를 통째로 지우는데, 대상이
    **"이번 적재에 첨부가 딸려 온 공고"** 로 한정된다(`if r.attachments`). K-Startup
    정규화기가 `attachments=[]` 를 내는 한 그 목록에 안 들어간다.

    이게 깨지면 **4.4시간 긁은 것이 10분짜리 재수집에 날아간다.**
    """
    import httpx

    with httpx.Client() as c:
        adapter = ingest_kstartup.KstartupAdapter(c)
        normalized = adapter.normalize({"pbanc_sn": "1", "biz_pbanc_nm": "테스트 공고"})

    assert normalized is not None, "정규화가 아무것도 안 냈다"
    assert normalized.attachments == [], (
        "K-Startup 이 첨부를 내기 시작했다. _flush 가 긁은 첨부를 지운다"
    )


def _db():  # noqa: ANN202
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[KstartupNotice.__table__, Attachment.__table__])
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def test_ids로_좁히면_그_밖은_안_본다() -> None:
    """**`--limit` 만으로는 안 되는 이유다.** 정렬이 `rcrt_prgs_yn` 기준이라 낡은 `Y`
    잔여분이 진짜 모집중과 같은 순위에 섞인다 — 개수로 끊으면 엉뚱한 게 걸릴 수 있다.
    `ids` 는 애초에 그 표 밖을 보지 않는다.
    """
    with _db()() as s:
        s.add_all(
            [
                KstartupNotice(pbanc_sn="1", content_hash="h1", detl_pg_url="u1", rcrt_prgs_yn="Y"),
                KstartupNotice(pbanc_sn="2", content_hash="h2", detl_pg_url="u2", rcrt_prgs_yn="Y"),
                # 첨부 없는 잔여분. ids 밖이니 안 걸려야 한다 — 지금 실제로 수천 건이다.
                KstartupNotice(
                    pbanc_sn="99", content_hash="h99", detl_pg_url="u99", rcrt_prgs_yn="Y"
                ),
            ]
        )
        s.flush()

        targets = kstartup._targets(s, limit=None, redo=False, ids=["1", "2"])

    assert {sn for sn, _, _ in targets} == {"1", "2"}


def test_ids_안에서도_이미_첨부있으면_건너뛴다() -> None:
    """`ids` 는 범위를 좁힐 뿐이다. `redo=False` 면 이미 긁은 것은 여전히 건너뛴다."""
    with _db()() as s:
        s.add_all(
            [
                KstartupNotice(pbanc_sn="1", content_hash="h1", detl_pg_url="u1", rcrt_prgs_yn="Y"),
                KstartupNotice(pbanc_sn="2", content_hash="h2", detl_pg_url="u2", rcrt_prgs_yn="Y"),
            ]
        )
        s.add(
            Attachment(
                id=1,
                source=str(Source.KSTARTUP),
                external_id="1",
                position=0,
                kind="other",
                filename="이미있음.hwp",
                ext="hwp",
                url="https://example.com/a",
            )
        )
        s.flush()

        targets = kstartup._targets(s, limit=None, redo=False, ids=["1", "2"])

    assert {sn for sn, _, _ in targets} == {"2"}


def test_ids_없으면_예전처럼_표_전체를_본다() -> None:
    """`ids=None` 이 기본값이다 — 독립 실행(`--scrape-kstartup`)의 기존 동작을 안 바꾼다."""
    with _db()() as s:
        s.add_all(
            [
                KstartupNotice(pbanc_sn="1", content_hash="h1", detl_pg_url="u1", rcrt_prgs_yn="Y"),
                KstartupNotice(
                    pbanc_sn="99", content_hash="h99", detl_pg_url="u99", rcrt_prgs_yn="N"
                ),
            ]
        )
        s.flush()

        targets = kstartup._targets(s, limit=None, redo=False, ids=None)

    assert {sn for sn, _, _ in targets} == {"1", "99"}
