import Link from "next/link";
import styles from "./layout.module.css";

/** 제품 껍데기. 상단 내비는 **3축이다** — 시연(`demo_from_hwi.html` 653·881·1198행)이 그렇다.
 *
 * **왼쪽 사이드바를 두지 않는다** — DESIGN.md §5.4 가 금지한 다섯 조합의 첫째다.
 * 3축을 위로 올린 것이 그 답이다.
 *
 * 셋 중 '지원사업'만 있다. '내 사업'(S7)과 '신청 현황'(S6)은 화면이 없어서
 * **누를 수 없는 채로 자리만 지킨다.** 없는 곳으로 보내지 않고, 없다는 것을 보여 준다.
 *
 * 활성 표시가 '지원사업'에 박혀 있다. 지금 라우트가 목록과 상세 둘뿐이고
 * 시연도 그 둘에서 같은 항목을 켠다. **나머지 축이 생기면 `usePathname` 이 필요해진다.**
 *
 * 2026-08-17 루트 레이아웃에서 여기로 내려왔다(ADR-0027). 운영 화면이 이 헤더를
 * 물려받지 않게 하려는 것이고 마크업은 그대로다. */

/** 운영 도구(`/admin`)로 나가는 문.
 *
 * **이제 같은 앱 안이다.** 2026-08-17 까지는 로컬 `127.0.0.1:8000` 의 별개 Python 앱을
 * 가리켰고, 그래서 배포본에서 누르면 아무것도 안 열렸다. 옮긴 뒤로 상대 경로다(ADR-0027).
 *
 * 3축 내비 안에 넣지 않는다 — 제품 화면이 아니라 `SPEC.md` §6 밖의 도구다. */
const ADMIN = "/admin/notices";

export default function ProductLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
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

          <Link href={ADMIN} className={styles.admin}>
            운영 도구
          </Link>
        </div>
      </header>

      <main className={styles.main}>{children}</main>
    </>
  );
}
