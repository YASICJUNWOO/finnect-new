import Link from "next/link";
import { Filters } from "@/components/Filters";
import { NoticeRow } from "@/components/NoticeRow";
import { NotYet } from "@/components/NotYet";
import { Pager } from "@/components/Pager";
import { listNotices } from "@/lib/api";
import styles from "./page.module.css";

type Search = { q?: string; source?: string; page?: string };

/** S4 공고 목록.
 *
 * 섹션 둘이다 — 추천 공고가 맨 위, 전체 공고가 아래(DESIGN.md §6.1).
 * 추천은 적합도(F3-2)가 있어야 하는데 없어서 자리만 지킨다.
 *
 * **적합도 숫자도 막대도 열도 없다**(§6). 순서가 정보를 담는다. */
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
      <NotYet
        title="추천 공고"
        why="사업 위키를 만들면 공고 취지와 맞는 순서로 골라 드려요. 아직 위키가 없어서 못 고르고 있어요."
      />

      <section className={styles.all} aria-labelledby="all-title">
        <div className={styles.head}>
          <h1 id="all-title" className={styles.title}>
            전체 공고
          </h1>
          <p className={styles.count} data-numeric>
            {list.total.toLocaleString("ko-KR")}건이에요
          </p>
        </div>

        <p className={styles.sub}>
          마감이 가까운 순서예요. 이미 마감된 공고는 빼 뒀어요.
        </p>

        <div className={styles.filters}>
          <Filters q={q} source={source} />
        </div>

        {list.items.length > 0 ? (
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
