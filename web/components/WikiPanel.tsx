"use client";

import { useState } from "react";
import type { Evidence, WikiNode, WikiStatement } from "@/lib/wiki";
import styles from "./WikiPanel.module.css";

/** 자리 한 장(SPEC F1-3). **이 화면의 시그니처는 근거 줄이다.**
 *
 * 값이든 문장이든 바로 아래 `파일명 · N쪽` 이 붙어 있고, 누르면 그 자리에서 원문 조각이
 * 열린다. `SPEC.md` §5.4-3 이 "신뢰가 여기서 생긴다 — 어떤 정보를 근거로 썼는지 열어볼
 * 수 있어야 한다"고 적은 자리이고, `wiki_evidence` 가 있어야만 할 수 있는 것이다.
 *
 * **출처를 툴팁이나 각주로 빼지 않는다.** 빼는 순간 값과 근거가 떨어지고, 떨어지면
 * 아무도 안 연다.
 *
 * **값은 여기 없다.** 트랙이 갈리면서 회사 정보로 나갔다(ADR-0056) — 이 패널은 노드
 * 하나에 앉은 **사실들**을 편다. 상세 상태는 글자로 적고 색으로 말하지 않는다. */
export function WikiPanel({ node, categoryLabel }: { node: WikiNode; categoryLabel: string }) {
  const [raw, setRaw] = useState(false);

  return (
    <article className={styles.panel} aria-labelledby="node-title">
      <header className={styles.head}>
        <div className={styles.headText}>
          <p className={styles.eyebrow}>
            {categoryLabel}
            {/* **경로가 곧 이름이다**(기획 §4-3). 집필 에이전트가 부르는 이름도 이것이다 */}
            <span className={styles.path}>{node.path}</span>
          </p>
          <h2 id="node-title" className={styles.title}>
            {node.name}
          </h2>
          <p className={styles.meta}>
            {node.filled ? `근거가 된 파일 ${node.source_count}개` : "아직 비어 있어요"}
            {node.filled && <span>자료 등급 {node.grade}</span>}
            {node.updated_at && <span>{node.updated_at} 갱신</span>}
          </p>
        </div>

        {/* 원문 마크다운. **저장된 파일이 아니라 매번 만든 것이다** */}
        <button
          type="button"
          className={styles.toggle}
          onClick={() => setRaw((v) => !v)}
          aria-pressed={raw}
        >
          {raw ? "읽기 좋게 보기" : "마크다운으로 보기"}
        </button>
      </header>

      {raw ? (
        <pre className={styles.raw}>{node.markdown}</pre>
      ) : !node.filled ? (
        /* 5. 빈 화면(§7). **"데이터 없음"으로 끝내지 않는다** */
        <p className={styles.empty}>
          이 자리를 채우려면 관련된 내용이 담긴 파일을 더 올리면 돼요.
        </p>
      ) : (
        <Facts statements={node.statements} />
      )}
    </article>
  );
}


/** 서술 사실 목록. 값이든 문장이든 **바로 아래 근거 줄이 붙는다.** */
function Facts({ statements }: { statements: WikiStatement[] }) {
  return (
    <ul className={styles.facts}>
      {statements.map((s, i) => (
        <li key={i} className={styles.fact}>
          <p className={styles.factText}>{s.text}</p>
          <Sources evidence={s.evidence} />
        </li>
      ))}
    </ul>
  );
}

/** 근거 줄. **이 컴포넌트가 화면의 시그니처다.**
 *
 * 접혀 있을 때도 `파일명 · N쪽` 이 그대로 보인다. 펼치면 그 자리에서 원문 조각이 열린다 —
 * 파일을 다시 여는 일이 없어야 한다는 것이 F1-3 의 "출처는 문자열이 아니라 연결이다"다. */
function Sources({ evidence, quiet = false }: { evidence: Evidence[]; quiet?: boolean }) {
  if (evidence.length === 0) {
    // 근거 없는 값은 저장하지 않으므로 여기 오면 안 된다. **와도 조용히 넘어가지 않는다**
    return <p className={styles.noSource}>근거가 없어요</p>;
  }
  return (
    <details className={quiet ? styles.srcQuiet : styles.src}>
      <summary className={styles.srcSummary}>
        <span className={styles.srcCount}>근거 {evidence.length}</span>
        <span className={styles.srcWhere}>
          {evidence.map((e) => `${e.filename}${e.page ? ` ${e.page}쪽` : ""}`).join(" · ")}
        </span>
      </summary>
      <ul className={styles.quotes}>
        {evidence.map((e, i) => (
          <li key={i} className={styles.quote}>
            <p className={styles.quoteWhere}>
              {e.filename}
              {e.page && <span className={styles.page}>{e.page}쪽</span>}
            </p>
            <blockquote className={styles.quoteText}>{e.quote}</blockquote>
          </li>
        ))}
      </ul>
    </details>
  );
}
