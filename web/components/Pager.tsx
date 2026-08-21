import Link from "next/link";
import type { View } from "@/lib/view";
import styles from "./Pager.module.css";

/** 앞뒤로만 간다. 페이지 번호를 96개 늘어놓지 않는다.
 *
 * 끝에 닿으면 링크를 지우지 않고 **비활성으로 남긴다** — 자리가 사라지면 레이아웃이 흔들린다.
 * DESIGN.md §7-3 의 비활성 상태가 여기 쓰인다. */
export function Pager({
  page,
  pages,
  params,
}: {
  page: number;
  pages: number;
  params: { q: string; source: string; view: View };
}) {
  if (pages <= 1) return null;

  // **`view` 를 같이 싣는다.** 안 싣으면 2쪽으로 넘어가는 순간 격자가 리스트로 돌아간다.
  // 기본값(list)은 주소에 안 적는다 — 적으면 같은 화면에 주소가 둘이 된다.
  const href = (p: number) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.source) qs.set("source", params.source);
    if (params.view !== "list") qs.set("view", params.view);
    if (p > 1) qs.set("page", String(p));
    const s = qs.toString();
    return s ? `/?${s}` : "/";
  };

  return (
    <nav className={styles.pager} aria-label="쪽 넘기기">
      {page > 1 ? (
        <Link href={href(page - 1)} className={styles.step} rel="prev">
          이전
        </Link>
      ) : (
        <span className={styles.step} aria-disabled="true">
          이전
        </span>
      )}

      <span className={styles.at} data-numeric>
        {page} / {pages}
      </span>

      {page < pages ? (
        <Link href={href(page + 1)} className={styles.step} rel="next">
          다음
        </Link>
      ) : (
        <span className={styles.step} aria-disabled="true">
          다음
        </span>
      )}
    </nav>
  );
}
