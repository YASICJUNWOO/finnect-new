import type { Metadata } from "next";
import Link from "next/link";
import { AdminNav } from "./AdminNav";
import styles from "./layout.module.css";

export const metadata: Metadata = {
  title: "finnect 관리",
  // 운영 도구가 검색에 잡힐 이유가 없다.
  robots: { index: false, follow: false },
};

/** 운영 껍데기.
 *
 * **이 화면들의 목적은 운영이 아니라 L1 스키마 설계를 위한 코퍼스 관찰이다** —
 * 옮겨 온 `admin/app.py` 독스트링이 그렇게 적었고 목적은 안 바뀌었다.
 *
 * 2026-08-17 Jinja2 에서 옮겨 왔다(ADR-0027). T-0023 이 정한 선을 지킨다.
 *
 * | 한 것 | 안 한 것 |
 * |---|---|
 * | 색·타입·간격·반경 토큰 | 표를 카드로 바꾸기 |
 * | 포커스 표시 (§3-9 · §7-1) | 내비게이션 구조 변경 |
 * | `tabular-nums` | 컬럼 늘리고 줄이기 |
 *
 * **카피를 해요체로 안 바꿨다.** `DESIGN.md` §8.0 이 해요체를 요구한 대상은
 * 창업 3년 이내 사업자다. 이 화면을 보는 사람은 우리다(plan/08 T-0023).
 *
 * **`DESIGN.md` §5.4 의 금지 조합은 여기 적용되지 않는다.** 금지의 근거가
 * "대체하려는 화면(기업마당)과 닮으면 안 된다"인데 admin 은 대체 대상이 아니라
 * 우리 관찰 도구다. §5.4 본문이 그 이유를 적었다.
 *
 * 폭이 제품(900px)보다 넓다. 실행 기록이 11열이라 900 에서는 못 읽는다. */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className={styles.bar}>
        <div className={styles.inner}>
          <Link href="/admin/notices" className={styles.brand}>
            finnect <span className={styles.kicker}>관리</span>
          </Link>

          <AdminNav />

          {/* 제품으로 돌아가는 문. `(product)/layout.module.css` 의 `.admin` 과 짝이다 */}
          <Link href="/" className={styles.back}>
            사용자 화면
          </Link>
        </div>
      </header>

      <main className={styles.main}>{children}</main>
    </>
  );
}
