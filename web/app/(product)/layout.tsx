"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Install } from "@/components/Install";
import styles from "./layout.module.css";

/** 제품 껍데기. 내비는 **3축이다**([ADR-0016](../../../docs/adr/0016-LNB-내-사업-축.md)).
 *
 * **폭에 따라 3축의 자리가 바뀐다**(ADR-0042 · ADR-0047 · DESIGN.md §5).
 *
 * | 폭 | 3축 | 상단 |
 * |---|---|---|
 * | ≥1024px | 좌측 레일 60px | 2단 — 브랜드·운영 도구 / 현재 위치 |
 * | 641~1023px | 상단 막대 | 1단 |
 * | ≤640px | 하단 탭 바 | 1단 |
 *
 * **같은 메뉴가 화면에 두 번 있으면 안 된다.** 자리가 셋이 됐으므로 둘은 반드시 꺼진다.
 * 규칙은 CSS 한 곳(`layout.module.css`)에 있고 여기서는 셋을 다 그린다.
 *
 * 2026-08-21 좌측 레일이 생겼다. **여기 있던 "§5 가 금지한 다섯 조합의 첫째다" 주석을
 * 지웠다** — 그 금지는 옛 판 §5.4 에 있었고 clean-slate 로 다시 쓰면서 빠졌는데(ADR-0041)
 * 코드만 남아서 없는 규칙을 인용하고 있었다. 지금 레일은 금지가 아니라 채택된 결정이다.
 *
 * 2026-08-21 **좁은 화면에서 3축이 아래로 내려간다**(ADR-0039 · DESIGN.md §12).
 * 설치하면 브라우저 크롬이 없어서 상단 막대가 유일한 크롬이 되고, 폰에서 그 자리는
 * 엄지가 안 닿는다. **시안은 이 자리를 모델링하지 않아 3축을 상단에 두고 가로로
 * 스크롤시켰지만, 그 이유(390px 에서 막대가 두 줄로 터진다)가 제품에는 없다** —
 * 여기서는 축이 이미 아래에 있어 상단에 브랜드와 운영 도구뿐이다.
 *
 * 2026-08-18 '내 사업'(S7)이 켜졌다. 축이 둘이 되면서 활성 표시를 `usePathname` 으로
 * 옮겼고, 그래서 이 파일이 클라이언트 컴포넌트가 됐다.
 *
 * 2026-08-17 루트 레이아웃에서 여기로 내려왔다(ADR-0027). */

/** 운영 도구(`/admin`)로 나가는 문.
 *
 * **이제 같은 앱 안이다.** 2026-08-17 까지는 로컬 `127.0.0.1:8000` 의 별개 Python 앱을
 * 가리켰고, 그래서 배포본에서 누르면 아무것도 안 열렸다. 옮긴 뒤로 상대 경로다(ADR-0027).
 *
 * 3축 내비 안에 넣지 않는다 — 제품 화면이 아니라 `SPEC.md` §6 밖의 도구다.
 *
 * **좁은 화면에서 숨기지 않는다.** 시안은 숨긴다. 그 이유도 자리가 없어서인데 제품에는
 * 자리가 있다(3축이 아래로 내려가 상단이 비었다). 숨기면 폰에서 `/admin` 으로 가는 문이
 * 사라지고, 그건 시각 결정이 아니라 기능 축소다. */
const ADMIN = "/admin/notices";

/** 3축. **레일·상단 막대·하단 탭 바가 이 배열 하나를 읽는다.**
 *
 * 축을 두 곳에 적으면 넷째 축이 생기는 날 한쪽만 고쳐지고, 그때 자리마다 다른 메뉴를
 * 보여 준다. `href` 가 `null` 인 축은 화면이 없는 축이다(S6).
 *
 * `on` 을 축마다 함수로 두는 이유는 **상세도 자기 축이기 때문이다** — `/notices/...` 는
 * '지원사업'이고 `'/' === path` 로 보면 목록에서만 켜진다. */
const AXES = [
  { href: "/", label: "지원사업", on: (p: string) => !p.startsWith("/wiki") },
  { href: "/wiki", label: "내 사업", on: (p: string) => p.startsWith("/wiki") },
  { href: null, label: "신청 현황", on: () => false },
] as const;

/** 3축을 그리는 유일한 곳. **자리가 셋이라 JSX 도 한 벌만 둔다.**
 *
 * 활성·비활성 모양은 감싸는 쪽(`.rail` · `.menu` · `.tabs`)이 자손 선택자로 정한다.
 * 여기서 자리마다 다른 클래스를 주면 배열을 한 곳에 둔 뜻이 없어진다. */
