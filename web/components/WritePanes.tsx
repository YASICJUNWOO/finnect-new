"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DocViewer } from "./DocViewer";
import { DraftThread } from "./DraftThread";
import { DEMO, DEMO_FILLED_URL, type DemoPhase } from "./DemoReply";
import { WriteWorkspace } from "./WriteWorkspace";
import { bodyOf, leaves, type Draft } from "@/lib/draft";
import type { NoticeDocuments } from "@/lib/documents";
import { filledDocumentUrl } from "@/lib/api";
import styles from "./WritePanes.module.css";

/** S4 의 두 단을 잇는 자리. **껍데기(`WriteWorkspace`)와 알맹이 사이에 있다.**
 *
 * 워크스페이스는 배치만 알고 뷰어는 문서 하나만 안다. 「지금 어느 문서인가」와
 * 「왼쪽에서 문서를 누르면 오른쪽이 따라간다」가 여기 있다.
 *
 * **`?doc` 을 갈아 끼울 때 `router.replace` 다.** 히스토리를 쌓으면 문서를 세 번
 * 바꾼 사람이 뒤로 가기를 세 번 눌러야 공고로 돌아간다. */
export function WritePanes({
  title,
  noticeUrl,
  docs,
  draft,
  source,
  externalId,
  company,
  initialDoc,
}: {
  title: string;
  noticeUrl: string | null;
  /** `null` 은 「양식이 없다」가 아니라 「모른다」다(`lib/api.ts`) */
  docs: NoticeDocuments | null;
  /** `null` 은 초안을 못 불러왔다는 뜻이다 */
  draft: Draft | null;
  source: string;
  externalId: string;
  company: string;
  /** 구간 id. **sha256 이 아니다** */
  initialDoc: string | null;
}) {
  const router = useRouter();
  const all = useMemo(() => docs?.documents ?? [], [docs]);
  // **문서 id 로 고른다.** sha256 은 한 첨부에 서식이 여럿일 때 겹친다(실측 29%)
  const [docId, setDocId] = useState<string | null>(initialDoc ?? all[0]?.id ?? null);
  const [pages, setPages] = useState<number | null>(null);
  const [left, setLeft] = useState<number | null>(null);
  /** 왼쪽에서 살아 움직이는 초안. **서버가 준 `draft` 는 처음 한 장뿐이다** —
   *  초안을 쓰거나 고치면 그 결과가 `DraftThread` 안에서만 갱신되므로, 여기로
   *  올려 받지 않으면 오른쪽 뷰어가 **새로고침 전까지 옛 파일을 보여 준다.** */
  const [live, setLive] = useState<Draft | null>(draft);
  /** 시연이 어디까지 갔나. **`done` 이면 오른쪽이 채워 둔 신청서를 연다** */
  const [demoPhase, setDemoPhase] = useState<DemoPhase>("idle");

  const active = all.find((d) => d.id === docId) ?? all[0] ?? null;

  /** 채운 파일의 주소 (plan/24 T-0155). **초안이 없으면 안 만든다** — 채울 것이
   *  없는데 부르면 원본과 같은 파일을 한 번 더 만드는 값만 든다.
   *
   *  **초안 내용을 주소에 넣는다.** 다시 쓰면 내용이 달라지는데 주소가 같으면
   *  뷰어가 다시 안 연다 — 브라우저 캐시가 아니라 `useEffect` 의 의존성 문제다.
   *
   *  **항목 수만으로는 모자란다.** 초기화도 고쳐 쓰기도 항목 수를 안 바꾼다 —
   *  글이 통째로 달라져도 주소가 같아서 옛 파일이 그대로 떴다. 글 길이의 합까지
   *  넣으면 그 둘이 갈린다. */
  const filledUrl = useMemo(() => {
    // **시연에서는 미리 채워 둔 파일을 연다.** 초안을 안 만들었으니 서버가 채울
    // 것이 없다 — 아래 진짜 경로는 `live.documents` 가 비어서 `null` 로 떨어진다.
    // **「바꿨어요!」가 뜬 뒤에만 갈아 끼운다** — 처음부터 채워져 있으면 그 말이
    // 이미 일어난 일을 두고 하는 거짓말이 된다.
    if (DEMO && demoPhase === "done") return DEMO_FILLED_URL;
    if (!active || !live || live.documents.length === 0) return null;
    const items = leaves(live.documents.flatMap((d) => d.items));
    const stamp = `${items.length}-${items.reduce((n, i) => n + bodyOf(i).length, 0)}`;
    return `${filledDocumentUrl(source, externalId, active.id, company)}&v=${stamp}`;
  }, [active, live, source, externalId, company, demoPhase]);

  const onFilled = useCallback((_filled: number, remaining: number) => {
    setLeft(remaining);
  }, []);

  /** 주소를 따라 바꾼다. **`scroll: false`** — 단이 각자 구르는 화면이라
   * 위로 튀면 읽던 자리를 잃는다. */
  const pick = useCallback(
    (next: string) => {
      setDocId(next);
      const qs = new URLSearchParams({ company, doc: next });
      router.replace(
        `/notices/${source}/${encodeURIComponent(externalId)}/write?${qs}`,
        { scroll: false },
      );
    },
    [router, source, externalId, company],
  );

  /** 왼쪽 구분선 → 오른쪽. `DraftDocument` 는 sha256 을 안 들고 있어서
   * `document_id` 로 받아 여기서 맞춘다 — 둘 다 `document.id` 에서 온 값이다. */
  const focusDoc = useCallback(
    (documentId: number) => {
      const found = all.find((d) => d.id === String(documentId));
      if (found) pick(found.id);
    },
    [all, pick],
  );

  /** 칩 둘 이상이 같은 파일을 가리키는 일이 흔하다 — 한 첨부에 서식이 여럿
   * 들어 있기 때문이다. **그 사실을 적는다**(그러지 않으면 칩을 눌러도 같은
   * 화면이 떠서 고장 난 것으로 읽힌다). */
  const sameFile = new Set(all.map((d) => d.sha256)).size < all.length;

  const header = (
    <div className={styles.head}>
      {all.length > 1 && (
        <div className={styles.chips}>
          {all.map((d) => (
            <button
              key={d.id}
              type="button"
              className={styles.chip}
              aria-pressed={d.id === active?.id}
              onClick={() => pick(d.id)}
            >
              {d.title}
            </button>
          ))}
        </div>
      )}
      <p className={styles.meta}>
        {/* **「0쪽」을 안 그린다** — 빈 문서로 읽힌다 */}
        {pages !== null && (
          <span data-numeric>{pages}쪽</span>
        )}
        {/* **못 채운 칸을 조용히 넘기지 않는다.** hwp 는 안내문이 든 칸을 못
            덮어써서 남는 자리가 많다 — 말 안 하면 사용자가 `000-0000-0000` 을
            그대로 제출한다. 0 이면 안 적는다(§10 — 빼도 뜻이 같은 말은 지운다) */}
        {left !== null && left > 0 && (
          <span className={styles.same}>
            <span data-numeric>{left}</span>칸은 직접 채워 주세요
          </span>
        )}
        {sameFile && <span className={styles.same}>같은 파일이에요. 파일 전체가 열려요.</span>}
      </p>
    </div>
  );

  return (
    <>
      <h1 className={styles.title}>{title}</h1>
      <WriteWorkspace
        collapsible={all.length > 0}
        viewerHeader={header}
        thread={
          draft ? (
            <DraftThread
              initial={draft}
              source={source}
              externalId={externalId}
              company={company}
              onFocusDoc={focusDoc}
              onDraft={setLive}
              onDemoPhase={setDemoPhase}
            />
          ) : (
            /* **`null` 은 「초안이 없다」가 아니라 「모른다」다.** 빈 화면을 띄우면
               우리가 못 읽은 것을 공고 탓으로 돌린다 */
            <div className={styles.gone}>
              <p className={styles.goneTitle}>초안을 지금 못 불러왔어요</p>
              <p className={styles.goneBody}>잠시 뒤에 다시 열어 주세요.</p>
            </div>
          )
        }
        viewer={
          <DocViewer
            doc={active}
            noticeUrl={noticeUrl}
            onPages={setPages}
            filledUrl={filledUrl}
            onFilled={onFilled}
          />
        }
      />
    </>
  );
}
