import AttachCard from "@/components/AttachCard";
import { getAdminAttach, getAdminAttachments } from "@/lib/admin";
import a from "../admin.module.css";
import styles from "./page.module.css";

/** 첨부 해독 현황. Jinja2 `attachments.html` 을 옮긴 것이다.
 *
 * **조용한 누락이 첫 줄이다**(plan/07 검증). 첨부 URL 중 상태 행이 없는 것,
 * 곧 조용히 사라진 건수다. 여기가 0이 아니면 아래 해독률은 믿을 게 못 된다. */

/** **빌드 때 굳으면 안 된다.** 이 화면은 파라미터가 없어서 Next 가 기본으로 미리 그리려 하고,
 *  그러면 해독 현황이 배포 시점 숫자로 박힌 뒤 다시 안 바뀐다. 재해독을 돌려도 화면이 옛 숫자를
 *  말하는 것이 이 화면에서 가장 나쁜 고장이다 — 여기 숫자를 근거로 T-0007 을 정한다.
 *
 *  `/admin/notices` 는 `searchParams` 를 읽어서 자동으로 동적이다. 여기와 `/admin/ingest`
 *  둘만 명시가 필요하다. */
export const dynamic = "force-dynamic";

/** 상태값이 무슨 뜻인지 **화면이 직접 적는다.** 셋을 갈라 놓고 뜻을 안 적으면
 *  갈라 놓은 의미가 없다. `models.py` 의 `FetchStatus` · `ParseStatus` 와 짝이다. */
const FETCH_WHY: Record<string, string> = {
  ok: "받았다",
  not_found: "4xx / 5xx",
  not_html: "HTTP 200 인데 파일이 아니라 HTML 오류 페이지였다. 저장하지 않았다",
  too_large: "크기 한도 초과. 받지 않았다",
  failed: "네트워크·타임아웃",
};

const PARSE_WHY: Record<string, string> = {
  ok: "텍스트가 나왔다",
  empty: "파서는 돌았는데 0바이트다 — 스캔본",
  unsupported: "지원 목록에 없는 포맷. 시도하지 않았다",
  failed: "시도했고 실패했다",
  container: "ZIP. 안의 목록만 읽었다",
};

const PLAN07 =
  "https://github.com/YASICJUNWOO/finnect-new/blob/master/docs/plan/07-첨부-내려받기와-해독.md";
const T0007 =
  "https://github.com/YASICJUNWOO/finnect-new/blob/master/docs/plan/02-수집과-추출.md#t-0007-스캔-pdf-처리-판단";

