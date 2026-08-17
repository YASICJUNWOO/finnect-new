"""상세 화면의 원문 전개 — 응답 통째에서 이 공고의 item 만 갈라 내는 부분.

**응답 하나에 공고가 최대 1,538건 들어온다**(기업마당 `searchCnt=2000`, 3.67MB).
그대로 화면에 펴면 못 읽으므로 봉투와 해당 item 을 가른다. 이 가르는 규칙이
출처마다 다르고(`jsonArray` vs `data`, `pblancId` vs `pbanc_sn`) 조용히 틀리면
**원문이 비어 보이는데 화면은 200 을 준다.** 그래서 테스트를 둔다.

2026-08-17 `admin/app.py` 에서 `api/admin_service.py` 로 옮겼다(ADR-0027).
화면이 Next.js 로 갔고 이 함수는 그 화면을 먹이는 API 쪽에 산다. 규칙은 안 바뀌었다.
"""

from __future__ import annotations

import json

from finnect.api.admin_service import _split_payload

BIZINFO = {
    "jsonArray": [
        {"pblancId": "PBLN_1", "pblancNm": "가", "totCnt": 3},
        {"pblancId": "PBLN_2", "pblancNm": "나", "totCnt": 3},
        {"pblancId": "PBLN_3", "pblancNm": "다", "totCnt": 3},
    ]
}

KSTARTUP = {
    "currentCount": 2,
    "matchCount": 29789,
    "totalCount": 29789,
    "data": [
        {"pbanc_sn": "178906", "biz_pbanc_nm": "가"},
        {"pbanc_sn": "178907", "biz_pbanc_nm": "나"},
    ],
}


class Test내_공고를_찾는다:
    def test_기업마당은_pblancId_로_찾는다(self) -> None:
        _, item, siblings = _split_payload(BIZINFO, "bizinfo", "PBLN_2")
        assert json.loads(item)["pblancNm"] == "나"
        assert siblings == 3

    def test_kstartup은_pbanc_sn_으로_찾는다(self) -> None:
        _, item, siblings = _split_payload(KSTARTUP, "kstartup", "178907")
        assert json.loads(item)["biz_pbanc_nm"] == "나"
        assert siblings == 2

    def test_pbanc_sn_이_숫자로_와도_찾는다(self) -> None:
        """DB 는 String 인데 API 가 int 로 줄 수 있다. 문자열로 맞춰 비교한다."""
        payload = {"matchCount": 1, "data": [{"pbanc_sn": 178906, "biz_pbanc_nm": "가"}]}
        _, item, _ = _split_payload(payload, "kstartup", "178906")
        assert item is not None


class Test봉투는_공고_배열을_뺀다:
    def test_기업마당_봉투는_비어_있다(self) -> None:
        """기업마당은 jsonArray 하나뿐이라 빼면 남는 것이 없다. totCnt 는 item 안에 있다."""
        envelope, _, _ = _split_payload(BIZINFO, "bizinfo", "PBLN_1")
        assert json.loads(envelope) == {}

    def test_kstartup_봉투에_matchCount_가_남는다(self) -> None:
        envelope, _, _ = _split_payload(KSTARTUP, "kstartup", "178906")
        got = json.loads(envelope)
        assert got["matchCount"] == 29789
        assert "data" not in got


class Test못_찾는_경우:
    def test_없는_id_는_None_이다(self) -> None:
        """빈 dict 가 아니라 None 이어야 화면이 '못 찾았다'를 적을 수 있다."""
        _, item, siblings = _split_payload(BIZINFO, "bizinfo", "PBLN_없음")
        assert item is None
        assert siblings == 3

    def test_모르는_출처는_item_을_못_찾는다(self) -> None:
        _, item, siblings = _split_payload(BIZINFO, "youth", "PBLN_1")
        assert item is None
        assert siblings == 0

    def test_payload_가_dict_가_아니면_통째로_보여준다(self) -> None:
        envelope, item, siblings = _split_payload([1, 2], "bizinfo", "PBLN_1")
        assert json.loads(envelope) == [1, 2]
        assert item is None
        assert siblings == 0

    def test_배열이어야_할_자리가_배열이_아니어도_안_터진다(self) -> None:
        """봉투 없는 응답이 raw_fetch 에 남아 있을 수 있다. 화면이 500 을 내면 안 된다."""
        envelope, item, siblings = _split_payload({"jsonArray": None}, "bizinfo", "PBLN_1")
        assert json.loads(envelope) == {}
        assert item is None
        assert siblings == 0


class Test한글은_그대로_쓴다:
    def test_유니코드를_이스케이프하지_않는다(self) -> None:
        """\\uac00 으로 나오면 원문 대조가 안 된다. 이 화면의 목적이 코퍼스 관찰이다."""
        _, item, _ = _split_payload(BIZINFO, "bizinfo", "PBLN_1")
        assert '"가"' in item
