import Link from "next/link";
import { listAdminNotices } from "@/lib/admin";
import a from "../admin.module.css";
import styles from "./page.module.css";

type Search = { source?: string; q?: string; sort?: string; page?: string };

/** 운영 공고 목록. Jinja2 `list.html` 을 옮긴 것이고 **열 일곱 개가 그대로다**.
 *
 * 제품 목록(`/`)과 다른 점 셋. 옮기면서 생긴 차이가 아니라 원래 그랬다.
 * 1. **마감된 공고를 빼지 않는다.** 31,327건 전량이 모집단이다
 * 2. 한 페이지 50건(제품은 20). 코퍼스를 훑는 화면이다
 * 3. 정렬을 고를 수 있다 — 마감 임박 · 최근 수집 · 이름
 *
 * 검색 폼은 **JS 없이 도는 GET 폼이다.** 서버 컴포넌트가 `searchParams` 를 읽는다. */
export default async function AdminNoticeListPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const sp = await searchParams;
  const source = sp.source ?? "";
  const q = sp.q?.trim() ?? "";
  const sort = sp.sort ?? "deadline";
  const page = Math.max(1, Number(sp.page) || 1);

  const list = await listAdminNotices({ source, q, sort, page });

  const bySource = Object.entries(list.by_source)
    .map(([s, n]) => `${s} ${n.toLocaleString("ko-KR")}`)
    .join(" · ");

  // 페이지 이동 링크가 필터를 잃지 않아야 한다.
  const keep = (to: number) => {
    const qs = new URLSearchParams();
    if (source) qs.set("source", source);
    if (q) qs.set("q", q);
    if (sort !== "deadline") qs.set("sort", sort);
    if (to > 1) qs.set("page", String(to));
    const s = qs.toString();
    return `/admin/notices${s ? `?${s}` : ""}`;
  };

  return (
    <>
      <h1 className={a.h1}>
        공고 <span data-numeric>{list.total.toLocaleString("ko-KR")}</span>건
      </h1>
      <p className={a.lead}>
        전체 {bySource} · <code>notice</code> 뷰에서 읽는다. 마감된 공고를 빼지 않았다.
      </p>

      <form className={styles.bar} method="get" action="/admin/notices">
        <select name="source" defaultValue={source} aria-label="출처">
          <option value="">전체 출처</option>
          <option value="bizinfo">기업마당</option>
          <option value="kstartup">K-Startup</option>
        </select>
        <input
          type="search"
          name="q"
          defaultValue={q}
          placeholder="사업명 검색"
          aria-label="사업명 검색"
          className={styles.q}
        />
        <select name="sort" defaultValue={list.sort} aria-label="정렬">
          {Object.entries(list.sorts).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <button type="submit">조회</button>
        {(source || q) && (
          <Link href="/admin/notices" className={a.link}>
            초기화
          </Link>
        )}
      </form>

      <div className={a.wrap}>
        <table className={a.table}>
          <thead>
            <tr>
              <th>출처</th>
              <th>사업명</th>
              <th>기관</th>
              <th>접수 기간</th>
              <th className={a.num}>마감</th>
              <th className={a.num}>첨부</th>
              <th className={a.num}>최종 확인</th>
            </tr>
          </thead>
          <tbody>
            {list.items.length === 0 ? (
              <tr>
                <td colSpan={7} className={a.empty}>
                  해당하는 공고가 없다.
                </td>
              </tr>
            ) : (
              list.items.map((n) => (
                <tr key={`${n.source}/${n.external_id}`}>
                  <td>
                    <span className={a.tag}>{n.source}</span>
                  </td>
                  <td>
                    <Link
                      href={`/admin/notices/${n.source}/${encodeURIComponent(n.external_id)}`}
                      className={a.link}
                    >
                      {n.title || "(제목 없음)"}
                    </Link>
                  </td>
                  <td>{n.organization || ""}</td>
                  <td>{n.apply_period_raw || ""}</td>
                  <td className={a.num}>
                    {n.apply_end ?? <span className={a.null}>날짜 아님</span>}
                  </td>
                  <td className={a.num}>
                    {/* **'미확인'과 0을 갈라야 한다.** K-Startup 은 출처가 첨부를
                     * 안 알려줘서 전량이 미확인이고, 그건 "첨부가 없다"가 아니다 */}
                    {n.attachment_status === "unknown" ? (
                      <span className={a.null}>미확인</span>
                    ) : (
                      n.attachment_count
                    )}
                  </td>
                  <td className={`${a.num} ${a.muted}`}>{stamp(n.last_seen_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className={styles.pager}>
        {page > 1 ? (
          <Link href={keep(page - 1)} className={a.link}>
            ← 이전
          </Link>
        ) : (
          <span />
        )}
        <span className={a.muted} data-numeric>
          {page.toLocaleString("ko-KR")} / {list.pages.toLocaleString("ko-KR")}
        </span>
        {page < list.pages ? (
          <Link href={keep(page + 1)} className={a.link}>
            다음 →
          </Link>
        ) : (
          <span />
        )}
      </div>
    </>
  );
}

/** `timestamptz` 는 UTC 로 온다. 옛 Jinja2 `ts` 필터와 같은 모양으로 적는다.
 *
 * **`toLocaleString` 에 시간대를 안 넘긴다.** 서버 컴포넌트라 Vercel 함수의
 * 시간대(UTC)로 렌더되는데, 여기 쓰이는 값은 "우리가 언제 봤는가"이고
 * 분 단위 정확도가 필요한 자리가 아니다. */
function stamp(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
