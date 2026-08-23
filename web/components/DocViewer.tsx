"use client";

import { useEffect, useRef, useState } from "react";
import { attachmentFileUrl } from "@/lib/api";
import { canPreview, type FormDocument } from "@/lib/documents";
import { DocxView } from "./DocxView";
import styles from "./DocViewer.module.css";

/** 양식 뷰어 — **원본 파일을 그대로 띄운다.**
 *
 * 우리가 뽑은 항목 트리를 다시 그리는 것이 아니라 `.hwp`·`.hwpx`·`.pdf`·`.docx`
 * 원본을 [rhwp](https://github.com/edwardkim/rhwp)(Rust + WASM · MIT)에 넣는다.
 * 서버 변환이 없다 — 브라우저가 직접 판다.
 *
 * **왜 rhwp 인가.** 2026-08-22 에 재 보고 골랐다.
 * - LibreOffice: HWP 5.x 를 못 연다(`source file could not be loaded`). 한글 필터가 HWP 97 까지다
 * - pyhwp: hwp 는 되는데 **hwpx 를 못 연다**(`Not an OLE2`)
 * - rhwp: **hwp·hwpx 둘 다** 되고 `exportHwp()` 로 되돌리기까지 된다
 *
 * **원본 URL 로 안 보낸다.** 다른 출처라 CORS 에 막히고, 그 URL 은 브라우저
 * UA·Referer 를 요구하며 오류를 HTTP 200 + HTML 로 준다(CLAUDE.md 함정) —
 * 오류 페이지가 hwp 로 둔갑해 뷰어에 들어간다. `/api/attachments/{sha}/file` 이
 * 디스크에 있는 바이트를 그대로 준다.
 *
 * **여는 단위가 파일이지 서류가 아니다.** 한 첨부에 `[서식1]`·`[붙임2]` 가 여럿
 * 들어 있고 우리는 그것을 구간으로 갈라 놨는데, 그 경계는 **글자 오프셋**이라
 * 페이지로 옮길 방법이 없다. 그래서 파일 전체가 열린다 — 머리줄이 그 사실을 말한다.
 *
 * **머리줄을 여기서 안 그린다.** rhwp 는 자체 메뉴 여덟 + 리본을 가진 에디터
 * 전체다. 그 위에 우리 크롬을 겹쳐 쌓으면 어디까지가 우리 것인지 안 보인다 —
 * 쪽수와 칩은 `onPages` 로 올려 보내고 부르는 쪽이 그린다. */

/** 상태 넷. **「비었다」와 「못 열었다」를 가른다** — 저쪽은 열 것이 없는 것이고
 * 이쪽은 열려다 실패한 것이라 사용자가 할 일이 다르다. */
type Phase =
  | { at: "여는 중" }
  | { at: "열렸다"; pages: number }
  | { at: "못 열었다"; why: string };

