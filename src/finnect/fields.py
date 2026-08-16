"""API 필드 설명 — **출처의 공식 문서에서 옮긴 것만** 담는다.

지어내지 않는다. 문서에 없는 필드는 여기에 없고, 화면은 그걸 '문서에 없음'으로 적는다.
필드 이름만 보고 뜻을 추측해 적으면 그 추측이 L1 추출 스키마 설계까지 따라간다.

근거는 각 상수 위의 URL 이다. 옮겨 적은 날짜를 같이 남긴다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocSource:
    """설명을 어디서 옮겼는지. 화면이 이걸 그대로 밝힌다."""

    label: str
    url: str | None = None


DOCS: dict[str, DocSource] = {
    "bizinfo": DocSource(
        "기업마당 오픈API 안내 — 응답 메시지 상세표 (2026-08-16 확인)",
        "https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi",
    ),
    "kstartup": DocSource(
        "공공데이터포털 K-Startup 사업정보 오픈API 활용가이드 v2.0 — "
        "getAnnouncementInformation01 응답 표 (2026-08-16 확인)"
    ),
}

#: 기업마당 응답 항목명. 2026-08-16 위 문서의 '응답 메시지 상세표'에서 옮겼다.
#: 22개 중 20개가 문서에 있다. pldirSportRealmMlsfcCodeNm 과 updtPnttm 은 없다.
#:
#: 주의. 문서의 응답표는 RSS 형식 이름(title·link·seq·author·description·lcategory·
#: pubDate·reqstDt)과 JSON 형식 이름이 한 표에 섞여 있다. 여기 담은 것은 우리가 실제로
#: 받는 JSON 쪽 이름이다. 문서가 `hashTags` 라고 쓴 필드는 실제 응답에서 `hashtags` 로 온다.
BIZINFO: dict[str, str] = {
    "bsnsSumryCn": "사업개요내용",
    "creatPnttm": "등록일자",
    "excInsttNm": "수행기관명",
    "fileNm": "첨부파일명",
    "flpthNm": "첨부파일경로명",
    "hashtags": "해시태그 (문서 표기는 hashTags, 실제 응답은 hashtags)",
    "inqireCo": "조회수",
    "jrsdInsttNm": "소관기관명",
    "pblancId": "공고ID",
    "pblancNm": "공고명",
    "pblancUrl": "공고URL",
    "pldirSportRealmLclasCodeNm": "지원분야 대분류",
    "printFileNm": "본문출력파일명",
    "printFlpthNm": "본문출력파일경로명",
    "rceptEngnHmpgUrl": "사업신청URL",
    "refrncNm": "문의처",
    "reqstBeginEndDe": "신청기간",
    "reqstMthPapersCn": "사업신청방법",
    "totCnt": "전체건수",
    "trgetNm": "지원대상",
}

#: K-Startup 항목명. 2026-08-16 활용가이드 v2.0 의 getAnnouncementInformation01 응답 표에서 옮겼다.
#: 30개 중 28개가 문서에 있다. biz_aply_url 과 id 는 없다.
#:
#: 문서와 실제 응답이 어긋나는 곳이 셋이다. **우리는 받는 쪽 이름을 따른다.**
#:   문서 aply_exclt_trgt_ctnt → 실제 aply_excl_trgt_ctnt (같은 문서의 XML 예시도 실제 쪽이다)
#:   문서 Rcrt_prgs_yn        → 실제 rcrt_prgs_yn
#:   문서 접수일시 예시 "2012-11-29 00:00:00" → 실제 "20121129" 8자리
#:
#: 그리고 문서 표의 '항목설명' 열이 biz_gdnc_url 과 prch_cnpl_no 두 행에서 서로 바뀌어 있다.
#: 항목명(국문) 열은 맞으므로 그쪽을 옮겼다.
KSTARTUP: dict[str, str] = {
    "aply_excl_trgt_ctnt": "신청제외대상내용",
    "aply_mthd_eml_rcpt_istc": "신청 방법 이메일 접수 설명",
    "aply_mthd_etc_istc": "신청 방법 기타 설명",
    "aply_mthd_fax_rcpt_istc": "신청 방법 팩스 접수 설명",
    "aply_mthd_onli_rcpt_istc": "신청 방법 온라인 접수 설명",
    "aply_mthd_pssr_rcpt_istc": "신청 방법 우편 접수 설명",
    "aply_mthd_vst_rcpt_istc": "신청 방법 방문 접수 설명",
    "aply_trgt": "신청 대상 (예: 청소년,대학생,일반인)",
    "aply_trgt_ctnt": "신청 대상 내용",
    "biz_enyy": "창업 기간 (예: 7년미만,5년미만,3년미만,2년미만,1년미만,예비창업자)",
    "biz_gdnc_url": "사업 안내 URL",
    "biz_pbanc_nm": "지원 사업 공고 명",
    "biz_prch_dprt_nm": "사업 담당자 부서명",
    "biz_trgt_age": "대상 연령 (예: 만 20세 미만, 만 20세 이상 ~ 만 39세 이하, 만 40세 이상)",
    "detl_pg_url": "상세페이지URL",
    "intg_pbanc_biz_nm": "통합 공고 사업 명",
    "intg_pbanc_yn": "통합 공고 여부",
    "pbanc_ctnt": "공고 내용",
    "pbanc_ntrp_nm": "창업 지원 기관명",
    "pbanc_rcpt_bgng_dt": "공고 접수 시작 일시",
    "pbanc_rcpt_end_dt": "공고 접수 종료 일시",
    "pbanc_sn": "공고일련번호",
    "prch_cnpl_no": "담당자 연락처",
    "prfn_matr": "우대 사항",
    "rcrt_prgs_yn": "모집진행여부 (문서 표기는 Rcrt_prgs_yn)",
    "sprv_inst": "주관 기관",
    "supt_biz_clsfc": "지원 분야",
    "supt_regin": "지역명",
}

#: 우리가 붙인 컬럼. API 가 준 것이 아니라 이 저장소가 만든 것이라 근거가 코드 자신이다.
OURS: dict[str, str] = {
    "extra": "API_FIELDS 에 없던 필드를 담아 둔 곳. 조용히 버리지 않으려고 있다",
    "derived_apply_start": "접수 시작일. 원문 문자열에서 우리가 파싱한 값",
    "derived_apply_end": "접수 마감일. 원문 문자열에서 우리가 파싱한 값",
    "content_hash": "원문 item 의 SHA-256. K-Startup 은 수정일시가 없어 이것뿐이다",
    "first_seen_at": "이 공고를 처음 받은 시각",
    "last_seen_at": "마지막으로 응답에 있던 시각. 내용이 안 바뀌어도 갱신된다",
    "changed_at": "내용이 마지막으로 바뀐 시각",
    "raw_fetch_id": "이 행을 만든 응답. raw_fetch 에 원문이 통째로 있다",
}

_BY_SOURCE: dict[str, dict[str, str]] = {
    "bizinfo": BIZINFO,
    "kstartup": KSTARTUP,
}


def describe(source: str, field: str) -> str | None:
    """공식 문서가 말하는 항목명. 문서에 없으면 None.

    None 과 빈 문자열을 구분한다. None 은 '문서에 없다'는 사실이고,
    화면은 그걸 그대로 보여야 한다. 빈칸으로 두면 설명이 있는 필드와 구별이 안 된다.
    """
    if field in OURS:
        return OURS[field]
    return _BY_SOURCE.get(source, {}).get(field)


def coverage(source: str, fields: list[str]) -> tuple[int, int]:
    """(문서에 있는 수, 전체 수). 화면이 '20/22' 로 정직하게 적을 수 있게."""
    known = sum(1 for f in fields if describe(source, f) is not None)
    return known, len(fields)
