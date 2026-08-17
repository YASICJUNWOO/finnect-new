import Link from "next/link";
import type { Notice } from "@/lib/api";
import { Deadline } from "./Deadline";
import styles from "./NoticeRow.module.css";

const SOURCE_NAME: Record<string, string> = {
  bizinfo: "기업마당",
  kstartup: "K-Startup",
};

/** 목록 한 줄. 시연의 '전체 공고' 행 형태다.
 *
 * **정보 덩어리를 넷 이하로 둔다**(DESIGN.md §8.1-7). 마감 · 제목 · 기관과 분야 ·
 * 낼 서류다. 적합도도 "맞는 이유"도 여기 없다 — 목록이 읽는 문서가 되면 안 된다(§6-2). */
export function NoticeRow({ notice }: { notice: Notice }) {
  const meta = [notice.organization, notice.category].filter(Boolean).join(" · ");

  return (
    <li className={styles.row}>
      <div className={styles.when}>
        <Deadline notice={notice} />
      </div>

      <div className={styles.body}>
        <h3 className={styles.title}>
          {/* 행 전체가 아니라 제목이 링크다. 어디를 누르는지가 분명해야 한다 */}
          <Link
            href={`/notices/${notice.source}/${encodeURIComponent(notice.external_id)}`}
            className={styles.link}
          >
            {notice.title ?? "제목이 없어요"}
          </Link>
        </h3>
        <p className={styles.meta}>
          {meta || "기관을 안 알려줬어요"}
          <span className={styles.dot} aria-hidden="true">
            ·
          </span>
          <span className={styles.source}>{SOURCE_NAME[notice.source] ?? notice.source}</span>
        </p>
      </div>

      <div className={styles.docs} data-numeric>
        {notice.attachment_count > 0 ? (
          <>
            낼 서류 <b className={styles.count}>{notice.attachment_count}</b>
          </>
        ) : (
          <span className={styles.none}>서류 없음</span>
        )}
      </div>
    </li>
  );
}