export function DocViewer({
  doc,
  noticeUrl,
  onPages,
  filledUrl,
  onFilled,
}: {
  /** `null` 이면 열 것이 없다 */
  doc: FormDocument | null;
  noticeUrl: string | null;
  onPages?: (pages: number | null) => void;
  /** 초안을 넣어 채운 파일의 주소 (plan/24 T-0155). **없으면 원본을 연다.**
   *
   * 있어도 실패하면 원본으로 물러난다 — 채우기가 안 되는 것과 문서를 못 여는
   * 것은 다르고, 뒤엣것으로 앞엣것을 덮으면 사용자가 양식 자체를 못 본다. */
  filledUrl?: string | null;
  /** 몇 칸을 채웠고 몇 칸이 남았나. **헤더로 온다** */
  onFilled?: (filled: number, left: number) => void;
}) {
  const mountRef = useRef<HTMLDivElement>(null);
  // rhwp 핸들. 타입이 커서 쓰는 것만 좁혀 든다
  const editorRef = useRef<{
    destroy: () => void;
    loadFile: (
      data: ArrayBuffer,
      fileName?: string,
      options?: { skipUnsavedGuard?: boolean },
    ) => Promise<{ pageCount: number }>;
  } | null>(null);
  const [phase, setPhase] = useState<Phase>({ at: "여는 중" });

  // **docx 는 rhwp 를 안 태운다.** 여기서 빼지 않으면 아래 분기가 `DocxView` 를
  // 그리기 전에 effect 가 먼저 돌아 8.3MB WASM 을 받고 실패한다.
  const isDocx = doc?.ext === "docx";
  const sha = doc && canPreview(doc) && !isDocx ? doc.sha256 : null;
  const filename = doc?.attachment.filename ?? "";

  // 문서가 바뀌면 상태를 되돌린다. **`useEffect` 가 아니라 렌더 중에 맞춘다** —
  // 효과로 하면 지난 문서의 「못 열었어요」가 한 프레임 스쳐 지나간다.
  // React 가 권하는 「props 가 바뀔 때 state 를 맞추는」 자리가 여기이고,
  // `DraftItemCard` 가 이미 같은 규칙을 쓴다.
  const [shownFor, setShownFor] = useState(sha);
  if (sha !== shownFor) {
    setShownFor(sha);
    setPhase({ at: "여는 중" });
  }

  // 쪽수를 올려 보내는 것을 effect 밖으로 뺀다. 부르는 쪽이 매 렌더 새 함수를
  // 넘겨도 문서를 다시 열지 않게 하려는 것이다.
  const pagesRef = useRef(onPages);
  useEffect(() => {
    pagesRef.current = onPages;
  }, [onPages]);

  // 같은 이유로 밖에 뺀다. 부르는 쪽이 매 렌더 새 함수를 넘겨도 문서를 다시 안 연다
  const filledRef = useRef(onFilled);
  useEffect(() => {
    filledRef.current = onFilled;
  }, [onFilled]);

  useEffect(() => {
    if (!sha) return;
    pagesRef.current?.(null);

    // **취소 깃발이 필요하다.** 8.3MB WASM 을 받는 동안 사용자가 떠날 수 있고,
    // 그때 늦게 도착한 응답이 이미 없어진 DOM 에 붙으면 조용히 터진다.
    let dead = false;

    (async () => {
      try {
        const mount = mountRef.current;
        if (!mount) return;

        // **에디터가 있으면 다시 만들지 않는다.** 문서를 바꿀 때마다 destroy →
        // createEditor 를 돌면 iframe 과 8.3MB WASM 을 매번 새로 받는다.
        // 모달일 때는 열 때마다 새로 만드는 것이 맞았지만 단으로 오면서 틀려졌다.
        if (!editorRef.current) {
          const { createEditor } = await import("@rhwp/editor");
          if (dead) return;
          const made = await createEditor(mount);
          if (dead) {
            made.destroy();
            return;
          }
          editorRef.current = made;
        }

        // **채운 파일을 먼저 시도한다.** 초안이 들어간 양식이 이 화면의 요점이다.
        // 실패해도 원본은 떠야 한다 — 채우기가 안 되는 것(포맷·좌표 없음)과 문서를
        // 못 여는 것은 다르고, 뒤엣것으로 앞엣것을 덮으면 양식 자체를 못 본다.
        let res: Response | null = null;
        if (filledUrl) {
          try {
            const tried = await fetch(filledUrl);
            if (tried.ok) {
              res = tried;
              filledRef.current?.(
                Number(tried.headers.get("x-finnect-filled") ?? 0),
                Number(tried.headers.get("x-finnect-left") ?? 0),
              );
            }
          } catch {
            // 원본으로 물러난다. 여기서 던지면 양식이 아예 안 뜬다
          }
        }
        if (!res) {
          res = await fetch(attachmentFileUrl(sha));
          if (!res.ok) throw new Error(await reasonOf(res));
        }
        const buf = await res.arrayBuffer();
        if (dead) return;

        // **`skipUnsavedGuard` 를 준다.** 안 주면 문서를 갈아 끼울 때 rhwp 가
        // 「저장 안 한 변경이 있다」 안내창을 띄우고 거기서 멈춘다.
        const { pageCount } = await editorRef.current.loadFile(buf, filename, {
          skipUnsavedGuard: true,
        });
        if (dead) return;
        setPhase({ at: "열렸다", pages: pageCount });
        pagesRef.current?.(pageCount);
      } catch (e) {
        if (dead) return;
        setPhase({ at: "못 열었다", why: e instanceof Error ? e.message : String(e) });
        pagesRef.current?.(null);
      }
    })();

    return () => {
      dead = true;
    };
    // **`filledUrl` 이 의존성에 든다.** 초안을 다시 쓰면 주소는 같아도 내용이
    // 달라지는데, 그건 부르는 쪽이 주소를 갈아 끼워 알린다(`?v=` 를 붙인다).
  }, [sha, filename, filledUrl]);

  // 화면을 떠날 때만 정리한다. **문서를 바꿀 때는 안 부순다**(위 주석 참조).
  useEffect(
    () => () => {
      editorRef.current?.destroy();
      editorRef.current = null;
    },
    [],
  );

  // 열 것이 아예 없다
  if (!doc) {
    return (
      <Notice
        title="이 공고에는 열어 볼 수 있는 양식이 없어요"
        body="양식 파일이 첨부에 없거나, 화면에서 못 여는 형식이에요."
        href={noticeUrl}
        cta="공고 원문 보기"
      />
    );
  }

  // **「못 열었다」와 가른다.** 저쪽은 시도했다 실패한 것이고 이쪽은 애초에 못 여는
  // 것이다 — 다시 눌러 볼 일이 없다는 뜻이 다르다.
  if (!canPreview(doc)) {
    return (
      <Notice
        title="이 형식은 화면에서 못 열어요"
        body="hwp · hwpx · pdf · docx 만 열 수 있어요."
        href={doc.attachment.url}
        cta="원본 파일 내려받기"
        filename={doc.attachment.filename}
      />
    );
  }

  // **포맷마다 뷰어가 다르다.** rhwp 는 한글 문서 뷰어라 docx 를 ZIP 으로 열고
  // hwpx 구조를 기대하다 실패한다(`필수 파일 누락: Contents/content.hpf`).
  // 화면은 오래 「docx 도 열 수 있어요」라고 말했지만 **한 번도 안 열렸다.**
  //
  // 이 자리가 지금 중요해진 이유는 **docx 가 채워지는 포맷**이라서다 — hwp 는
  // 안내문이 든 칸을 못 덮어써서(ADR-0060 결정 3) 값이 몇 칸 안 들어간다.
  if (isDocx) {
    return (
      <DocxView
        url={filledUrl ?? attachmentFileUrl(doc.sha256)}
        filename={doc.attachment.filename}
        downloadUrl={doc.attachment.url}
        onFilled={onFilled}
      />
    );
  }

  return (
    <div className={styles.stage}>
      {/* rhwp 가 여기에 iframe 을 심는다. **언마운트하지 않는다** —
          조건부로 그리면 `createEditor` 가 붙을 자리가 그때 없다 */}
      <div ref={mountRef} className={styles.mount} data-busy={phase.at !== "열렸다"} />

      {phase.at === "여는 중" && (
        <p className={styles.status}>문서를 여는 중이에요. 처음 열 때는 조금 걸려요.</p>
      )}

      {phase.at === "못 열었다" && (
        <Notice
          title="이 문서를 못 열었어요"
          body={phase.why}
          href={doc.attachment.url}
          cta="원본 파일 내려받기"
          filename={doc.attachment.filename}
          overlay
        />
      )}
    </div>
  );
}