export default async function AdminAttachmentsPage() {
  const [{ coverage: c, ocr, formats }, attach] = await Promise.all([
    getAdminAttachments(),
    getAdminAttach(),
  ]);

  const n = (v: number) => v.toLocaleString("ko-KR");

  return (
    <>
      <h1 className={a.h1}>첨부 해독</h1>
      <p className={a.lead}>
        첨부를 내려받아 텍스트를 뽑은 결과다. 뽑은 텍스트로 무엇을 판단하지는 않는다 (
        <a href={PLAN07} rel="noreferrer" target="_blank" className={a.link}>
          plan/07
        </a>
        ).
      </p>

      <h2 className={a.h2}>조용한 누락</h2>
      {c.unaccounted === 0 ? (
        <p className={styles.first}>
          첨부 <span data-numeric>{n(c.listed)}</span>건 · URL{" "}
          <span data-numeric>{n(c.urls)}</span>개 · 상태 행{" "}
          <span data-numeric>{n(c.files)}</span>개. <b>상태가 없는 첨부는 0건이다.</b>
        </p>
      ) : (
        <p className={`${styles.first} ${a.bad}`}>
          ⚠ 첨부 URL <span data-numeric>{n(c.urls)}</span>개 중{" "}
          <b>
            <span data-numeric>{n(c.unaccounted)}</span>개에 상태가 없다.
          </b>{" "}
          아래 숫자는 모집단이 아니다.
        </p>
      )}
      <p className={a.note}>
        이 화면에서 가장 먼저 봐야 하는 값이다. 여기가 0이 아니면 해독률은 믿을 게 못 된다.
      </p>

      {/* **「조용한 누락」 아래다.** 저 절이 스스로 "가장 먼저 봐야 하는 값"이라고
       *  적어 뒀으니 동작을 그 위에 올리면 그 문장이 거짓이 된다(ADR-0071). */}
      <h2 className={a.h2}>첨부 받기</h2>
      <p className={a.note}>
        아직 안 받은 것만 받는다. 수집은 첨부 메타데이터까지만 담고 파일은 여기서 받는다.
        실행에는 수집과 같은 실행 토큰이 필요하다 — 없으면 버튼이 503으로 막힌다.
      </p>
      <div className={a.cards}>
        <AttachCard initial={attach} />
      </div>

      <h2 className={a.h2}>내려받기</h2>
      <StatusTable rows={c.fetch} why={FETCH_WHY} fallback="" />

      <h2 className={a.h2}>해독</h2>
      <StatusTable
        rows={c.parse}
        why={PARSE_WHY}
        fallback="내려받기가 실패해 해독을 시도하지 않았다"
      />

      <h2 className={a.h2}>포맷별</h2>
      <p className={a.note}>
        포맷은 파일명이 아니라 <b>내용</b>으로 판정한 것이다. 확장자가 <code>.hwp</code>인데
        실제로는 HWPX인 파일이 실재한다.
      </p>
      <div className={a.wrap}>
        <table className={a.table}>
          <thead>
            <tr>
              <th>포맷</th>
              <th>상태</th>
              <th className={a.num}>건수</th>
              <th className={a.num}>평균 글자</th>
            </tr>
          </thead>
          <tbody>
            {c.by_ext.map((r) => (
              <tr key={`${r.ext}/${r.status}`}>
                <td>
                  <code>{r.ext || "?"}</code>
                </td>
                <td>
                  <Pill status={r.status} />
                </td>
                <td className={a.num}>{n(r.count)}</td>
                <td className={a.num}>{r.avg_chars ? n(r.avg_chars) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className={a.h2}>지원 포맷 목록</h2>
      <p className={styles.formats}>
        <code>ATTACHMENT_FORMATS</code> ={" "}
        {formats.map((f) => (
          <span key={f} className={a.tag}>
            {f}
          </span>
        ))}
      </p>
      <p className={a.note}>
        설정이라 코드를 고치지 않고 바꾼다. <b>목록을 줄이면 그만큼 미해독이 늘 뿐, 사라지지
        않는다.</b> 여기 없는 포맷은 <code>unsupported</code>로 기록된다.
      </p>

      <h2 className={a.h2}>OCR 없이는 못 읽는 것</h2>
      <p className={a.note}>
        <a href={T0007} rel="noreferrer" target="_blank" className={a.link}>
          T-0007
        </a>
        이 이 숫자를 근거로 OCR 도입을 정한다. 지금은 정하지 않는다.
      </p>
      <div className={a.wrap}>
        <table className={a.table}>
          <thead>
            <tr>
              <th>무엇</th>
              <th className={a.num}>건수</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                텍스트가 0바이트인 PDF <span className={a.muted}>— 스캔본</span>
              </td>
              <td className={a.num}>{n(ocr.pdf_empty)}</td>
            </tr>
            <tr>
              <td>
                이미지 첨부 <span className={a.muted}>— png · jpg</span>
              </td>
              <td className={a.num}>{n(ocr.images)}</td>
            </tr>
            <tr>
              <td>
                그중 <b>공고문</b> 자리에 붙은 이미지
              </td>
              <td className={a.num}>{n(ocr.image_notices)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}

function StatusTable({
  rows,
  why,
  fallback,
}: {
  rows: { status: string | null; count: number }[];
  why: Record<string, string>;
  fallback: string;
}) {
  return (
    <div className={a.wrap}>
      <table className={a.table}>
        <thead>
          <tr>
            <th>상태</th>
            <th className={a.num}>건수</th>
            <th>뜻</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.status ?? "none"}>
              <td>
                <Pill status={r.status} />
              </td>
              <td className={a.num}>{r.count.toLocaleString("ko-KR")}</td>
              <td className={a.muted}>{(r.status && why[r.status]) || fallback}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** 상태 하나. **`null` 은 '미시도'다** — 실패와 구분한다. */
function Pill({ status }: { status: string | null }) {
  if (status === null) {
    return <span className={`${a.pill} ${a.pillNone}`}>미시도</span>;
  }
  const tone =
    status === "ok" ? a.pillOk : status === "failed" || status === "not_found" ? a.pillBad : a.pillWarn;
  return <span className={`${a.pill} ${tone}`}>{status}</span>;
}
