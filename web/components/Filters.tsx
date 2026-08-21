import Link from "next/link";
import type { View } from "@/lib/view";
import styles from "./Filters.module.css";

/** 필터 줄. 검색 · 출처 칩 셋 · 리스트/격자 토글이 한 줄에 선다.
 *
 * **클라이언트 자바스크립트가 없다.** 검색은 GET 폼이고 칩과 토글은 링크다.
 * 제출하거나 누르면 주소가 바뀌고 서버가 다시 그린다 — 주소에 상태가 그대로 있어서
 * 뒤로 가기와 새로 고침이 자연히 동작한다.
 *
 * **칩이 폼 안의 제출 버튼이 아니라 밖의 링크인 이유가 있다.** 폼 안에 `<button
 * name="source">` 셋을 두면 검색창에서 엔터를 쳤을 때 **첫 칩의 값이 같이 제출된다** —
 * 브라우저가 첫 제출 버튼을 기본 제출로 삼기 때문이다. 그러면 검색할 때마다 출처가
 * 조용히 '전체' 로 돌아간다. */

const SOURCES = [
  { value: "", label: "전체" },
  { value: "bizinfo", label: "기업마당" },
  { value: "kstartup", label: "K-Startup" },
] as const;

/** 리스트/격자 토글 아이콘. 선으로 그리고 색은 글자 색을 따라간다(§8) */
const ICON = {
  list: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  ),
  grid: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
      <rect x="4" y="4" width="7" height="7" rx="1.5" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" />
    </svg>
  ),
};

type State = { q: string; source: string; view: View };

/** 지금 상태에서 한 축만 바꾼 주소.
 *
 * **`page` 를 안 싣는다.** 출처나 형태를 바꾸면 결과 수가 달라져서 3쪽이 없을 수 있다 —
 * 조건을 바꿀 때 1쪽으로 돌아가는 것이 맞다.
 *
 * 기본값(`view=list` · `source=`)은 주소에 안 적는다. 적으면 같은 화면에 주소가 둘이 된다. */
function hrefWith(now: State, next: Partial<State>): string {
  const s = { ...now, ...next };
  const qs = new URLSearchParams();
  if (s.q) qs.set("q", s.q);
  if (s.source) qs.set("source", s.source);
  if (s.view !== "list") qs.set("view", s.view);
  const query = qs.toString();
  return query ? `/?${query}` : "/";
}

export function Filters({ q, source, view }: State) {
  const now: State = { q, source, view };

  return (
    <div className={styles.bar}>
      <form className={styles.form} action="/" method="get" role="search">
        <label className="srOnly" htmlFor="q">
          공고 이름으로 찾기
        </label>
        <input
          id="q"
          name="q"
          type="search"
          defaultValue={q}
          placeholder="공고 이름으로 찾아보세요"
          className={styles.input}
        />
        {/* **안 넣으면 검색할 때마다 출처와 형태가 초기화된다.** 폼은 자기 안의 것만
          * 제출하는데 저 둘은 폼 밖의 링크가 정한다.
          *
          * 기본값일 때는 아예 안 그린다. 그리면 폼이 `?source=&view=list` 를 만들어서
          * **같은 화면인데 링크가 만든 주소와 폼이 만든 주소가 달라진다.** */}
        {source && <input type="hidden" name="source" value={source} readOnly />}
        {view !== "list" && <input type="hidden" name="view" value={view} readOnly />}
        <button type="submit" className={styles.submit}>
          찾기
        </button>
      </form>

      <nav className={styles.chips} aria-label="어디서 온 공고인지">
        {SOURCES.map((s) => (
          <Link
            key={s.value || "all"}
            href={hrefWith(now, { source: s.value })}
            className={styles.chip}
            aria-current={s.value === source ? "true" : undefined}
          >
            {s.label}
          </Link>
        ))}
      </nav>

      {/* 목록 형태. **사용자가 매번 고르는 것이라 조작 요소가 화면에 있어야 한다**
        * (ADR-0046). 기본값은 리스트다 */}
      <nav className={styles.toggle} aria-label="목록 형태">
        <Link
          href={hrefWith(now, { view: "list" })}
          className={styles.vt}
          aria-current={view === "list" ? "true" : undefined}
          aria-label="리스트로 보기"
        >
          {ICON.list}
        </Link>
        <Link
          href={hrefWith(now, { view: "grid" })}
          className={styles.vt}
          aria-current={view === "grid" ? "true" : undefined}
          aria-label="격자로 보기"
        >
          {ICON.grid}
        </Link>
      </nav>
    </div>
  );
}
