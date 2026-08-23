"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Draft, DraftItem, DraftStart } from "@/lib/draft";
import { bodyOf, leaves } from "@/lib/draft";
import styles from "./DraftView.module.css";

/** 초안 (S4 · plan/21 T-0122 · T-0123).
 *
 * **`FormFill` 과 다른 물건이다.** 저쪽은 양식의 빈 칸을 보여 주는 화면이고 여기는
 * **이미 써진 글**을 보여 주는 화면이다. 한 컴포넌트에 `variant` 로 합치지 않는다 —
 * 근거·못 채운 자리·되돌리기가 저쪽에는 뜻이 없다.
 *
 * **초안이 먼저 다 나오고 그다음에 묻는다**(ADR-0028). 그래서 이 화면에 폼이 앞에
 * 서지 않는다 — 글이 먼저 있고, 못 채운 자리가 그 옆에 붙는다.
 *
 * **저장이 항목 단위다**(ADR-0055). 문단 단위로 두면 두 문단을 하나로 합치는 편집을
 * 표현할 수 없다. */

/** 상태를 **글자로** 가른다. 색으로 가르면 §7(UI 크롬에 색 금지)에 걸리고,
 * 색조 하나에 뜻 둘을 얹지 않는다는 규칙(§2)에도 걸린다.
 *
 * **`blank` 만 물어보는 자리다**(F6-6). 나머지는 다른 이유로 비어 있다 — 섞으면
 * 화면이 사용자에게 **이미 아는 것을 묻는다.** */
const STATUS: Record<string, string> = {
  drafted: "썼어요",
  answered: "답을 반영했어요",
  blank: "재료가 없어서 못 썼어요",
  no_needs: "쓰는 자리가 아니에요",
  yielded: "다른 항목에 썼어요",
  unwritten: "쓰다가 실패했어요",
  stale: "근거가 바뀌었어요",
};

