import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import styles from "./layout.module.css";

export const metadata: Metadata = {
  title: "라스트마일 — 지원사업",
  description: "맞는 공고를 골라 주고, 들어가면 문서가 이미 써져 있어요.",
};

/** 껍데기. 상단 내비는 **3축이다** — 시연(`demo_from_hwi.html` 653·881·1198행)이 그렇다.
 *
 * **왼쪽 사이드바를 두지 않는다** — DESIGN.md §5.4 가 금지한 다섯 조합의 첫째다.
 * 3축을 위로 올린 것이 그 답이다.
 *
 * 셋 중 '지원사업'만 있다. '내 사업'(S7)과 '신청 현황'(S6)은 화면이 없어서
 * **누를 수 없는 채로 자리만 지킨다.** 없는 곳으로 보내지 않고, 없다는 것을 보여 준다.
 *
 * 활성 표시가 '지원사업'에 박혀 있다. 지금 라우트가 목록과 상세 둘뿐이고
 * 시연도 그 둘에서 같은 항목을 켠다. **나머지 축이 생기면 `usePathname` 이 필요해진다.** */

/** 운영 도구(`src/finnect/admin/`)로 나가는 문. **개발에서만 낸다.**
 *
 * admin 은 Vercel 에 올라가지 않는다(ADR-0026) — 배포본에 두면 죽은 링크가 된다.
 * 3축 내비에 넣지 않는 이유도 같다. 제품 화면이 아니라 SPEC §6 밖의 도구다. */
const ADMIN =
  process.env.NODE_ENV === "development" ? process.env.FINNECT_ADMIN : undefined;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className={styles.bar}>
          <div className={styles.inner}>
            <Link href="/" className={styles.brand}>
              <i className={styles.mark} aria-hidden />
              라스트마일
            </Link>

            <nav className={styles.menu} aria-label="주요 메뉴">
              <Link href="/" className={styles.on} aria-current="page">
                지원사업
              </Link>
              <span className={styles.soon} aria-disabled="true">
                내 사업
                <span className="srOnly"> — 아직 없어요</span>
              </span>
              <span className={styles.soon} aria-disabled="true">
                신청 현황
                <span className="srOnly"> — 아직 없어요</span>
              </span>
            </nav>

            {ADMIN ? (
              <a
                href={ADMIN}
                className={styles.admin}
                target="_blank"
                rel="noreferrer"
              >
                운영 도구
              </a>
            ) : null}
          </div>
        </header>

        <main className={styles.main}>{children}</main>
      </body>
    </html>
  );
}
