import Link from "next/link";
import { Filters } from "@/components/Filters";
import { NoticeRow } from "@/components/NoticeRow";
import { Pager } from "@/components/Pager";
import { listNotices } from "@/lib/api";
import styles from "./page.module.css";

type Search = { q?: string; source?: string; page?: string };

/** S4 공고 목록. 시연 `demo_from_hwi.html#list` 를 따른다.
 *
 * 섹션 둘이다 — 추천 공고가 맨 위, 전체 공고가 아래(DESIGN.md §6.1).
 * 추천은 적합도(F3-2)가 있어야 하는데 없어서 **카드 셋 자리를 비워 둔다.**
 *
 * **적합도 숫자도 막대도 열도 없다**(§6). 순서가 정보를 담는다.
 *
 * 시연에서 옮기지 않은 것 셋. 전부 값이 없어서다.
 * - `.won` 금액과 `.kind` 지원 형태 — 두 출처가 안 준다. 시연 행의 제일 굵은 사실이 이것이다
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

  const list = await listNotices({ q, source, page });

  return (
    <>
      {/* 화면 이름. 눈으로는 상단 내비의 '지원사업'이 말하고 있어서 글자를 두지 않는다.
       * **h1 을 없애는 대신 숨긴다** — 섹션 둘이 h2 라 h1 이 없으면 계층이 h2 로 시작한다 */}
      <h1 className="srOnly">지원사업</h1>

      {/* 1. 추천. 적합성 순 — 시연 894~932행 */}
      <section className={styles.sec} aria-labelledby="rec-title">
        <div className={styles.sh}>
          <div className={styles.stack}>
            <h2 id="rec-title" className={styles.title}>
              추천 공고
            </h2>
            <p className={styles.sub}>공고 취지와 사업 내용이 맞는 순서로 골라 드려요</p>
          </div>
        </div>

        {/* 카드 셋이 올 자리. **예시 공고로 채우지 않는다**(plan/09) */}
        <p className={styles.hole}>
          아직 사업 위키가 없어서 못 고르고 있어요. 파일을 올리면 여기에 세 건이 뜹니다.
        </p>
      </section>

      {/* 2. 전체 공고 — 시연 935~1034행 */}
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
          <Filters q={q} source={source} />
        </div>

        {list.items.length > 0 ? (
          /* 시연의 `.list` — 카드 하나 안에 줄을 나눈다. 줄마다 카드를 세우지 않는다 */
          <ul className={styles.list}>
            {list.items.map((n) => (
              <NoticeRow key={`${n.source}/${n.external_id}`} notice={n} />
            ))}
          </ul>
        ) : (
          /* 5. 빈 화면. **다음 동작을 권한다** — DESIGN.md §7-5 */
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

        <Pager page={list.page} pages={list.pages} params={{ q, source }} />
      </section>
    </>
  );
}
