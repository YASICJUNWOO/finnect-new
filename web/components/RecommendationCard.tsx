import Link from "next/link";
import type { Recommendation } from "@/lib/api";
import { Deadline } from "./Deadline";
import styles from "./RecommendationCard.module.css";

/** 추천 한 장 (S2 위쪽 섹션 · plan/21 T-0119).
 *
 * **`NoticeRow` 와 다른 물건이다.** 저쪽은 "적합도도 맞는 이유도 여기 없다 — 목록이
 * 읽는 문서가 되면 안 된다" 를 지키는 줄이고, 여기는 **이유를 읽히려고 있는 자리**다.
 * 한 컴포넌트에 `variant` 로 합치면 그 규칙이 옵션이 된다.
 *
 * **숫자도 막대도 없다**(DESIGN.md §7 · §12.2). 92 와 74 의 차이를 설명할 눈금이
 * 없어서 순서가 정보를 담는다 — 그래서 순위 번호(1·2·3)도 안 붙인다. 번호를 붙이면
 * 그것이 눈금 없는 점수가 된다.
 *
 * **덩어리를 넷 이하로 둔다**(DESIGN.md §10). 마감 · 제목 · 이유 · 근거 수다.
 * 기관을 뺀 이유가 그것이다 — 다섯째가 된다.
 *
 * 테두리 하나를 두르는 것은 격자 칸과 같은 예외다(ADR-0046). **채움·그림자는 안 온다.** */
export function RecommendationCard({ notice }: { notice: Recommendation }) {
  const href = `/notices/${notice.source}/${encodeURIComponent(notice.external_id)}`;

  return (
    <li className={styles.card}>
      <Deadline notice={notice} className={styles.dl} />

      <h3 className={styles.title}>
        {/* 카드 전체가 아니라 제목이 링크다. `NoticeRow` 와 같은 규칙이다 */}
        <Link href={href} className={styles.link}>
          {notice.title ?? "제목이 없어요"}
        </Link>
      </h3>

      {/* 이 카드가 있는 이유. **우리가 고쳐 쓰지 않는다** — `match/rank.py` 가
        * 템플릿으로 만들고 표 부스러기는 거기서 이미 걸러졌다(`rank.quotable()`).
        *
        * **한 문장이다.** 라벨을 붙여 「공고 / 내 사업 / 맞는 이유」 세 줄로 나눠
        * 봤는데, 훑는 카드에 정보 덩어리가 여섯이 되어 §10(넷 이하)을 넘었다.
        * 셋을 한 문장에 담는 것은 문장이 할 일이지 레이아웃이 할 일이 아니다. */}
      <p className={styles.reason}>{notice.reason}</p>

      {/* **근거 수를 적는다**(DESIGN.md §12.3 모든 값에 출처를 매단다).
        * 0 이면 이 카드가 목록에 없다 — 이유 없는 등급은 안 올라온다 */}
      {notice.evidence_count > 0 && (
        <p className={styles.evidence} data-numeric>
          내 사업 정보 <b>{notice.evidence_count}</b>개에서 나왔어요
        </p>
      )}
    </li>
  );
}
