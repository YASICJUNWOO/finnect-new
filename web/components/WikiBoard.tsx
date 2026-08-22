"use client";

import { useState } from "react";
import Link from "next/link";
import { Orbit } from "./Orbit";
import { WikiPanel } from "./WikiPanel";
import type { Wiki } from "@/lib/wiki";
import styles from "./WikiBoard.module.css";

/** S7 내 사업 위키. 탭 둘과 방사형 아래 패널 하나다.
 *
 * **SPEC §5.3 은 탭 셋을 적었다.** 변경 이력을 안 만들었다 — `wiki_fact` 에 `first_seen_at`
 * 이 있긴 하지만 **한 번에 다 넣은 값이라 전부 같은 시각이다.** 이력처럼 생긴 빈 화면을
 * 만드는 것보다 없는 편이 정직하다. 파일을 나눠 올리기 시작하면 그때 뜻이 생긴다.
 *
 * **패널을 그래프 위에 겹치지 않고 아래에 편다.** SPEC 은 "겹쳐 뜬다"고 적었는데 그 문장의
 * 뜻은 별도 탭으로 빼지 말라는 것이고(§5.3), 근거를 펼치면 길어지는 패널을 720px 그래프
 * 위에 겹치면 그래프가 통째로 가려 위치를 확인할 수 없다. 고른 자리는 그래프에 링으로 남는다. */
export function WikiBoard({
  wiki,
  initial,
  company,
}: {
  wiki: Wiki;
  initial?: string | null;
  company?: string;
}) {
  const [tab, setTab] = useState<"orbit" | "files">("orbit");
  const [picked, setPicked] = useState<string | null>(
    wiki.nodes.some((n) => n.path === initial) ? (initial as string) : null,
  );

  /** 고른 자리를 주소에 남긴다. **딥링크가 되고 새로고침해도 살아 있다.**
   *
   * `router.replace` 를 쓰지 않는다 — 서버를 한 번 더 다녀오는데 위키는 이미 다 받아 뒀다.
   * `history.replaceState` 로 주소만 갈면 뒤로 가기도 목록으로 바로 돌아간다. */
  function pick(path: string | null) {
    setPicked(path);
    const url = new URL(window.location.href);
    // **자리의 이름이 경로다**(기획 §4-3). 주소에도 그 경로가 그대로 들어간다
    if (path) url.searchParams.set("spot", path);
    else url.searchParams.delete("spot");
    window.history.replaceState(null, "", url);
  }

  const node = wiki.nodes.find((n) => n.path === picked) ?? null;
  const empty = wiki.filled === 0;
  const upload = company ? `/wiki/files?company=${encodeURIComponent(company)}` : "/wiki/files";

  return (
    <>
      <div className={styles.tabs} role="tablist" aria-label="보기">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "orbit"}
          className={styles.tab}
          onClick={() => setTab("orbit")}
        >
          자리
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "files"}
          className={styles.tab}
          onClick={() => setTab("files")}
        >
          원본 파일
          <span className={styles.tabN} data-numeric>
            {wiki.files.length}
          </span>
        </button>

        {/* **아직 아무것도 없으면 안 보여 준다.** 눌러 봐야 없는 화면이 뜬다 —
          * 갈 곳 없는 문을 두지 않는다.
          *
          * 절대 경로다. `./wiki/markdown` 은 `/wiki` 에서 우연히 맞을 뿐,
          * 주소 끝에 슬래시가 붙으면 `/wiki/wiki/markdown` 으로 샌다 */}
        {wiki.filled > 0 && (
          <Link
            href={company ? `/wiki/markdown?company=${encodeURIComponent(company)}` : "/wiki/markdown"}
            className={styles.md}
          >
            마크다운 전체
          </Link>
        )}
      </div>

      {tab === "orbit" ? (
        <section className={styles.stage} aria-label="자리">
          {empty && (
            /* 5. 빈 화면(§7). **자리를 지우지 않는다** — 무엇이 없는지 보여야 한다 */
            <p className={styles.hole}>
              아직 위키가 없어요. 파일을 올리면 카테고리 아래로 자리가 자라요.
              <span className={styles.holeSub}>
                <Link href={upload}>파일 올리러 가기</Link>
              </span>
            </p>
          )}

          <Orbit
            nodes={wiki.nodes}
            categories={wiki.categories}
            filled={wiki.filled}
            total={wiki.total}
            selected={picked}
            onSelect={(p) => pick(picked === p ? null : p)}
          />

          {/* 범례. **색이 없으므로 모양이 무엇을 뜻하는지 말한다** */}
          <ul className={styles.legend}>
            <li data-mark="filled">찼어요</li>
            <li data-mark="empty">아직 비었어요</li>
          </ul>

          {node ? (
            <div className={styles.panelWrap}>
              <WikiPanel node={node} categoryLabel={wiki.categories[node.category] ?? node.category} />
            </div>
          ) : (
            <p className={styles.hint}>자리를 누르면 무엇이 들어 있는지, 어디서 왔는지 열려요.</p>
          )}
        </section>
      ) : (
        <Files
          wiki={wiki}
          upload={upload}
          onPick={(k) => {
            pick(k);
            setTab("orbit");
          }}
        />
      )}
    </>
  );
}

/** 원본 파일(F1-4-7). **어느 파일을 지우면 무엇이 사라지는지** 보이는 자리다.
 *
 * 읽히지 않은 파일도 그대로 둔다 — 실패를 안 보여 주면 사용자는 올린 줄 안다. */
function Files({
  wiki,
  upload,
  onPick,
}: {
  wiki: Wiki;
  upload: string;
  onPick: (key: string) => void;
}) {
  if (wiki.files.length === 0) {
    return (
      <p className={styles.hole}>
        아직 올린 파일이 없어요.
        <span className={styles.holeSub}>
          <Link href={upload}>파일 올리러 가기</Link>
        </span>
      </p>
    );
  }

  const label = (path: string) => wiki.nodes.find((n) => n.path === path)?.name ?? path;

  return (
    <ul className={styles.files}>
      {wiki.files.map((f) => (
        <li key={f.filename} className={styles.file} data-ok={f.spots.length > 0}>
          <p className={styles.fileName}>{f.filename}</p>
          <p className={styles.fileMeta}>
            {f.parser ?? "안 읽혔어요"}
            {f.chunk_count ? <span data-numeric>조각 {f.chunk_count}개</span> : null}
            {f.page_count ? <span data-numeric>{f.page_count}쪽</span> : null}
          </p>

          {f.spots.length > 0 ? (
            <p className={styles.made}>
              {f.spots.map((path) => (
                <button
                  key={path}
                  type="button"
                  className={styles.chip}
                  onClick={() => onPick(path)}
                >
                  {label(path)}
                </button>
              ))}
            </p>
          ) : (
            /* **왜 아무것도 안 나왔는지 적는다.** 조용히 비워 두지 않는다 */
            <p className={styles.fileWhy}>
              {f.parse_error ?? (f.parse_status === "empty" ? "글자가 안 나왔어요" : null) ??
                "아직 사실을 못 뽑았어요"}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
