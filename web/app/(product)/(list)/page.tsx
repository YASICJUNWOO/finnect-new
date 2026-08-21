import Link from "next/link";
import { Filters } from "@/components/Filters";
import { NoticeRow } from "@/components/NoticeRow";
import { Pager } from "@/components/Pager";
import { listNotices } from "@/lib/api";
import { viewOf } from "@/lib/view";
import styles from "./page.module.css";

type Search = { q?: string; source?: string; page?: string; view?: string };

/** S4 공고 목록.
 *
 * 섹션 둘이다 — 추천 공고가 맨 위, 전체 공고가 아래. 추천은 적합도(F3-2)가 있어야
 * 하는데 없어서 **카드 셋 자리를 비워 둔다.**
 *
 * **적합도 숫자도 막대도 열도 없다**(§7 · §12.2). 순서가 정보를 담는다.
 *
 * 2026-08-21 시안 `R 적응` 을 옮기면서 **숫자 밴드가 붙고 목록 형태 토글이 생겼다**
 * (ADR-0042 · ADR-0046). 밴드는 넓은 화면에서만 뜬다 — 좁은 화면에서 숫자가 세로로
 * 쌓이면 첫 화면을 다 먹는다.
 *
 * 옮기지 않은 것 셋. 전부 값이 없어서다.
 * - `.won` 금액과 `.kind` 지원 형태 — 두 출처가 안 준다
 * - `.star` 저장 — 로그인도 S6 신청 현황도 없다. 눌러도 갈 곳이 없다
 * - `.sort` 정렬 고르기 — 서버 정렬이 마감순 하나다(`api/service.py` `ORDER`).
 *   누를 수 없는 버튼을 두는 대신 **무슨 순서인지 부제로 적는다** */
export default async function NoticeListPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const sp = await searchParams;
  const q = sp.q?.trim() ?? "";
  const source = sp.source ?? "";
  const page = Math.max(1, Number(sp.page) || 1);
  const view = viewOf(sp.view);

  const list = await listNotices({ q, source, page });

  return (
    <>
      {/* 화면 이름. 눈으로는 내비의 '지원사업'이 말하고 있어서 글자를 두지 않는다.
       * **h1 을 없애는 대신 숨긴다** — 섹션 둘이 h2 라 h1 이 없으면 계층이 h2 로 시작한다 */}
      <h1 className="srOnly">지원사업</h1>

      {/* 숫자 밴드. **넓은 화면에서만 뜬다.**
        *
        * 시안은 넷을 놓는다 — 열린 공고 · 이번 주 마감 · 글자를 읽은 첨부 · 나에게 맞는
        * 공고. **둘만 옮겼다.**
        *
        * - `이번 주 마감` — 목록 API 가 이 쪽 것만 주고 코퍼스 전체 수를 안 준다.
        *   지금 쪽에서 세면 "31,327건 중 2건" 이 아니라 "이 20건 중 2건" 이 되는데,
        *   그 둘은 **다른 사실이고 화면은 앞의 것처럼 읽힌다.**
        * - `글자를 읽은 첨부 2,827` — 실측값을 박아 넣는 것이라 넣는 순간부터 낡는다.
        *   §7 「예시 데이터로 빈 화면을 채우지 않는다」에 걸린다.
        *
        * 둘을 되살리려면 API 가 그 수를 줘야 한다. **화면에서 지어내지 않는다.** */}
      <div className={styles.band}>
        <div className={styles.stat}>
          <b data-numeric>{list.total.toLocaleString("ko-KR")}</b>
          <span>{q || source ? "찾은 공고" : "열린 공고"}</span>
        </div>
        {/* 0 은 사실이다 — 위키가 없어서 추천이 0 건이고, 바로 아래 섹션이 같은 말을 한다 */}
        <div className={styles.stat}>
          <b data-numeric>0</b>
          <span>나에게 맞는 공고</span>
        </div>
      </div>

      {/* 1. 추천. 적합성 순 */}
      <section className={styles.sec} aria-labelledby="rec-title">
        <div className={styles.sh}>
          <div className={styles.stack}>
            <h2 id="rec-title" className={styles.title}>
              추천 공고
            </h2>
            <p className={styles.sub}>공고 취지와 사업 내용이 맞는 순서로 골라 드려요</p>
          </div>
        </div>

        {/* 카드 셋이 올 자리. **예시 공고로 채우지 않는다** */}
        <p className={styles.hole}>
          아직 사업 위키가 없어서 못 고르고 있어요. 파일을 올리면 여기에 세 건이 뜹니다.
        </p>
        <Link href="/wiki/files" className={styles.cta}>
          파일 올리기
        </Link>
      </section>

      {/* 2. 전체 공고 */}
      <section className={styles.sec} aria-labelledby="all-title">
        <div className={styles.sh}>
          <div className={styles.stack}>
            <h2 id="all-title" className={styles.title}>
              전체 공고
              <span className={styles.n} data-numeric>
                {list.total.toLocaleString("ko-KR")}건
              </span>
            </h2>
            <p className={styles.sub}>마감이 가까운 순서예요. 이미 마감된 공고는 빼 뒀어요.</p>
          </div>
        </div>

        <div className={styles.filters}>
          <Filters q={q} source={source} view={view} />
        </div>

        {list.items.length > 0 ? (
          /* 리스트일 때는 카드 하나 안에서 줄을 가르고, 격자일 때는 칸이 제 테두리를
             갖는다(ADR-0046). **줄마다 카드를 세우지 않는다** — 그러면 20건이 20장이
             되어 목록이 무거워진다 */
          <ul className={view === "grid" ? styles.grid : styles.list}>
            {list.items.map((n) => (
              <NoticeRow key={`${n.source}/${n.external_id}`} notice={n} view={view} />
            ))}
          </ul>
        ) : (
          /* 빈 화면. **다음 동작을 권한다** — DESIGN.md §14 */
          <div className={styles.empty}>
            <p className={styles.emptyLead}>
              {q ? `'${q}'로 찾은 공고가 없어요.` : "조건에 맞는 공고가 없어요."}
            </p>
            <p className={styles.emptyWhy}>
              검색어를 줄이거나 출처를 전체로 두면 더 나올 수 있어요.
            </p>
            {(q || source) && (
              <Link href="/" className={styles.emptyAction}>
                조건 지우고 다시 보기
              </Link>
            )}
          </div>
        )}

        <Pager page={list.page} pages={list.pages} params={{ q, source, view }} />
      </section>
    </>
  );
}
