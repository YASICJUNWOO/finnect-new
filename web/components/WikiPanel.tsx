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
 * 하나에 앉은 **사실들**을 편다. 상세 상태는 글자로 적고 색으로 말하지 않는다.
 *
 * `onClose` 는 곁에 세울 때만 온다. **그래프를 안 가리므로 닫기가 급하지 않지만**,
 * 고르면 나머지가 흐려지므로 전체로 돌아갈 길이 눈에 보여야 한다. */
export function WikiPanel({
  node,
  categoryLabel,
  onClose,
}: {
  node: WikiNode;
  categoryLabel: string;
  onClose?: () => void;
}) {
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

        <div className={styles.acts}>
          {/* 원문 마크다운. **저장된 파일이 아니라 매번 만든 것이다** */}
          <button
            type="button"
            className={styles.toggle}
            onClick={() => setRaw((v) => !v)}
            aria-pressed={raw}
          >
            {raw ? "읽기 좋게" : "마크다운"}
          </button>

          {onClose && (
            <button type="button" className={styles.close} onClick={onClose} aria-label="닫기">
              닫기
            </button>
          )}
        </div>
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


/** 사실 목록. **사실마다 이름(`key`)이 먼저 서고 그 아래 근거 줄이 붙는다.**
 *
 * 2026-08-22 까지 이 목록이 `text` 만 뿌렸다. 한 자리에 사실이 셋이면 **이름 없는 문단
 * 셋**이 되어서, 위에서 「같은 key 면 같은 사실」로 묶어 놓은 것을 화면에서 확인할 방법이
 * 없었다. 사용자가 찾는 것은 문장이 아니라 「직원 수가 어디 있나」다.
 *
 * **key 로 묶지 않는다.** 값이 갈린 자리는 같은 이름이 값 둘로 나란히 서야 하고, 그것이
 * 충돌의 표현이다 — 접으면 값 하나가 조용히 사라진다(`wiki/markdown.py` `render_facts`). */
function Facts({ statements }: { statements: WikiStatement[] }) {
  return (
    <ul className={styles.facts}>
      {statements.map((s, i) => (
        <li key={i} className={styles.fact}>
          <p className={styles.factKey}>
            <span className={styles.keyName}>{s.key}</span>
            {s.qualifier && <span className={styles.qual}>{s.qualifier}</span>}
            {/* **단위를 안 붙인다.** 트랙 A 의 key 는 자유 문자열이라 아는 단위가 없다 */}
            {s.value && <span className={styles.factValue}>{s.value}</span>}
            {s.as_of && <span className={styles.asOf}>{s.as_of} 기준</span>}
          </p>
          {s.text && <p className={styles.factText}>{s.text}</p>}
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
