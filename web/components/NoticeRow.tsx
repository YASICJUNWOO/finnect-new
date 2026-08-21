import Link from "next/link";
import type { Notice } from "@/lib/api";
import type { View } from "@/lib/view";
import { Deadline } from "./Deadline";
import styles from "./NoticeRow.module.css";

const SOURCE_NAME: Record<string, string> = {
  bizinfo: "기업마당",
  kstartup: "K-Startup",
};

/** 목록 한 줄. **마크업 하나를 두 구조로 그린다**(ADR-0047 · DESIGN.md §5).
 *
 * | 폭 | 구조 |
 * |---|---|
 * | ≥1024px | 4열 그리드 — 마감 128px · 제목 1fr · 기관 92px · 서류 64px. 행 39px |
 * | <1024px | 세로 스택 — 마감 한 줄 · 제목 한 줄 · 기관과 서류가 한 줄을 나눠 쓴다 |
 *
 * 자식 넷의 순서가 DOM 그대로다(마감 → 제목 → 기관 → 서류). **`order` 를 쓰지 않는다** —
 * 쓰면 넓은 화면에서 되돌려야 하고, 안 되돌리면 그리드가 소스 순서를 안 따라 열이
 * 어긋난다. 순서를 안 바꾸면 그 함정 자체가 없다.
 *
 * **정보 덩어리를 넷 이하로 둔다**(DESIGN.md §10). 마감 · 제목 · 기관 · 낼 서류다.
 * 적합도도 "맞는 이유"도 여기 없다 — 목록이 읽는 문서가 되면 안 된다.
 *
 * **분야(`category`)를 뺐다.** 넓은 화면의 기관 칸이 92px 이라 "성남산업진흥원 · 창업"
 * 이 안 들어가고, 넣으면 덩어리가 다섯이 된다. 분야는 상세에 그대로 있다. */
export function NoticeRow({ notice, view }: { notice: Notice; view: View }) {
  return (
    <li className={view === "grid" ? `${styles.item} ${styles.card}` : styles.item}>
      <Deadline notice={notice} className={styles.dl} />

      {/* 넓은 화면에서 이 래퍼가 `display: contents` 로 사라지고 제목이 직접 칸이 된다.
        * **안 그러면 행 높이가 39px 이 아니라 57px 이다** — 래퍼가 남으면 그리드 자식이
        * blockify 되면서 baseline 정렬이 한 겹 더 생긴다. 좁은 화면에서는 이 래퍼가
        * "제목이 한 줄을 통째로 쓴다" 를 만들어서 지울 수 없다. */}
      <span className={styles.body}>
        <h3 className={styles.title}>
          {/* 행 전체가 아니라 제목이 링크다. 어디를 누르는지가 분명해야 한다 */}
          <Link
            href={`/notices/${notice.source}/${encodeURIComponent(notice.external_id)}`}
            className={styles.link}
          >
            {notice.title ?? "제목이 없어요"}
          </Link>
        </h3>
      </span>

      <span className={styles.org}>
        {notice.organization ?? "기관을 안 알려줬어요"}
        {/* **구분점을 `.src` 안에 둔다.** 밖에 두면 좁은 화면에서 출처를 숨겼을 때
          * "성남산업진흥원 ·" 처럼 점만 남는다 */}
        <span className={styles.src}>
          <span className={styles.dot} aria-hidden="true">
            {" · "}
          </span>
          {SOURCE_NAME[notice.source] ?? notice.source}
        </span>
      </span>

      <span className={styles.docs} data-numeric>
        {notice.attachment_count > 0 ? (
          <>
            낼 서류 <b className={styles.count}>{notice.attachment_count}</b>
          </>
        ) : (
          <span className={styles.none}>서류 없음</span>
        )}
      </span>
    </li>
  );
}
