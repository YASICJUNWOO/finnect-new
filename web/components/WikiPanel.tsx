"use client";

import { useState } from "react";
import type { Evidence, WikiSpot, WikiStatement, WikiValue } from "@/lib/wiki";
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
 * 상세 상태는 **글자로** 적는다 — 확정·충돌·비어 있음. 그래프가 단색이라(ADR-0052)
 * 여기도 색으로 말할 것이 없다. */
export function WikiPanel({ spot, folderLabel }: { spot: WikiSpot; folderLabel: string }) {
  const [raw, setRaw] = useState(false);

  return (
    <article className={styles.panel} aria-labelledby="node-title">
      <header className={styles.head}>
        <div className={styles.headText}>
          <p className={styles.eyebrow}>
            {folderLabel}
            {/* **접혔으면 원래 경로를 적는다.** 조용히 접으면 트리를 지원한다는 말이 거짓이 된다 */}
            <span className={styles.path}>{spot.collapsed ?? spot.path}</span>
            {spot.eligibility && <span className={styles.tag}>자격 판별에 써요</span>}
          </p>
          <h2 id="node-title" className={styles.title}>
            {spot.title}
          </h2>
          <p className={styles.meta}>
            {spot.filled ? `근거가 된 파일 ${spot.source_count}개` : "아직 비어 있어요"}
            {spot.filled && <span>자료 등급 {spot.grade}</span>}
            {spot.base_date && <span>{spot.base_date} 기준</span>}
            {spot.conflicted && <span className={styles.warn}>값이 갈렸어요</span>}
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
        <pre className={styles.raw}>{spot.markdown}</pre>
      ) : !spot.filled ? (
        /* 5. 빈 화면(§7). **"데이터 없음"으로 끝내지 않는다.**
         * 채울 topic 이 아예 없는 자리와 아직 안 올린 자리는 **다른 말을 한다** */
        <p className={styles.empty}>
          {spot.gap
            ? `이 자리는 아직 안 채워요. ${spot.gap}.`
            : "이 자리를 채우려면 관련된 내용이 담긴 파일을 더 올리면 돼요."}
        </p>
      ) : (
        <>
          {spot.values.length > 0 && <Values values={spot.values} />}
          {spot.grouped ? (
            /* topic 이 둘 이상인 자리. **빈 topic 도 자리를 지키고 무엇이 없는지 말한다** */
            spot.groups.map((g) => (
              <section key={g.topic} className={styles.block}>
                <h3 className={styles.blockTitle}>{g.label}</h3>
                {g.statements.length > 0 ? (
                  <Facts statements={g.statements} />
                ) : (
                  <p className={styles.empty}>아직 없어요.</p>
                )}
              </section>
            ))
          ) : (
            spot.statements.length > 0 && (
              <section className={styles.block}>
                {spot.values.length > 0 && <h3 className={styles.blockTitle}>사업 내용</h3>}
                <Facts statements={spot.statements} />
              </section>
            )
          )}
        </>
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

/** 정형 슬롯. **현재값 · 이전값 · 충돌을 한 눈에 가른다.**
 *
 * 시점이 다르면 성장이고 같으면 모순이다 — 그 판정은 서버가 이미 했고(`status`)
 * 여기는 그 결과를 배치로만 말한다. 이전값을 지우지 않는 것이 F1-1-7 이다. */
function Values({ values }: { values: WikiValue[] }) {
  // (슬롯, 한정어)로 묶는다. 한정어가 다르면 다른 것이다 — 시드와 정책자금
  const groups = new Map<string, WikiValue[]>();
  for (const v of values) {
    const key = `${v.slot}|${v.qualifier ?? ""}`;
    groups.set(key, [...(groups.get(key) ?? []), v]);
  }

  return (
    <section className={styles.block}>
      <dl className={styles.slots}>
        {[...groups.values()].map((items) => {
          const head = items[0];
          const current = items.filter((v) => v.status !== "superseded");
          const history = items.filter((v) => v.status === "superseded");
          const conflicted = current.some((v) => v.status === "conflict");

          return (
            <div key={`${head.slot}|${head.qualifier ?? ""}`} className={styles.slot}>
              <dt className={styles.slotName}>
                {head.label}
                {head.qualifier && <span className={styles.qual}>{head.qualifier}</span>}
              </dt>
              <dd className={styles.slotBody}>
                {conflicted && (
                  <p className={styles.conflict}>
                    값이 갈려요. 어느 쪽이 맞는지 정해야 해요 — 둘 다 두었어요.
                  </p>
                )}
                {current.map((v, i) => (
                  <div key={i} className={styles.value} data-conflict={v.status === "conflict"}>
                    <p className={styles.valueText} data-numeric>
                      {v.display}
                      {v.as_of && <span className={styles.asOf}>{v.as_of} 기준</span>}
                    </p>
                    <Sources evidence={v.evidence} />
                  </div>
                ))}

                {/* 이전 값. **지우지 않는다** — 시계열이지 쓰레기가 아니다 */}
                {history.length > 0 && (
                  <details className={styles.history}>
                    <summary className={styles.historySummary}>
                      이전 값 {history.length}개
                    </summary>
                    <ul className={styles.historyList}>
                      {history
                        .slice()
                        .sort((a, b) => (b.as_of ?? "").localeCompare(a.as_of ?? ""))
                        .map((v, i) => (
                          <li key={i}>
                            <span data-numeric>{v.display}</span>
                            {v.as_of && <span className={styles.asOf}>{v.as_of}</span>}
                            <Sources evidence={v.evidence} quiet />
                          </li>
                        ))}
                    </ul>
                  </details>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
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