function Axes({ path }: { path: string }) {
  return AXES.map((a) =>
    a.href === null ? (
      <span key={a.label} className={styles.soon} aria-disabled="true">
        {a.label}
        <span className="srOnly"> — 아직 없어요</span>
      </span>
    ) : (
      <Link
        key={a.label}
        href={a.href}
        className={a.on(path) ? styles.on : undefined}
        aria-current={a.on(path) ? "page" : undefined}
      >
        {a.label}
      </Link>
    ),
  );
}

/** 상단 2단의 둘째 줄에 적을 현재 위치. 넓은 화면에서만 뜬다.
 *
 * **모르는 경로에서는 null 이고 화면은 둘째 칸을 아예 안 그린다.** 새 화면이 생겼을 때
 * 틀린 이름을 보여 주는 것보다 안 보여 주는 쪽이 낫다 — 여기는 경로를 아는 유일한
 * 자리가 아니라 두 번째 자리라 반드시 낡는다.
 *
 * **순서가 중요하다.** `/write` 가 상세보다 먼저 와야 한다 — 뒤에 두면 상세 규칙이
 * 먼저 걸려서 쓰기 화면이 '공고 상세'로 뜬다.
 *
 * 시안은 이 줄에 코퍼스 건수와 마지막 수집 시각을 넣는다. **안 옮겼다** — 껍데기는
 * 데이터를 안 가져오고, 숫자를 박아 넣으면 그 순간부터 낡는다(§7 "예시 데이터로 빈
 * 화면을 채우지 않는다"). 수집 시각은 운영 정보라 이미 `/admin` 에 있다. */
const WHERE: ReadonlyArray<readonly [RegExp, string]> = [
  [/^\/$/, "전체 공고"],
  [/^\/notices\/[^/]+\/[^/]+\/write$/, "쓰기"],
  [/^\/notices\/[^/]+\/[^/]+$/, "공고 상세"],
  [/^\/wiki$/, "사업 위키"],
  [/^\/wiki\/files$/, "파일 올리기"],
  [/^\/wiki\/markdown$/, "마크다운"],
  [/^\/documents\/[^/]+\/write$/, "쓰기"],
  [/^\/documents\/[^/]+$/, "서류"],
];

function whereOf(path: string): string | null {
  return WHERE.find(([re]) => re.test(path))?.[1] ?? null;
}

export default function ProductLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const axis = AXES.find((a) => a.on(path))?.label ?? null;
  const where = whereOf(path);

  return (
    <div className={styles.app}>
      {/* 좌측 레일. **넓은 화면에서만 뜬다.**
        *
        * 아이콘을 그리지 않고 글자로 둔다 — 세 축의 그림글자를 새로 정하는 것은
        * DESIGN.md §1 이 미정으로 남긴 '시그니처 요소'를 결정 없이 채우는 일이다.
        * 앱 아이콘에서 둘째 글리프를 안 만든 것과 같은 이유다(ADR-0042). */}
      <aside className={styles.rail}>
        <Link href="/" className={styles.railMark} aria-label="라스트마일 홈">
          <i className={styles.mark} aria-hidden />
        </Link>
        <nav className={styles.railNav} aria-label="주요 메뉴">
          <Axes path={path} />
        </nav>
      </aside>

      <div className={styles.col}>
        <header className={styles.bar}>
          <div className={styles.inner}>
            <Link href="/" className={styles.brand}>
              <i className={styles.mark} aria-hidden />
              라스트마일
            </Link>

            {/* 3축. 641~1023px 에서만 뜬다 — 위로는 레일이, 아래로는 탭 바가 맡는다 */}
            <nav className={styles.menu} aria-label="주요 메뉴">
              <Axes path={path} />
            </nav>

            <Link href={ADMIN} className={styles.admin}>
              운영 도구
            </Link>
          </div>

          {/* 둘째 단. 넓은 화면에서만 뜬다 — 축이 레일로 내려가 첫째 단이 비어서다 */}
          {axis && (
            <div className={styles.tier2}>
              <span className={styles.crumb}>
                {axis}
                {where && (
                  <>
                    <span className={styles.sep} aria-hidden>
                      ›
                    </span>
                    <b>{where}</b>
                  </>
                )}
              </span>
            </div>
          )}
        </header>

        <Install />

        <main className={styles.main}>{children}</main>

        {/* 같은 3축. **≤640px 에서만 뜨고 그때 위의 둘은 꺼진다** —
          * 규칙은 CSS 한 곳에 있다.
          *
          * `aria-hidden` 을 걸지 않는다. 숨는 쪽이 `display: none` 이라 스크린 리더가
          * 어차피 하나만 읽는다 — 여기에 걸면 폰에서 내비가 아예 안 읽힌다. */}
        <nav className={styles.tabs} aria-label="주요 메뉴">
          <Axes path={path} />
        </nav>
      </div>
    </div>
  );
}
