import Link from "next/link";
import type { Recommendation } from "@/lib/api";
import { Deadline } from "./Deadline";
import styles from "./RecommendationCard.module.css";

/** 추천 한 장 (S2 위쪽 섹션 · plan/21 T-0119).
 *
 * **이유를 여기서 안 읽힌다**(2026-08-24). 「맞는 이유」와 「내 사업 정보 N개에서
 * 나왔어요」가 여기 있었고 **공고 상세의 「추천 사유」와 같은 값이었다**(둘 다
 * `notice_fit` 한 행이다). 같은 문장을 두 화면이 들고 있으면 한쪽이 먼저 낡는다 —
 * 목록에서 빼고 상세 한 곳만 남긴다.
 *
 * **`NoticeRow` 와 다른 물건이다.** 저쪽은 4열 그리드의 한 줄이고 여기는 격자 칸이라
 * 마크업이 안 겹친다. 한 컴포넌트에 `variant` 로 합치면 폭마다 다른 구조 둘을 한
 * 파일이 들게 된다.
 *
 * **숫자도 막대도 없다**(DESIGN.md §7 · §12.2). 92 와 74 의 차이를 설명할 눈금이
 * 없어서 순서가 정보를 담는다 — 그래서 순위 번호(1·2·3)도 안 붙인다. 번호를 붙이면
 * 그것이 눈금 없는 점수가 된다.
 *
 * 테두리 하나를 두르는 것은 격자 칸과 같은 예외다(ADR-0046). **채움·그림자는 안 온다.** */
export function RecommendationCard({ notice }: { notice: Recommendation }) {
  const href = `/notices/${notice.source}/${encodeURIComponent(notice.external_id)}`;

  return (
    <li className={styles.card}>
      <Deadline notice={notice} className={styles.dl} />

      <h3 className={styles.title}>
        {/* 카드 전체가 아니라 제목이 링크다. `NoticeRow` 와 같은 규칙이다.
          * 이유는 이 링크 너머 상세의 「추천 사유」에 있다 */}
        <Link href={href} className={styles.link}>
          {notice.title ?? "제목이 없어요"}
        </Link>
      </h3>
    </li>
  );
}
