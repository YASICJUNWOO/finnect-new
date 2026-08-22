"use client";

import Link from "next/link";
import type { Evidence, Profile, ProfileKey, WikiValue } from "@/lib/wiki";
import styles from "./CompanyTable.module.css";

/** 회사 정보 열넷(트랙 B · ADR-0056 결정 5).
 *
 * **빈 칸이 물어볼 자리다**(ADR-0028). 질문이 고정이라 못 채운 것을 셀 수 있고, 셀 수
 * 있어서 물어볼 수 있다 — 위키 그래프는 정답지가 없어 이걸 못 한다.
 *
 * **크롬 없는 조밀한 목록이다**(DESIGN.md §4 «목록»). 카드 격자로 만들지 않는다.
 *
 * 시점이 다르고 값이 다르면 **시계열**이라 최신을 위에 쓰고 나머지를 접는다. 시점이
 * 같은데 값이 다르면 **충돌**이라 둘 다 편다 — 지우면 어느 쪽이 맞는지 물을 수 없다. */
export function CompanyTable({ profile, upload }: { profile: Profile; upload: string }) {
  if (profile.filled === 0) {
    /* 5. 빈 화면(§7). **"데이터 없음"으로 끝내지 않는다** */
    return (
      <p className={styles.hole}>
        아직 아무것도 몰라요. 사업자등록증이나 사업계획서를 올리면 이 {profile.total}칸이 차요.
        <span className={styles.holeSub}>
          <Link href={upload}>파일 올리러 가기</Link>
        </span>
      </p>
    );
  }

  return (
    <dl className={styles.table}>
      {profile.keys.map((k) => (
        <Row key={k.key} item={k} />
      ))}
    </dl>
  );
}

function Row({ item }: { item: ProfileKey }) {
  return (
    <div className={styles.row} data-empty={item.current.length === 0}>
      <dt className={styles.name}>
        {item.label}
        {/* **자격 판별에 쓰는 칸.** 비면 그만큼 공고를 못 거른다 */}
        {item.eligibility && <span className={styles.tag}>공고 거를 때 써요</span>}
      </dt>
      <dd className={styles.body}>
        {item.current.length === 0 ? (
          <p className={styles.unknown}>아직 몰라요</p>
        ) : (
          <>
            {item.conflicted && (
              <p className={styles.conflict}>
                값이 갈려요. 어느 쪽이 맞는지 정해야 해요 — 둘 다 두었어요.
              </p>
            )}
            {item.current.map((v, i) => (
              <Value key={i} v={v} conflicted={v.status === "conflict"} />
            ))}

            {/* 이전 값. **지우지 않는다** — 시계열이지 쓰레기가 아니다(F1-1-7) */}
            {item.history.length > 0 && (
              <details className={styles.history}>
                <summary className={styles.historySummary}>
                  이전 값 {item.history.length}개
                </summary>
                <ul className={styles.historyList}>
                  {item.history
                    .slice()
                    .sort((a, b) => (b.as_of ?? "").localeCompare(a.as_of ?? ""))
                    .map((v, i) => (
                      <li key={i}>
                        <span data-numeric>{v.display}</span>
                        {v.qualifier && <span className={styles.qual}>{v.qualifier}</span>}
                        {v.as_of && <span className={styles.asOf}>{v.as_of}</span>}
                      </li>
                    ))}
                </ul>
              </details>
            )}
          </>
        )}
      </dd>
    </div>
  );
}

function Value({ v, conflicted }: { v: WikiValue; conflicted: boolean }) {
  return (
    <div className={styles.value} data-conflict={conflicted}>
      <p className={styles.valueText} data-numeric>
        {v.display}
        {v.qualifier && <span className={styles.qual}>{v.qualifier}</span>}
        {v.as_of && <span className={styles.asOf}>{v.as_of} 기준</span>}
      </p>
      <Sources evidence={v.evidence} />
    </div>
  );
}

/** 근거 줄. **값 바로 아래 붙는다**(SPEC F1-3).
 *
 * 툴팁이나 각주로 빼지 않는다 — 빼는 순간 값과 근거가 떨어지고, 떨어지면 아무도 안 연다. */
function Sources({ evidence }: { evidence: Evidence[] }) {
  if (evidence.length === 0) {
    // 근거 없는 값은 저장하지 않으므로 여기 오면 안 된다. **와도 조용히 넘어가지 않는다**
    return <p className={styles.noSource}>근거가 없어요</p>;
  }
  return (
    <details className={styles.src}>
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
