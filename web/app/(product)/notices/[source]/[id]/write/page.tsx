import { Suspense } from "react";
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
 * 공고 상세 상단의 「사업계획서 작성」에서 들어온다.
 *
 * ## `?doc` 은 이제 이 화면이 스스로 쓴다
 *
 * **2026-08-24 morph 가 없어졌다.** 공고 상세의 서류 카드마다 있던 「이 양식으로
 * 쓰기」가 상단 버튼 하나로 합쳐지면서 `?doc` 을 물고 오는 출발점이 사라졌다 —
 * 이 페이지에 `ViewTransition` 을 남겨 둬도 짝이 안 맺혀 이름만 붙는다.
 *
 * 값 자체는 산다. `WritePanes` 가 양식 칩을 누를 때 `router.replace` 로 이 자리에
 * 도로 적고, 그것이 새로고침 뒤 `initialDoc` 이 된다.
 *
 * `<Suspense>` 는 그대로 둔다. **morph 때문에 만든 구조였지만** 셋을 최상단에서
 * `await` 하면 초안·양식·공고가 다 올 때까지 화면이 통째로 빈다 — 지금은 껍데기가
 * 먼저 서고 「초안을 불러오는 중이에요」가 그 안에 앉는다.
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

  // **sha256 이 아니라 구간 id 다.** 한 첨부에 서식이 여럿이라 sha256 은 카드마다
  // 유일하지 않다(실측 224쌍 중 65 · 29%). 숫자만 통과시키는 것은 이 값이 주소에서
  // 오기 때문이다 — 아래로 내려가면 `document.id` 와 문자열로 비교된다.
  const doc = /^\d{1,18}$/.test(sp.doc ?? "") ? sp.doc! : null;

  const back = `/notices/${source}/${encodeURIComponent(external)}?company=${encodeURIComponent(company)}`;

  return (
    <div className={styles.page}>
      <Link href={back} className={styles.back}>
        ← 공고로 돌아가기
      </Link>

      <div className={styles.shell}>
        <Suspense fallback={<Loading />}>
          <Panes source={source} external={external} company={company} doc={doc} />
        </Suspense>
      </div>
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
