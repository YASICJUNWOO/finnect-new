import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import styles from "./layout.module.css";

export const metadata: Metadata = {
  title: "finnect — 지원사업",
  description: "맞는 공고를 골라 주고, 들어가면 문서가 이미 써져 있어요.",
};

/** 껍데기.
 *
 * **왼쪽 내비게이션 사이드바를 두지 않는다** — DESIGN.md §5.4 가 금지한 다섯 조합의 첫째다.
 * LNB 3축(SPEC §5.1)은 '내 사업'과 '신청 현황'이 생길 때 붙인다. 지금 걸면 빈 곳으로 간다. */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className={styles.header}>
          <Link href="/" className={styles.brand}>
            finnect
          </Link>
          <p className={styles.tagline}>지원사업</p>
        </header>
        <main className={styles.main}>{children}</main>
      </body>
    </html>
  );
}