function Evidence({ item }: { item: DraftItem }) {
  const all = item.paragraphs.flatMap((p) => p.evidence);
  if (all.length === 0) return null;

  return (
    <details className={styles.evBox}>
      <summary className={styles.evSummary}>
        근거 <span data-numeric>{all.length}</span>개
      </summary>
      <ul className={styles.evList}>
        {all.map((e, i) => (
          <li key={`${e.fact_id}-${i}`} className={styles.ev}>
            <span className={styles.evPlace}>{e.place_label}</span>
            <span className={styles.evText}>{e.text}</span>
            {/* **원문 조각을 먼저 보여 준다**(F1-3). `user_stated` 는 원문이 없다 */}
            {e.quote && <span className={styles.evQuote}>{e.quote}</span>}
            {e.source_type === "user_stated" && (
              <span className={styles.evSaid}>내가 알려준 값이에요</span>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}

/** 받침이 있으면 앞엣것, 없으면 뒤엣것.
 *
 * **자리 이름을 우리가 못 고른다.** 기획 트리와 매칭 정보가 주는 이름이라 `기록`
 * 처럼 받침으로 끝나기도 하고 `대표자` 처럼 아니기도 하다 — 조사를 고정하면 그중
 * 절반이 「기록가 없어서」가 된다. **목록의 마지막 낱말이 정한다.**
 *
 * 한글이 아니면(숫자·로마자) 판정할 근거가 없으므로 받침 없는 쪽을 준다. */
function josa(word: string, withBatchim: string, without: string): string {
  const code = (word.trim().at(-1) ?? "").charCodeAt(0);
  if (Number.isNaN(code) || code < 0xac00 || code > 0xd7a3) return without;
  return (code - 0xac00) % 28 === 0 ? without : withBatchim;
}

/** 못 채운 자리. **`required` 가 앞줄이고 `optional` 이 뒷줄이다.** */
function Missing({ item }: { item: DraftItem }) {
  if (item.missing.length === 0 && item.missing_optional.length === 0) return null;

  const need = item.missing.map((m) => m.place_label).join(" · ");
  const extra = item.missing_optional.map((m) => m.place_label).join(" · ");

  return (
    <p className={styles.missing}>
      {item.missing.length > 0 && (
        <>
          <b>{need}</b>
          {`${josa(need, "이", "가")} 없어서 못 썼어요. `}
        </>
      )}
      {item.missing_optional.length > 0 && (
        <span className={styles.optional}>
          {extra}
          {`${josa(extra, "이", "가")} 있으면 더 쓸 수 있어요.`}
        </span>
      )}
    </p>
  );
}

/** 분량. **`unmeasurable` 은 숫자를 안 만든다**(`draft/limits.py`) —
 * `50페이지 내외` 를 글자로 환산하는 순간 근거 없는 눈금이 생긴다. */
function Length({ item, chars }: { item: DraftItem; chars: number }) {
  const { verdict, limit_text, note } = item.length;
  if (verdict === "none") {
    return (
      <p className={styles.len} data-numeric>
        {chars}자
      </p>
    );
  }
  return (
    <p className={verdict === "over" ? `${styles.len} ${styles.over}` : styles.len}>
      <span data-numeric>{chars}자</span>
      {limit_text && <span className={styles.limit}>{limit_text}</span>}
      {verdict === "unmeasurable" && <span className={styles.limit}>{note}</span>}
    </p>
  );
}

type SaveState = "idle" | "saving" | "saved" | "failed";

/** 항목 하나 — 써진 글 · 근거 · 못 채운 자리 · 저장.
 *
 * **`<li>` 를 그대로 낸다** — 부르는 쪽이 `<ol>`/`<ul>` 을 대야 한다.
 * `DraftView` 와 `DraftThread` 가 같이 쓴다. */
export function DraftItemCard({
  item,
  onSave,
}: {
  item: DraftItem;
  onSave: (itemId: number, text: string | null) => Promise<void>;
}) {
  const server = bodyOf(item);
  const [text, setText] = useState(server);
  const [state, setState] = useState<SaveState>("idle");
  const [why, setWhy] = useState("");
  // 서버가 마지막으로 준 글. **`server` 와 비교해 바뀐 순간을 잡는다**
  const [seen, setSeen] = useState(server);
  const leaf = item.children.length === 0;

  // 서버 값이 바뀌면(저장·되돌리기·재작성) 따라간다. **`useEffect` 가 아니라
  // 렌더 중에 맞춘다** — 효과로 하면 헌 값이 한 번 그려졌다가 바뀌고, 그 사이에
  // 사람이 친 글자가 날아간다. React 가 권하는 「props 가 바뀔 때 state 를
  // 맞추는」 자리가 여기다.
  if (server !== seen) {
    setSeen(server);
    setText(server);
    setState("idle");
  }

  const dirty = text !== server;

  async function save(next: string | null) {
    setState("saving");
    try {
      await onSave(item.document_item_id, next);
      setState("saved");
      setWhy("");
    } catch (e) {
      setState("failed");
      // **무엇이 잘못됐고 어떻게 고치는지 적는다**(DESIGN.md §10). 개발 명령은 안 보인다
      setWhy(e instanceof Error ? e.message : "저장을 못 했어요");
    }
  }

  return (
    <li className={styles.item}>
      <div className={styles.head}>
        {item.number && (
          <span className={styles.number} data-numeric>
            {item.number}
          </span>
        )}
        <span className={styles.title}>{item.title}</span>
        <span className={styles.status}>{STATUS[item.status] ?? item.status}</span>
        {item.edited && <span className={styles.status}>고쳤어요</span>}
      </div>

      {/* 양식이 쓴 "무엇을 쓰라". **우리가 고쳐 쓰지 않는다** */}
      {item.instruction && <p className={styles.instr}>{item.instruction}</p>}

      {/* **"그 얘기는 6번에 썼어요."** 물어볼 자리가 아니다.
          **「번」은 API 가 붙인다** — 칸 서식은 번호가 없어서 제목이 온다 */}
      {item.yielded_to.length > 0 && (
        <p className={styles.yielded}>
          이 내용은 {item.yielded_to.join(" · ")}에 썼어요.
        </p>
      )}

      <Missing item={item} />

      {item.error && <p className={styles.error}>{item.error}</p>}

      {leaf && (
        <div className={styles.write}>
          <textarea
            className={styles.textarea}
            value={text}
            aria-label={`${item.title} 초안`}
            onChange={(e) => setText(e.target.value)}
          />

          <div className={styles.foot}>
            <Length item={item} chars={text.length} />

            <span className={styles.actions}>
              {state === "saving" && <span className={styles.hint}>저장하고 있어요</span>}
              {state === "saved" && !dirty && (
                <span className={styles.hint}>저장했어요</span>
              )}
              {state === "failed" && <span className={styles.fail}>{why}</span>}

              {/* **되돌리기는 지우기다**(ADR-0055 결정 5). 집필기의 글이 안 지워졌으니 된다 */}
              {item.edited && (
                <button
                  type="button"
                  className={styles.ghost}
                  onClick={() => save(null)}
                  disabled={state === "saving"}
                >
                  처음 글로 되돌리기
                </button>
              )}
              <button
                type="button"
                className={styles.save}
                onClick={() => save(text)}
                disabled={!dirty || state === "saving"}
              >
                저장
              </button>
            </span>
          </div>

          {/* **고치면 문단 근거를 안 낸다**(ADR-0055 결정 3). 그 사실을 숨기지 않는다 */}
          {item.evidence_detached ? (
            <p className={styles.detached}>
              고친 뒤라 어느 문장이 어느 근거에서 왔는지 더는 못 짚어요. 되돌리면 다시 보여요.
            </p>
          ) : (
            <Evidence item={item} />
          )}

          {item.edited && item.original && (
            <details className={styles.origBox}>
              <summary className={styles.origSummary}>처음 쓴 글 보기</summary>
              <p className={styles.orig}>{item.original}</p>
            </details>
          )}
        </div>
      )}

      {item.children.length > 0 && (
        <ol className={styles.children}>
          {item.children.map((c) => (
            <DraftItemCard key={c.document_item_id} item={c} onSave={onSave} />
          ))}
        </ol>
      )}
    </li>
  );
}

/** 초안 상태 하나 — 폴링 · 시작 · 저장.
 *
 * **`DraftView` 에서 뽑아 낸 것이고 파일을 안 옮겼다.** 같은 규칙을 두 화면
 * (`DraftView` 와 `DraftThread`)이 써야 하는데, 파일을 가르면 폴링 규칙이
 * 두 벌이 되고 한쪽만 고쳐지는 날이 온다.
 *
 * 표현을 안 갖는다 — 무엇을 그릴지는 부르는 쪽이 정한다. */
export function useDraft({
  initial,
  source,
  externalId,
  company,
}: {
  initial: Draft;
  source: string;
  externalId: string;
  company: string;
}) {
  const [draft, setDraft] = useState(initial);
  const [starting, setStarting] = useState(false);
  const [why, setWhy] = useState("");
  const base = useMemo(
    () =>
      `/api/notices/${encodeURIComponent(source)}/${encodeURIComponent(externalId)}/draft` +
      `?company=${encodeURIComponent(company)}`,
    [source, externalId, company],
  );
  /** **`running` 이 false 가 되면 그만 묻는다.** `/wiki/files` 가 쓰는 규칙과 같다.
   *
   * **`alive` 가 이 안에서 산다.** `useRef` 로 밖에 두면 StrictMode 가 마운트를 두 번
   * 할 때 첫 cleanup 이 `false` 로 만들고 **재마운트가 그것을 되돌리지 않는다** — ref 는
   * 재마운트해도 같은 객체이고 되돌릴 코드가 어디에도 없다. 그러면 첫 폴링의 응답이
   * 버려지고, `draft` 가 안 바뀌니 이 effect 도 다시 안 돌아 **두 번째 폴링이 영영
   * 안 나간다.** 화면은 「지금 쓰고 있어요」에 굳고 새로고침해야 풀린다.
   *
   * 개발 모드에서만 나서 늦게 잡혔다. `Upload.tsx` 가 처음부터 이 모양이었다. */
  useEffect(() => {
    if (!draft.running) return;
    // 폴링 타이머가 언마운트 뒤에도 살면 사라진 화면에 setState 를 한다
    let alive = true;
    const t = setTimeout(async () => {
      try {
        const res = await fetch(base, { cache: "no-store" });
        if (!res.ok) return;
        const next = (await res.json()) as Draft;
        if (alive) setDraft(next);
      } catch {
        // 한 번 못 물어본 것은 실패가 아니다. 다음 차례에 다시 묻는다
      }
    }, 2500);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [draft, base]);

  async function start() {
    setStarting(true);
    setWhy("");
    try {
      const res = await fetch(base, { method: "POST" });
      const out = (await res.json()) as DraftStart & { detail?: string };
      if (!res.ok) throw new Error(out.detail ?? "초안을 못 시작했어요");
      setDraft(out.draft);
      // **거절이 오류가 아니다.** 이미 돌고 있다는 사실을 그대로 말한다
      if (!out.started) setWhy(out.reason);
    } catch (e) {
      setWhy(e instanceof Error ? e.message : "초안을 못 시작했어요");
    } finally {
      setStarting(false);
    }
  }

  const onSave = useCallback(
    async (itemId: number, text: string | null) => {
      const res = await fetch(`${base}`.replace("/draft?", `/draft/items/${itemId}?`), {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const out = (await res.json()) as DraftItem & { detail?: string };
      if (!res.ok) throw new Error(out.detail ?? "저장을 못 했어요");
      // **항목 하나만 갈아 끼운다.** 통째로 다시 받으면 다른 항목에서 쓰던 글이 날아간다
      setDraft((d) => ({ ...d, documents: d.documents.map((doc) => swap(doc, out)) }));
    },
    [base],
  );

  const written = draft.documents.flatMap((d) => leaves(d.items));
  const done = written.filter((i) => bodyOf(i).trim().length > 0).length;

  return { draft, starting, why, start, onSave, written, done };
}

/** 지금까지의 화면. **안 지운다** — 스레드가 실패하면 되돌아갈 자리이고,
 * `useDraft` 가 정말 표현과 갈렸는지 보는 대조군이기도 하다. */
export function DraftView({
  initial,
  source,
  externalId,
  company,
}: {
  initial: Draft;
  source: string;
  externalId: string;
  company: string;
}) {
  const { draft, starting, why, start, onSave, written, done } = useDraft({
    initial,
    source,
    externalId,
    company,
  });

  return (
    <section className={styles.section} aria-labelledby="draft-title">
      <div className={styles.top}>
        <h2 id="draft-title" className={styles.h2}>
          초안
        </h2>

        {draft.documents.length > 0 && (
          /* **막대를 두지 않는다**(§6 이 뺀 적합도 막대와 혼동될 자리를 안 만든다) */
          <p className={styles.count} data-numeric>
            {written.length}개 중 <b>{done}개</b>가 써졌어요
          </p>
        )}
      </div>

      {draft.running ? (
        <p className={styles.running}>
          지금 쓰고 있어요. 항목이 많으면 몇 분 걸려요 — 이 화면을 열어 둬도 돼요.
        </p>
      ) : (
        <div className={styles.startRow}>
          <button
            type="button"
            className={styles.start}
            onClick={start}
            disabled={starting}
          >
            {draft.documents.length > 0 ? "다시 쓰기" : "초안 쓰기"}
          </button>
          <span className={styles.startWhy}>
            {draft.documents.length > 0
              ? "못 쓴 항목만 다시 써요. 내가 고친 글은 그대로 둬요."
              : "위키에 있는 것으로 항목마다 써 드려요."}
          </span>
        </div>
      )}

      {why && <p className={styles.fail}>{why}</p>}

      {draft.documents.length === 0 && !draft.running && (
        <p className={styles.empty}>
          {draft.pending_documents > 0
            ? `글로 쓰는 양식이 ${draft.pending_documents}개 있어요. 위 버튼을 누르면 채워 드려요.`
            : "이 공고에는 글로 쓰는 양식이 아직 안 붙어 있어요. 아래에서 직접 쓸 수 있어요."}
        </p>
      )}

      {draft.documents.map((doc) => (
        <div key={doc.document_id} className={styles.doc}>
          <h3 className={styles.docTitle}>{doc.title}</h3>
          <ol className={styles.items}>
            {doc.items.map((it) => (
              <DraftItemCard key={it.document_item_id} item={it} onSave={onSave} />
            ))}
          </ol>
        </div>
      ))}
    </section>
  );
}

/** 항목 하나를 트리 안에서 갈아 끼운다. **새 객체를 만든다** — 제자리에서 고치면
 * React 가 안 바뀐 줄 안다. */
function swap<T extends { items: DraftItem[] }>(doc: T, next: DraftItem): T {
  return { ...doc, items: doc.items.map((i) => replace(i, next)) };
}

function replace(item: DraftItem, next: DraftItem): DraftItem {
  if (item.document_item_id === next.document_item_id) {
    // **자식은 응답에 안 온다**(`edit_item` 이 항목 하나만 낸다). 들고 있던 것을 쓴다
    return { ...next, children: item.children };
  }
  if (item.children.length === 0) return item;
  return { ...item, children: item.children.map((c) => replace(c, next)) };
}
