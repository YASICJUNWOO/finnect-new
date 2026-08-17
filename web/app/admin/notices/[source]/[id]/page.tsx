import Link from "next/link";
import { notFound } from "next/navigation";
import { type AdminAttachment, type Field, getAdminNotice } from "@/lib/admin";
import a from "../../../admin.module.css";
import styles from "./page.module.css";

/** 운영 공고 상세. Jinja2 `detail.html` 을 옮긴 것이다.
 *
 * **출처가 준 컬럼을 하나도 고르지 않고 전부 편다.** 이 화면의 목적이 운영이 아니라
 * L1 스키마 설계를 위한 코퍼스 관찰이라서다 — 옮겨 온 `admin/app.py` 독스트링.
 *
 * 제품 상세(`/notices/...`)와 정반대다. 저기는 사용자가 볼 것만 고르고, 여기는 안 고른다. */
export default async function AdminNoticeDetailPage({
  params,
}: {
  params: Promise<{ source: string; id: string }>;
}) {
  const { source, id } = await params;
  const d = await getAdminNotice(source, decodeURIComponent(id));
  if (!d) notFound();

  return (
    <>
      <p className={styles.crumb}>
        <Link href="/admin/notices" className={a.link}>
          ← 목록
        </Link>
      </p>

      <h1 className={a.h1}>
        {d.source} / {d.external_id}
      </h1>
      <p className={a.lead}>
        <code>{d.table}</code> 테이블에서 직접 읽는다. 뷰를 거치지 않는다.
      </p>

      <h2 className={a.h2}>API 컬럼 {d.api_fields.length}개 — 출처가 준 그대로</h2>
      <p className={a.note}>
        설명은 {d.described}/{d.described_total}개가 공식 문서에 있다. 출처{" "}
        {d.doc_url ? (
          <a href={d.doc_url} rel="noreferrer" target="_blank" className={a.link}>
            {d.doc_label}
          </a>
        ) : (
          d.doc_label
        )}
        .
        {d.described < d.described_total && (
          <> 나머지는 <b>문서에 없다.</b> 이름으로 뜻을 추측해 채우지 않았다.</>
        )}
      </p>
      <FieldTable fields={d.api_fields} head="항목명 (공식 문서)" undocumented />

      {Object.keys(d.extra).length > 0 && (
        <>
          {/* 비어 있지 않으면 API 가 늘어났다는 뜻이다. **조용히 버리지 않는다** */}
          <h2 className={a.h2}>
            <span className={a.warn}>⚠</span> 처음 보는 필드 {Object.keys(d.extra).length}개 — API
            가 늘어났다
          </h2>
          <div className={a.wrap}>
            <table className={a.table}>
              <tbody>
                {Object.entries(d.extra).map(([k, v]) => (
                  <tr key={k}>
                    <td className={a.key}>{k}</td>
                    <td className={a.val}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2 className={a.h2}>
        첨부 {d.attachments.length}개 중 {d.decoded_count}개 해독
      </h2>
      {d.attachments.length > 0 ? (
        <div className={a.wrap}>
          <table className={a.table}>
            <thead>
              <tr>
                <th className={a.num}>#</th>
                <th>구분</th>
                <th>파일명</th>
                <th>확장자</th>
                <th>해독</th>
                <th>파서</th>
                <th className={a.num}>글자</th>
                <th>URL</th>
              </tr>
            </thead>
            <tbody>
              {d.attachments.map((f) => (
                <AttachmentRows key={f.position} f={f} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className={a.note}>
          {d.source === "kstartup" ? (
            <>
              K-Startup 목록 API 에는 첨부 필드가 없다. <code>detl_pg_url</code> 을 긁어야
              나온다 (plan/02).
            </>
          ) : (
            <>
              첨부 0건. <code>printFileNm</code> 도 <code>fileNm</code> 도 비어 있다.{" "}
              <b>2026-08-17 실측 1,538건에는 이런 공고가 없었다</b> — 기업마당은 공고문을 100%
              붙인다. 새로 생긴 형태다.
            </>
          )}
        </p>
      )}

      <h2 className={a.h2}>우리가 붙인 컬럼 {d.ours.length}개 — API 가 준 값이 아니다</h2>
      <FieldTable fields={d.ours} head="무엇인가" />

      <h2 className={a.h2}>원문 — API 가 준 응답 그대로</h2>
      {d.raw === null ? (
        <p className={a.note}>
          이 공고에 <code>raw_fetch_id</code> 가 없다. 원문 응답을 못 찾는다.
        </p>
      ) : (
        <>
          <p className={a.note}>
            <code>raw_fetch#{d.raw.id}</code> · {stamp(d.raw.fetched_at)} 수신 · 응답{" "}
            <span data-numeric>{d.raw.item_count.toLocaleString("ko-KR")}</span>건 /{" "}
            <span data-numeric>{d.raw.byte_size.toLocaleString("ko-KR")}</span>B
            {d.raw.page !== null && <> · {d.raw.page}페이지</>}
            {d.raw.ratelimit_remaining !== null && (
              <> · 잔여 쿼터 {d.raw.ratelimit_remaining.toLocaleString("ko-KR")}</>
            )}
            <br />
            {/* 인증키는 저장 전에 마스킹된다(`ingest/base.py` `mask()`). `crtfcKey=***` 로 남는다 */}
            <span className={styles.url}>{d.raw.request_url}</span>
          </p>

          <details className={a.raw}>
            <summary>
              이 공고의 원문 item
              {d.raw.siblings > 0 && (
                <> — 같은 응답에 {d.raw.siblings.toLocaleString("ko-KR")}건이 함께 왔다</>
              )}
            </summary>
            {d.raw.item ? (
              <pre className={a.pre}>{d.raw.item}</pre>
            ) : (
              <p className={a.note}>
                이 응답 안에서 <code>{d.external_id}</code> 를 못 찾았다. 공고가 뒤에 갱신되면서{" "}
                <code>raw_fetch_id</code> 가 다른 응답을 가리켰을 수 있다.
              </p>
            )}
          </details>

          <details className={a.raw}>
            <summary>봉투 — 공고 배열을 뺀 나머지</summary>
            <pre className={a.pre}>{d.raw.envelope}</pre>
          </details>

          <p className={a.note}>
            <b>두 API 모두 실패를 HTTP 200 으로 준다.</b> 봉투를 남기는 것은 그래서다
            (<code>ingest/envelope.py</code>).
          </p>
        </>
      )}
    </>
  );
}

/** 컬럼 표. API 컬럼과 우리 컬럼이 같은 모양이라 하나로 쓴다.
 *
 * `undocumented` 는 **설명이 없을 때 빈칸으로 두지 않고 '문서에 없음'을 적는 것**이다.
 * 빈칸이면 "설명이 있는데 안 보이는 것"과 구별이 안 된다. */
function FieldTable({
  fields,
  head,
  undocumented = false,
}: {
  fields: Field[];
  head: string;
  undocumented?: boolean;
}) {
  return (
    <div className={a.wrap}>
      <table className={a.table}>
        <thead>
          <tr>
            <th>필드</th>
            <th>{head}</th>
            <th>값</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((f) => (
            <tr key={f.name}>
              <td className={a.key}>{f.name}</td>
              <td className={a.desc}>
                {f.description ??
                  (undocumented ? <span className={a.undoc}>문서에 없음</span> : "")}
              </td>
              <td className={a.val}>
                {f.value === null ? <span className={a.null}>null</span> : f.value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** 첨부 한 건. 오류와 ZIP 목록이 있으면 **아래 줄로 이어 붙인다** — 옛 화면과 같다. */
function AttachmentRows({ f }: { f: AdminAttachment }) {
  const err = f.parse_error || f.fetch_error;
  return (
    <>
      <tr>
        <td className={a.num}>{f.position}</td>
        <td>
          <span className={a.tag}>{f.kind}</span>
        </td>
        <td className={a.val}>{f.filename}</td>
        <td>
          {f.ext || ""}
          {/* 파일명이 준 확장자와 내용이 다르면 둘 다 보여 준다. **파일명은 거짓말을 한다** */}
          {f.detected_ext && f.detected_ext !== f.ext && (
            <span className={a.warn}> → {f.detected_ext}</span>
          )}
        </td>
        <td>
          <StatusPill f={f} />
        </td>
        <td className={a.muted}>{f.parser || ""}</td>
        <td className={a.num}>
          {f.text_chars === null ? "" : f.text_chars.toLocaleString("ko-KR")}
        </td>
        <td>
          {f.url ? (
            <a href={f.url} rel="noreferrer" target="_blank" className={a.link}>
              열기
            </a>
          ) : (
            <span className={a.null}>URL 없음</span>
          )}
        </td>
      </tr>
      {err && (
        <tr>
          <td />
          <td colSpan={7} className={a.bad}>
            {err}
          </td>
        </tr>
      )}
      {f.contents.length > 0 && (
        <tr>
          <td />
          <td colSpan={7} className={a.muted}>
            ZIP 안 {f.contents.length}개 — 풀지 않았다: {f.contents.join(" · ")}
          </td>
        </tr>
      )}
    </>
  );
}

/** 해독 상태 알약.
 *
 * **셋을 갈라야 한다** — 안 받았다 / 받다 실패했다 / 받았는데 못 읽었다.
 * 뜻은 `/admin/attachments` 가 표로 적는다. */
function StatusPill({ f }: { f: AdminAttachment }) {
  if (f.fetch_status === null) {
    return <span className={`${a.pill} ${a.pillNone}`}>안 받음</span>;
  }
  if (f.fetch_status !== "ok") {
    return <span className={`${a.pill} ${a.pillBad}`}>{f.fetch_status}</span>;
  }
  const s = f.parse_status;
  const tone = s === "ok" ? a.pillOk : s === "failed" ? a.pillBad : a.pillWarn;
  return <span className={`${a.pill} ${tone}`}>{s ?? "미시도"}</span>;
}

function stamp(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
