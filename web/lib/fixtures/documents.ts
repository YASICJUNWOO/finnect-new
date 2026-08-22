/** 실제 공고 셋에서 뽑은 고정 데이터. **지어낸 값이 하나도 없다.**
 *
 * plan/11 T-0039 가 파이프라인(T-0035~T-0038)보다 먼저 서기 위한 재료다.
 * 화면이 "항목 102개를 어떻게 접을 것인가" 를 먼저 물어야 그 답이
 * `document_item` 스키마에 들어간다. 나중에 만들면 스키마를 고치게 된다.
 *
 * 셋이 범위를 덮는다.
 * - `pohang` 긴 지시문(최장 2,031자) · 트리 2단 · narrative + fields 한 파일
 * - `ai`     최악의 밀도 — 최상위 67 · 칸 199
 * - `empty`  양식이 첨부에 없다. 공고문이 "신청 버튼을 누르면 안내" 라고 말한다
 *
 * 뽑은 방법은 docs/plan/11-작성-항목-추출과-표시.md T-0039 에 있다.
 * 목차 점선이 깨진 꼬리(`사업목표鰾ȃ00`)만 털었고 나머지는 원문 그대로다. */

import type { NoticeDocuments } from "@/lib/documents";

export const FIXTURES: Record<string, NoticeDocuments> = {
  "pohang": {
    "notice": {
      "id": "PBLN_000000000125069",
      "source": "bizinfo",
      "title": "[경북] 포항시 2026년 2차 지역산업위기대응 맞춤형 지원사업 참여기업 모집 통합 공고",
      "url": "https://www.bizinfo.go.kr/sii/siia/selectSIIA200Detail.do?pblancId=PBLN_000000000125069"
    },
    "documents": [
      {
        "id": "pohang-plan",
        "title": "[붙임2] 2026년 경북 포항시 지역산업위기대응 맞춤형 지원사업 신청서식.hwp",
        "kind": "narrative",
        "sha256": "",
        "ext": null,
        "attachment": {
          "filename": "[붙임2] 2026년 경북 포항시 지역산업위기대응 맞춤형 지원사업 신청서식.hwp",
          "url": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_000000000767525&fileSn=1"
        },
        "items": [
          {
            "number": "2",
            "title": "추진배경 및 목표",
            "instruction": null,
            "inputKind": "narrative",
            "children": [
              {
                "number": "2-1",
                "title": "사업수행 배경 및 목적",
                "instruction": "사업 수행 배경 및 필요성, 과제추진 목적, 규모 및 내용 등에 대하여 자세하게 기술 ※ 대상기술의 간략한 내용 및 기존 기술과의 차별성, 산업 동향에 따른 사업 전략과의 관계 제시",
                "inputKind": "narrative",
                "children": []
              },
              {
                "number": "2-2",
                "title": "지원필요성",
                "instruction": "산업위기에 따른 기업지원 필요성 (중요) ※ 철강산업 위기에 따른 애로사항 중심으로 필요성(중요성), 시의성 등을 구체적으로 기술",
                "inputKind": "narrative",
                "children": []
              },
              {
                "number": "2-3",
                "title": "사업내용 및 위기대응 계획",
                "instruction": "사업수행을 통해 달성하고자 하는 최종 목표 및 내용 서술",
                "inputKind": "narrative",
                "children": []
              }
            ]
          },
          {
            "number": "3",
            "title": "사업추진 계획 및 내용",
            "instruction": null,
            "inputKind": "narrative",
            "children": [
              {
                "number": "3-1",
                "title": "제품 및 기술 현황",
                "instruction": "지원 대상 제품 및 기술에 대한 내용 작성 ※ 핵심기술, 목표시장, 경쟁우위요소 등 작성 ※ 필요시 제품(기술)의 사진, 기본 개념도 추가 가능",
                "inputKind": "narrative",
                "children": []
              },
              {
                "number": "3-2",
                "title": "사업추진 세부계획",
                "instruction": "사업 목표를 달성하기 위한 계획 및 방법에 대한 내용을 자유롭게 기술 ※ 신청내용에 맞은 추진계획과 전략 등을 구체적으로 작성 (하단의 작성예시 참고 필수) (중요)",
                "inputKind": "narrative",
                "children": []
              },
              {
                "number": "3-3",
                "title": "추진일정",
                "instruction": "추진일정은 Bar Chart로 표시하고, 각 내용별 선, 후행 관계를 명확히 표기",
                "inputKind": "narrative",
                "children": []
              }
            ]
          },
          {
            "number": "4",
            "title": "사업비 집행계획",
            "instruction": "기업부담금은 의무사항이 아니며, 프로그램별 지원금 한도를 초과하여 예산이 소요되는 경우 초과분에 한하여 기업부담금에 편성 (전액 현금) ※ 부가가치세(VAT)는 사업비에 포함되지 않으며, 기업비 별도 부담함 (사업비 산정에서 제외) ※ 소모성 재료(실험∙실습 기자재, 시약, 시료 구입비 / 직접 제작 또는 시공하는 기계∙기구에 소요되는 재료비)는 편성이 가능하나 영구적인 제품은 자산취득으로 보아 구매 불가 ※ 재료비는 상세명세와 소요량을 산정하여 과다 계상 금지",
            "inputKind": "narrative",
            "children": [
              {
                "number": "4-1",
                "title": "사업비 총괄",
                "instruction": null,
                "inputKind": "narrative",
                "children": []
              },
              {
                "number": "4-2",
                "title": "사업비 세부내역",
                "instruction": null,
                "inputKind": "narrative",
                "children": []
              }
            ]
          },
          {
            "number": "5",
            "title": "성과활용계획",
            "instruction": "사업수행의 결과로 얻어진 결과(성과)물을 활용한 구체적인 향후 전략 및 활용방안 작성 ※ 제품화/상용화 전략, 판매/마케팅 전략, 신규시장 확보, 후속사업 연계 등",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "6",
            "title": "기대효과",
            "instruction": "사업수행 결과에 따른 정량적(객관적 수치) 및 정성적 기대효과 작성",
            "inputKind": "narrative",
            "children": [
              {
                "number": "6-1",
                "title": "정량적 성과",
                "instruction": null,
                "inputKind": "narrative",
                "children": []
              },
              {
                "number": "6-2",
                "title": "정성적 성과",
                "instruction": null,
                "inputKind": "narrative",
                "children": []
              }
            ]
          }
        ]
      },
      {
        "id": "pohang-form",
        "title": "신청서 · 서식",
        "kind": "fields",
        "sha256": "",
        "ext": null,
        "attachment": {
          "filename": "[붙임2] 2026년 경북 포항시 지역산업위기대응 맞춤형 지원사업 신청서식.hwp",
          "url": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_000000000767525&fileSn=1"
        },
        "items": [
          {
            "number": null,
            "title": "기업정보",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "설 립 일",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "대표자명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "주 소",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "공장",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "연구소",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "주생산품",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "지원신청 프로그램 (√체크) ※중복지원 가능",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "□ 제품고급화",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "□ AI·디지털 전환지원",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "□ IP&R&D전략",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "□ 마케팅",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "□ 스마트물류 내비게이션",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "총 사업비 (천원)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "신청기업 주요현황 (천원,명)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "매출액",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "수출",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "종업원수 (고용보험가입자)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "담 당 자",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "휴 대 폰",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "기 업 명 :",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "필수",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "■ 사업자등록증 사본 1부",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "선택",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "■ 공장등록증 사본 1부",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "지 원 프로그램",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "사 업 명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "사업기간",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "사 업 비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "수행기업명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "제품(기술) 이미지",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "번호",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "총소요비용 (VAT제외)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "항 목",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "순번",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "지표명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "매출",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "사업수행결과물의 예상 매출액(B)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "사업수행결과물의 점유비율(C=B/A)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "고용",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "신규고용수",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "자율 지표",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "별첨1",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "별첨2",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "성명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "검토내용",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "기업 현황",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "사업자등록번호",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "담당자",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "부 서 명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          }
        ]
      }
    ],
    "submitHint": null,
    "undecided": 0
  },
  "ai": {
    "notice": {
      "id": "PBLN_000000000125417",
      "source": "bizinfo",
      "title": "2026년 2차 독자 AI 파운데이션 모델 프로젝트 공동활용 데이터 지원사업 공고",
      "url": "https://www.bizinfo.go.kr/sii/siia/selectSIIA200Detail.do?pblancId=PBLN_000000000125417"
    },
    "documents": [
      {
        "id": "ai-plan",
        "title": "붙임2_사업수행계획서 등 관련 서식.hwp",
        "kind": "narrative",
        "sha256": "",
        "ext": null,
        "attachment": {
          "filename": "붙임2_사업수행계획서 등 관련 서식.hwp",
          "url": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_000000000769075&fileSn=2"
        },
        "items": [
          {
            "number": "1",
            "title": "사업목표",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "추진방안 및 전략",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3",
            "title": "최종목표 평가기준",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "공동활용 데이터 개요",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "과제 관련 데이터 구축ㆍ활용 내용",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3",
            "title": "데이터 권원 및 저작권 등 확보 전략",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "과제 추진체계",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "사업 추진 일정",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "사업비 총괄표",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "수행기관별 예산 분담 계획",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3",
            "title": "비목별 총괄표",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "4",
            "title": "예산 세부 계획",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "과 제 명",
            "instruction": "사업계획서 본문의 ‘I. 추진목표 및 전략’ 부분을 참조하여 공동활용 데이터 공급계획에 대한 목표 기술",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "6",
            "title": "과제내용",
            "instruction": "목표를 달성하기 위한 과제의 사업범위 및 주요 추진과업 내용을 요약하며, 참여기관이 있는 경우 과업 구분을 명확히 나누어 제시 ㅇ 주관기관(기관명) - 과제 수행내용 및 추진일정 ㅇ 참여기관1(기관명) - 수행내용 및 추진일정 ㅇ 참여기관2(기관명) - 수행내용 및 추진일정",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "7",
            "title": "최종결과물(산출물)",
            "instruction": "과제 결과물의 종류와 내용 등에 대하여 요약 기술",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "8",
            "title": "사업비 편성",
            "instruction": "요약서는 3페이지 내외로 작성",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "사업목표",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "추진방안 및 전략",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3",
            "title": "최종목표 평가기준",
            "instruction": "****",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "공동활용 데이터 개요",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "과제 관련 데이터 구축ㆍ활용 내용",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3",
            "title": "데이터 권원 및 저작권 등 확보 전략",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "과제 추진 체계",
            "instruction": "구분: 대기업, 중견기업, 중소기업, 공공기관, 공기업, 출연연, 국가기관, 지자체, 대학교, 병원, 비영리법인(협회 등)",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "사업 추진 일정",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "사업비 총괄표",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "수행기관별 예산 분담 계획",
            "instruction": "기관유형 : 중소기업, 중견기업, 대기업, 공기업, 국가기관, 지자체, 공공기관, 출연연, 대학교, 병원, 비영리법인(협회 등)",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3",
            "title": "비목별 총괄표",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2.3",
            "title": "특근매식비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3.2",
            "title": "국외여비",
            "instruction": "상기 비목별 총괄은 수행기관 전체의 비목별 소요 예산 합계임",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "4",
            "title": "예산 세부 계획",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "인건비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1.1",
            "title": "보수",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1.2",
            "title": "상용임금",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1.3",
            "title": "일용임금",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1.3.1",
            "title": "일용임금(직접)",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1.3.2",
            "title": "일용임금(크라우드소싱)",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "운영비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2.1",
            "title": "일반수용비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2.2",
            "title": "공공요금 및 제세",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2.3",
            "title": "특근매식비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2.4",
            "title": "임차료",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2.5",
            "title": "재료비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2.6",
            "title": "일반용역비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3",
            "title": "여비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3.1",
            "title": "국내여비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3.2",
            "title": "국외여비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "4",
            "title": "업무추진비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "4.1",
            "title": "사업추진비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "5",
            "title": "연구용역비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "5.1",
            "title": "일반연구비",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "6",
            "title": "유형자산",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "6.1",
            "title": "자산취득비",
            "instruction": "정부지원금 위탁용역비(2.6일반용역비+5.1일반연구비) : 원, 위탁용역 비율(위탁용역비 ÷ 정부지원금 합계 ) : %(28.57% 이내 편성)",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "인건비",
            "instruction": "과제 수행을 위해 일용직 형태로 모집하여 상근형태로 참여하는 인력은 크라우드 소싱 인원이 아닌 일용직 비목에 계상",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "운영비",
            "instruction": "전문가 활용 목적을 개인별로 구체적으로 기재",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "원고 자문 : A4기준 1장당 30,000원 이내",
            "instruction": "2026년 예산안 편성 및 기금운용계획안 작성 세부지침에 따라 특근매식비는 1끼 9천원을 초과할 수 없음",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3",
            "title": "여 비",
            "instruction": "자체 출장관련 규정을 적용하되 별도로 정한 기준이 없는 경우 공무원 여비규정 기준 단가를 준용하며, 사업추진비, 특근매식비와 중복지급 불가",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "4",
            "title": "업무추진비",
            "instruction": "회의비 사용 시 외부기관 소속 참여자가 포함되어야 하며, 인당 3만원 (부가가치세 포함)을 초과할 수 없음",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "5",
            "title": "연구용역비 : 각종 조사·연구 용역비",
            "instruction": "위탁 및 용역 사업명 각 건별로 [서식 2] 위탁용역 계획서를 작성해야 함",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "6",
            "title": "유형자산",
            "instruction": "단일품목 또는 동일품목 구매 총액이 부가가치세 포함 3,000만원 이상인 건에 대해서는 [서식 3] 기자재 구입 및 활용계획서’를 각 건별로 작성",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "업무의 개요",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "업무상 작업자 가이드의 준수",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "0000년 00월 00일 (계약체결일)부터 0000년 00월 00일 (과제종료일)까지",
            "instruction": "“상”과 “생”의 합의 하에 본 계약기간은 연장될 수 있으나, “상”의 계약기간 연장에 관한 별도의 의사표시가 없는 한 본 계약은 본 계약기간이 만료됨과 동시에 종료된다.",
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "3",
            "title": "“생”은 원만한 업무수행을 위해 “상”과의 긴밀한 연락체계를 수립하여야 한다.",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "“상”은 다음 각 호의 경우 본 계약을 해지할 수 있다.",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "2",
            "title": "“상”은 “생”에게 계약해지를 통보할 경우, 해지 예정일 기준 7일 전에 통보하여야 한다.",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "4",
            "title": "본 조의 손해배상 청구권은 제11조의 계약해지에 영향을 미치지 아니한다.",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          },
          {
            "number": "1",
            "title": "본 계약으로 발생하는 분쟁은 OOOOOOOO 법원을 관할법원으로 한다.",
            "instruction": null,
            "inputKind": "narrative",
            "children": []
          }
        ]
      },
      {
        "id": "ai-form",
        "title": "신청서 · 서식",
        "kind": "fields",
        "sha256": "",
        "ext": null,
        "attachment": {
          "filename": "붙임2_사업수행계획서 등 관련 서식.hwp",
          "url": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_000000000769075&fileSn=2"
        },
        "items": [
          {
            "number": null,
            "title": "사업명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "과 제 명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "주관기관",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "주 소",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "기관 성격",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "책임자",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "성 명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "E-mail",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "실무 책임자",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "총사업비 (단위: 백만 원)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "총 사 업 기 간",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "참여기관",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "버전",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "2. 수행기관명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "3. 수행기간",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "4. 총 사 업 비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "5. 과제목표",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "작성 요령",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "구분",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "데이터 종류 및 규모",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "성과 지표",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "OOO 데이터셋 구축량",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "기 타",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "성과지표명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "정의",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "가 중 치",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "측정주기",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "II",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "데이터 정보",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "데이터명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "데이터 소개",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "세분류",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "구조",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "확장자",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "데이터 출처",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "데이터 수량",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "Data1",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "Data2",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "키워드",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "자막",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "품질지표",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "데이터 완전성",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "객체 및 범위 유효성",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "데이터 다양성",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "데이터 보안성",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "원천데이터 정보",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "수집방법",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "수집주기",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "수집출처",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "최종데이터 정보",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "상품유형",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "제공방법",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "III",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "기관명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "OOO (주관기관)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "OOO (참여기관)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "구 분",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "참여기관 (1)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "일 정",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "4월",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "5월",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "6월",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "7월",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "8월",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "일련번호",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "IV",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "정부지원금",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "수행기관 민간부담금",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "현물",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "합 계",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "No",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "최소 민간부담금 산출 기준",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "정부지원금 기준 민간부담금",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "비율*",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "비 목",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "현금",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "1. 인건비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "1.1 보수",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "1.2 상용임금",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "1.3 일용임금",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "1.3.1 일용임금(직접)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "1.3.2 일용임금(크라우드소싱)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "2. 운영비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "2.1 일반수용비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "2.2 공공요금 및 제세",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "2.4 임차료",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "2.5 재료비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "2.6 일반용역비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "3. 여비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "3.1 국내여비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "4. 업무추진비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "4.1 사업추진비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "5. 연구용역비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "5.1 일반연구비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "6. 유형자산",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "6.1 자산취득비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "성명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "시작일",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "소 계",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "권OO",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "이OO",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "임OO",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "김OO",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "박OO",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "정OO",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "장OO",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "주OO",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "한OO",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "채용예정1",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "겸직 참여자 소속기관 정보",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "기업명 2",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "총계",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "신OO",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "구축 데이터명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "OOOO 영상 데이터",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "세세목 구분",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "사무용품 및 소모성 물품구입비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "인쇄·유인비 및 안내·홍보물 등 제작비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "간행물 등 구입비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "비품 수선비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "업무위탁대가 및 사례금",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "공고료 및 광고료",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "각종 수수료 및 사용료",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "교육훈련비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "국내",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "내용",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "클라우드컴퓨팅서비스 이용료",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "전기요금",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "관리비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "특근매식비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "노트북 임차료",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "모니터 임차료",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "사무실 임차료",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "스캐너 임차료",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "측정센서보드 제작비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "저작권 획득비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "베이스판 제작",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "기타 소모성 재료비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "위탁 및 용역 사업명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "데이터 가공작업 전문운영 대행비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "영상 데이터 규격화 작업",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "구분 (사용용도)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "근무지외 출장",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "근무지내 출장",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "출장지",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "일본",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "회의비",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "시설 및 장비명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "사무용 노트북",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "SSD",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "복합기",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "영상획득용 테스트 지그",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "실증스마트팜",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "작성일 : YY.MM.DD.",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "변호사",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "등록번호",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "소속기관명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "수행 기관",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "소재지",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "작성 시 유의 사항",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "자문명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "기본 정보",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "검토 의견",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "관련 참고자료",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "동의 사항",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "발주기관",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "용역구분",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "용역 사업명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "계약 방법",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "소요금액",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "수행기간",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "도입기관",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "장 비 명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "(영문)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "모 델 명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "제작국가",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "구입방법",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "구입일자(예정)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "공동활용 여부",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "장비 개요",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "원리 및 특징",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "주요사양",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "사용용도 (활용방안)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "활용 계획",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "운영비 확보 방안",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "전담인력 확보 방안",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "유지보수 방안",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "기타",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "주관 기관",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "참여 기관",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "주관기관(총괄책임자)",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "No.",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "소속기관",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "확인 사항",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "계약건명",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "계약기간",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "“생”",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "“상”",
            "instruction": null,
            "inputKind": "field",
            "children": []
          },
          {
            "number": null,
            "title": "대 표 자",
            "instruction": null,
            "inputKind": "field",
            "children": []
          }
        ]
      }
    ],
    "submitHint": null,
    "undecided": 0
  },
  "empty": {
    "notice": {
      "id": "PBLN_000000000118524",
      "source": "bizinfo",
      "title": "2026년 농식품 현지화지원사업(현지 전문기관 자문) 신청 공고",
      "url": "https://www.bizinfo.go.kr/sii/siia/selectSIIA200Detail.do?pblancId=PBLN_000000000118524"
    },
    "documents": [],
    "submitHint": [
      "신청방법 : 수출종합지원시스템(global.at.or.kr) > 사업신청 > 농식품현지화지원사업",
      "제출서류는 [신청] 버튼을 클릭하면 국가별 안내사항 확인 가능"
    ]
  }
};
