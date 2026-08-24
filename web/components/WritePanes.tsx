"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DocViewer } from "./DocViewer";
import { DraftThread } from "./DraftThread";
import { DemoViewerLoading, isDemoNotice, useDemoReply } from "./DemoReply";
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
  /** 시연 시계. **두 단이 같은 것을 본다.**
   *
   *  예전에는 `DraftThread` 가 들고 `onDemoPhase` 로 올려 줬는데, 그 컴포넌트는
   *  `draft` 가 있을 때만 서므로 **초안을 못 불러온 화면에서는 로딩이 영영 안 걷혔다.**
   *  트리거가 「버튼을 눌렀다」에서 「화면에 들어왔다」로 바뀌면서 그 경우가 실제로
   *  생겼다 — 누르는 사람이 없으니 못 불러온 화면도 로딩부터 시작한다.
   *
   *  **공고를 본다**(`isDemoNotice`). 안 보면 어느 신청서에서든 나린데이터로 채운
   *  현대모비스 파일이 열린다. */
  const demoOn = isDemoNotice(source, externalId);
  const demo = useDemoReply(demoOn);
  /** 세는 중인가. **턴 둘을 한 값으로 든다** — 오른쪽에 겹치는 로딩은 같은 것이고
   *  글만 다르다(집필 · 수정). 부르는 쪽에서 둘을 따로 보면 한쪽을 빠뜨린다. */
  const demoBusy = demoOn && (demo.phase === "writing" || demo.phase === "revising");

  const active = all.find((d) => d.id === docId) ?? all[0] ?? null;

  /** 스레드로 내려 줄 시연 시계. **`demoOn` 이 아니면 `undefined` 다** — 있는 것이
   *  「이 화면에서 시연이 켜졌다」는 뜻이라야 부르는 쪽이 값 하나만 보면 된다. */
  const threadDemo = useMemo(
    () => (demoOn ? { phase: demo.phase, start: demo.start, revise: demo.revise } : undefined),
    [demoOn, demo.phase, demo.start, demo.revise],
  );

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
    // **시연에서는 미리 만들어 둔 파일을 연다.** 초안을 안 만들었으니 서버가 채울
    // 것이 없다 — 아래 진짜 경로는 `live.documents` 가 비어서 `null` 로 떨어진다.
    // **턴이 끝난 뒤에만 갈아 끼운다**(`file` 이 그때 앉는다) — 처음부터 채워져
    // 있으면 「바꿨어요!」가 이미 일어난 일을 두고 하는 거짓말이 된다.
    //
    // **어느 파일인지는 시계가 안다**(`demo.file`). 여기서 단계로 갈래를 만들면
    // 세는 동안(`revising`) 무엇을 열지 정할 수 없다 — 답이 「직전 것을 그대로」라서다.
    // 갈래로 만들었더니 두 번째 수정에서 **고치기 전 파일로 6초 되돌아갔다**(실측).
    if (demoOn && demo.file) return demo.file;
    if (!active || !live || live.documents.length === 0) return null;
    const items = leaves(live.documents.flatMap((d) => d.items));
    const stamp = `${items.length}-${items.reduce((n, i) => n + bodyOf(i).length, 0)}`;
    return `${filledDocumentUrl(source, externalId, active.id, company)}&v=${stamp}`;
  }, [active, live, source, externalId, company, demoOn, demo.file]);

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
              demo={threadDemo}
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
          /* **감싸는 div 가 늘 있다.** 시연 로딩이 걷힐 때만 없애면 `DocViewer` 가
             언마운트되고 rhwp WASM 8.3MB 를 다시 받는다 — 그 자리가 마침 채운 파일을
             여는 순간이라 10초 뒤가 가장 느려진다 */
          <div className={styles.stage}>
            <DocViewer
              doc={active}
              noticeUrl={noticeUrl}
              onPages={setPages}
              filledUrl={filledUrl}
              onFilled={onFilled}
            />
            {demoBusy && <DemoViewerLoading revising={demo.phase === "revising"} />}
          </div>
        }
      />
    </>
  );
}