/** 무대 대신 서는 글. **「데이터 없음」으로 끝내지 않는다**(DESIGN.md §7-5) —
 * 무엇이 없고 다음에 무엇을 할 수 있는지 적는다. */
function Notice({
  title,
  body,
  href,
  cta,
  filename,
  overlay,
}: {
  title: string;
  body: string;
  href: string | null;
  cta: string;
  filename?: string;
  overlay?: boolean;
}) {
  return (
    <div className={overlay ? `${styles.notice} ${styles.overlay}` : styles.notice}>
      <p className={styles.noticeTitle}>{title}</p>
      <p className={styles.noticeBody}>{body}</p>
      {/* 파일명은 여기서 처음 나온다 — 내려받으려면 무슨 파일인지 알아야 한다 */}
      {filename && <p className={styles.filename}>{filename}</p>}
      {href && (
        <a className={styles.cta} href={href}>
          {cta}
        </a>
      )}
    </div>
  );
}

/** 서버가 적은 이유를 그대로 올린다. **「HTTP 404」보다 「아직 안 받아 둔 첨부예요」**
 * 가 화면에서 할 말이 많다. */
async function reasonOf(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail) return body.detail;
  } catch {
    // JSON 이 아니면 상태 코드로 말한다
  }
  return `원본을 못 받았어요 (${res.status})`;
}
