import Link from "next/link";
import { notFound } from "next/navigation";
import { Attachments } from "@/components/Attachments";
import { FormDocuments } from "@/components/FormDocuments";
import { Deadline } from "@/components/Deadline";
import { NotYet } from "@/components/NotYet";
import { getNotice, getNoticeDocuments } from "@/lib/api";
import { fromApi } from "@/lib/documents";
import { periodOf } from "@/lib/deadline";
import { DEFAULT_COMPANY } from "@/lib/wiki";
import styles from "./page.module.css";

const SOURCE_NAME: Record<string, string> = {
  bizinfo: "기업마당",
  kstartup: "K-Startup",
};

/** S3 공고 상세 — SPEC §5.2. **옛 이름은 S5 였다**(ADR-0053).
 *
 * **배점 섹션이 없다.** 시연에 `25 / 25 / 30 / 20`이 있지만 ADR-0019 와 정면으로 어긋난다.
 *
 * **빈 섹션이 넷에서 둘로 줄었다**(2026-08-22 · plan/21 T-0120).
 *
 * - 「왜 맞는지」 — `notice_fit` 이 채운다. 이제 값이 있다
 * - ~~「자격이 되는지」~~ — **없앴다.** [ADR-0003](../../../../../docs/adr/0003-판별-비노출.md)
 *   이 「판정은 뒤에서 하고 화면은 결과만 준다」로 정했고, 자격 결과는 **목록에서
 *   빼는 것**으로 이미 나갔다. 이 자리를 값으로 채우면 그 결정을 되돌리는 것이 된다 —
 *   기다리던 것이 사실은 만들면 안 되는 것이었다
 * - 「어떻게 심사해요」·「놓치기 쉬운 것」 — F2-3 이 없어서 그대로 비어 있다 */
export default async function NoticeDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ source: string; id: string }>;
  searchParams: Promise<{ company?: string }>;
}) {
  const { source, id } = await params;
  const sp = await searchParams;
  const external = decodeURIComponent(id);
  const company = sp.company?.trim() || DEFAULT_COMPANY;
  // 서류는 없어도 화면이 떠야 한다. 공고와 같이 부르되 실패를 따로 받는다.
  const [notice, docs] = await Promise.all([
    getNotice(source, external, company),
    getNoticeDocuments(source, external),
  ]);
  if (!notice) notFound();

  const period = periodOf(notice);
  const meta = [notice.organization, notice.supervisor, notice.category].filter(Boolean);

  return (
    <article className={styles.page}>
      <Link href="/" className={styles.back}>
        ← 공고 목록
      </Link>

      <header className={styles.head}>
        <Deadline notice={notice} />
        <h1 className={styles.title}>{notice.title ?? "제목이 없어요"}</h1>
        <p className={styles.meta}>
          {meta.length > 0 ? meta.join(" · ") : "기관을 안 알려줬어요"}
          <span className={styles.dot} aria-hidden="true">
            ·
          </span>
          <span className={styles.source}>{SOURCE_NAME[source] ?? source}</span>
        </p>
      </header>

      <dl className={styles.facts}>
        <dt>접수 기간</dt>
        <dd data-numeric>{period ?? "안 알려줬어요"}</dd>
        {notice.detail_url && (
          <>
            <dt>원문</dt>
            <dd>
              <a href={notice.detail_url} className={styles.ext}>
                공고 원문 보기
              </a>
            </dd>
          </>
        )}
      </dl>

      <section className={styles.summary} aria-labelledby="summary-title">
        <h2 id="summary-title" className={styles.sectionTitle}>
          개요
        </h2>
        {notice.summary ? (
          <div className={styles.body}>
            {notice.summary.split("\n\n").map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        ) : (
          <p className={styles.noBody}>출처가 개요를 안 줬어요. 원문을 열어 보세요.</p>
        )}
      </section>

      {docs && (
        <>
          <FormDocuments
            data={fromApi(docs, {
              id: external,
              source,
              title: notice.title ?? "",
              url: notice.detail_url ?? null,
            })}
          />
          {/* 양식이 있을 때만 문을 연다. **없는 곳으로 보내지 않는다** — 서류가 0개면
              쓰기 화면도 "쓸 양식이 없어요" 밖에 못 보여 준다.
              카피는 `/documents/<표본>` 이 쓰는 것과 같다(DESIGN.md §8.3-3).

              **`company` 를 물고 간다.** 저쪽이 초안을 열려면 누구의 것인지 알아야
              하는데 인증이 없다 — 안 물리면 쓰기 화면이 기본 회사로 떨어져서
              사용자가 남의 초안을 본다. */}
          {docs.documents.length > 0 && (
            <Link
              href={`/notices/${source}/${encodeURIComponent(external)}/write?company=${encodeURIComponent(company)}`}
              className={styles.write}
            >
              여기에 뭘 쓰는지 보기
            </Link>
          )}
        </>
      )}

      <Attachments items={notice.attachments} decoded={notice.decoded_count} />

      {/* 왜 맞는지. **`null` 이면 자리를 안 그린다** — 「안 맞아요」가 아니라
        * 「아직 안 봤어요」라서, `NotYet` 으로 떨어뜨려 무엇이 없는지 말한다.
        *
        * **등급을 글자로 안 낸다.** `맞다`·`애매` 를 적으면 그것이 눈금 없는
        * 점수가 된다(§7 · §12.2) — 여기 올라온 것 자체가 판정 결과다 */}
      {notice.fit ? (
        <section className={styles.fit} aria-labelledby="fit-title">
          <h2 id="fit-title" className={styles.sectionTitle}>
            왜 맞는지
          </h2>
          <p className={styles.fitReason}>{notice.fit.reason}</p>
          {notice.fit.evidence_count > 0 && (
            <p className={styles.fitEvidence} data-numeric>
              내 사업 정보 <b>{notice.fit.evidence_count}</b>개에서 나왔어요
            </p>
          )}
        </section>
      ) : (
        <div className={styles.gaps}>
          <NotYet
            title="왜 맞는지"
            why="사업 위키가 있어야 공고 취지와 대 볼 수 있어요. 파일을 올리면 골라 드려요."
          />
        </div>
      )}

      {/* 자리는 있고 값이 없는 둘. 예시 데이터를 넣지 않는다.
        *
        * **「자격이 되는지」가 여기 있었다.** 없앤 이유는 값이 생겨서가 아니라
        * ADR-0003 이 그 화면을 금지해서다 — 못 넘는 공고는 목록에서 빠지는 것으로
        * 이미 답했고, 여기 대조표를 두면 우리 일을 사용자에게 떠넘긴다 */}
      <div className={styles.gaps}>
        <NotYet
          title="어떻게 심사해요"
          why="서류에서 심사 항목을 아직 안 뽑았어요. 서류 글자는 이미 읽어 뒀어요."
        />
        <NotYet
          title="놓치기 쉬운 것"
          why="심사 항목을 뽑고 나서 알려 드릴 수 있어요."
        />
      </div>
    </article>
  );
}
