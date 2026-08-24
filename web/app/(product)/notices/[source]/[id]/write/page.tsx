import { Suspense, ViewTransition } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { WritePanes } from "@/components/WritePanes";
import { getNotice, getNoticeDocuments } from "@/lib/api";
import { getDraft } from "@/lib/draft";
import type { Draft } from "@/lib/draft";
import { fromApi } from "@/lib/documents";
import { currentCompany } from "@/lib/wiki";
import styles from "./page.module.css";

/** S4 신청서 쓰기 — SPEC §5.2. **2단 워크스페이스다**(2026-08-22).
 *
 * 왼쪽이 초안(대화처럼 차례로 쌓인다), 오른쪽이 양식(원본 파일을 rhwp 로 연다).
 * 공고 상세의 「이 양식으로 쓰기」에서 `?doc=<sha256>` 을 물고 넘어온다.
 *
 * ## 왜 최상단에서 `await` 하지 않는가
 *
 * **morph 가 서스펜드에 진다.** Next 의 view-transitions 문서가 「도착 콘텐츠가
 * fallback 으로 먼저 떨어지면 쌍이 안 맺힌다」고 적어 뒀다. 예전 이 페이지는
 * 최상단에서 `await Promise.all([getNotice, getNoticeDocuments, safeDraft])` 를
 * 해서 통째로 서스펜드했고, 그대로 두면 **morph 가 아예 안 일어난다.**
 *
 * 그래서 `searchParams` 만으로 **이름 붙은 상자를 즉시 그리고** 데이터가 필요한
 * 것을 `<Suspense>` 안으로 내린다. `?doc` 이 searchParams 라 fetch 없이 이름을
 * 붙일 수 있는 것이 이 구조가 성립하는 이유다.
 *
 * **`company` 는 `currentCompany()` 가 정한다**(ADR-0066). 주소가 말하면 그것이
 * 이기고, 아니면 입장 게이트가 앉힌 쿠키다 — `/wiki` 와 같은 규칙이다. */
export default async function NoticeWritePage({
  params,
  searchParams,
}: {
  params: Promise<{ source: string; id: string }>;
  searchParams: Promise<{ company?: string; doc?: string }>;
}) {
  // **여기 리소스 힌트가 있었고 둘 다 걷어냈다**(2026-08-23).
  //
  // ① `preconnect(edwardkim.github.io)` — studio 를 우리 오리진으로 옮기면서
  //    (`lib/documents.ts` 의 `STUDIO_URL`) 미리 열 외부 오리진이 없어졌다.
  //
  // ② `preload(wasm · js, { as: "fetch" })` — **헛돌았다.** 뷰어가 그 파일을 받는
  //    것은 `DocViewer` 가 세운 iframe 안이고, **preload 캐시는 문서마다 따로다.**
  //    실측에서 같은 URL 이 `frame=main` 과 `frame=iframe` 으로 두 번 나갔다 —
  //    3.2MB 를 미리 받아 놓고 아무도 안 쓴 것이다. 캐시는 이제 `next.config.ts`
  //    의 `headers()` 가 준다.
  const { source, id } = await params;
  const sp = await searchParams;
  const external = decodeURIComponent(id);
  const company = await currentCompany(sp.company);

  // **`view-transition-name` 에 그대로 들어가는 값이다.** 숫자만 통과시킨다 —
  // 아무 문자열이나 CSS 식별자 자리에 넣으면 안 된다.
  //
  // **sha256 이 아니라 구간 id 다.** 한 첨부에 서식이 여럿이라 sha256 은 카드마다
  // 유일하지 않고(실측 29%), 겹치면 morph 가 죽는다.
  const doc = /^\d{1,18}$/.test(sp.doc ?? "") ? sp.doc! : null;

  const back = `/notices/${source}/${encodeURIComponent(external)}?company=${encodeURIComponent(company)}`;

  return (
    <div className={styles.page}>
      <Link href={back} className={styles.back}>
        ← 공고로 돌아가기
      </Link>

      {/* **이름을 `doc` 이 있을 때만 붙인다.** 없으면 어느 카드에서 왔는지 모르는데,
          그때 morph 하면 아무 문서나 골라 이은 것이 된다 */}
      {doc ? (
        <ViewTransition name={`doc-${doc}`} share="morph" default="none">
          <div className={styles.shell}>
            <Suspense fallback={<Loading />}>
              <Panes source={source} external={external} company={company} doc={doc} />
            </Suspense>
          </div>
        </ViewTransition>
      ) : (
        <div className={styles.shell}>
          <Suspense fallback={<Loading />}>
            <Panes source={source} external={external} company={company} doc={null} />
          </Suspense>
        </div>
      )}
    </div>
  );
}

/** **회색 막대를 안 세운다.** 항목이 몇 개인지 모르는 채로 뼈대를 그리면 그것이
 * 예시 데이터다(DESIGN.md §7). 한 줄만 적는다. */
function Loading() {
  return <p className={styles.loading}>초안을 불러오는 중이에요.</p>;
}

/** 데이터가 필요한 부분. **서스펜드는 여기서만 일어난다.** */
async function Panes({
  source,
  external,
  company,
  doc,
}: {
  source: string;
  external: string;
  company: string;
  doc: string | null;
}) {
  // 초안을 못 불러와도 **양식은 떠야 한다.** 셋을 같이 부르되 실패를 따로 받는다 —
  // `getNoticeDocuments` 가 배포본에서 상세를 통째로 500 으로 만든 적이 있다.
  const [notice, docs, draft] = await Promise.all([
    getNotice(source, external, company),
    getNoticeDocuments(source, external),
    safeDraft(source, external, company),
  ]);
  if (!notice) notFound();

  return (
    <WritePanes
      title={notice.title ?? "제목이 없어요"}
      noticeUrl={notice.detail_url ?? null}
      docs={
        docs
          ? fromApi(docs, {
              id: external,
              source,
              title: notice.title ?? "",
              url: notice.detail_url ?? null,
            })
          : null
      }
      draft={draft}
      source={source}
      externalId={external}
      company={company}
      initialDoc={doc}
    />
  );
}

/** 초안을 못 불러오는 것과 초안이 없는 것을 가른다. **`null` 은 모른다는 뜻이다.** */
async function safeDraft(
  source: string,
  external: string,
  company: string,
): Promise<Draft | null> {
  try {
    return await getDraft(source, external, company);
  } catch (e) {
    console.error("초안을 못 불러왔다 — 양식은 그대로 띄운다", e);
    return null;
  }
}
