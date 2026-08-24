import {
  countItems,
  type FormDocument,
  type FormItem,
  type NoticeDocuments,
} from "@/lib/documents";
import styles from "./FormDocuments.module.css";

/** 지시문이 이보다 길면 접는다. 실측 최장이 2,031자다 — 펴 두면 화면이 무너진다. */
const LONG = 180;

/** 칸을 한 번에 이만큼만 보여 준다. 실측 최대가 326개다. */
const FIELDS_SHOWN = 20;

/** 항목 하나. 번호 · 이름 · 지시문 · 자식.
 *
 * **지시문은 양식이 쓴 그대로 둔다.** 우리가 해요체로 고쳐 쓰지 않는다 —
 * 섞이면 어디까지가 공고의 요구인지 알 수 없다(DESIGN.md §8, plan/11 T-0039). */
function Item({ item }: { item: FormItem }) {
  const long = (item.instruction?.length ?? 0) > LONG;

  return (
    <li className={styles.item}>
      <div className={styles.itemHead}>
        {item.number && (
          <span className={styles.number} data-numeric>
            {item.number}
          </span>
        )}
        <span className={styles.itemTitle}>{item.title}</span>
        {item.limitText && <span className={styles.limit}>{item.limitText}</span>}
      </div>

      {item.instruction &&
        (long ? (
          <details className={styles.instrBox}>
            {/* summary 를 숨기면 다시 접을 수가 없다. 펼친 뒤엔 글자만 바꾼다 */}
            <summary className={styles.instrSummary}>
              <span className={styles.instrClamp}>{item.instruction}</span>
              <span className={styles.fold}>접기</span>
            </summary>
            <p className={styles.instr}>{item.instruction}</p>
          </details>
        ) : (
          <p className={styles.instr}>{item.instruction}</p>
        ))}

      {item.children.length > 0 && (
        <ol className={styles.children}>
          {item.children.map((c) => (
            <Item key={(c.number ?? "") + c.title} item={c} />
          ))}
        </ol>
      )}
    </li>
  );
}

/** 칸 채우기 문서. **하나씩 펼치지 않는다** — 이름만 늘어놓는다.
 *
 * 실측 중앙값이 66개, 최대 326개다. 펼치면 화면이 소음이 된다(DESIGN.md §8.1-7). */
function Fields({ items }: { items: FormItem[] }) {
  const shown = items.slice(0, FIELDS_SHOWN);
  const rest = items.slice(FIELDS_SHOWN);

  return (
    <>
      <ul className={styles.chips}>
        {shown.map((f) => (
          <li key={f.title} className={styles.chip}>
            {f.title}
          </li>
        ))}
      </ul>
      {rest.length > 0 && (
        <details className={styles.more}>
          <summary className={styles.moreSummary}>
            나머지 <span data-numeric>{rest.length}</span>개 보기
          </summary>
          <ul className={styles.chips}>
            {rest.map((f) => (
              <li key={f.title} className={styles.chip}>
                {f.title}
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

/** 양식 구간 하나. **첨부 파일 행 안에 들어간다**(2026-08-24).
 *
 * 한 첨부에 서식이 여럿 든다 — 실측 224쌍 중 65(29%)가 그렇고 최대 14구간이다.
 * 그래서 파일이 바깥이고 구간이 안이다.
 *
 * **파일명을 여기서 안 적는다.** 바로 위 행이 이미 그것이다 — 적으면 같은 이름이
 * 두 줄 연속으로 선다(§10 «제목이 말한 것을 부제에서 반복하지 않는다»). */
export function FormCard({ doc, open }: { doc: FormDocument; open: boolean }) {
  const n = countItems(doc.items);

  return (
    <details className={styles.doc} open={open}>
      <summary className={styles.docHead}>
        <span className={styles.docTitle}>{doc.title}</span>
        <span className={styles.docMeta} data-numeric>
          {doc.kind === "narrative" ? `항목 ${n}개` : `채울 칸 ${n}개`}
        </span>
      </summary>

      {/* 양식은 갈랐는데 항목이 안 나온 것. **"항목 0개"로 끝내지 않는다**
          (DESIGN.md §7-5). 쓰기 화면(`FormFill`)이 같은 말을 한다. */
      doc.items.length === 0 ? (
        <p className={styles.none}>
          이 양식에서 항목을 못 뽑았어요. 원본 파일을 열어서 확인해 주세요.
        </p>
      ) : doc.kind === "narrative" ? (
        <ol className={styles.items}>
          {doc.items.map((it) => (
            <Item key={(it.number ?? "") + it.title} item={it} />
          ))}
        </ol>
      ) : (
        <Fields items={doc.items} />
      )}
    </details>
  );
}

/** 목록 아래에 붙는 말 둘. **섹션을 안 만든다** — 첨부파일 한 절 안의 각주다.
 *
 * ① 양식을 하나도 못 갈랐을 때. "데이터 없음"으로 끝내지 않는다(DESIGN.md §7-5) —
 *    양식이 없어도 "무슨 서류를 내나"는 공고문에서 나오므로 그것만이라도 넘긴다.
 *    **공고 셋 중 하나가 여기다 — 기본 상태다.**
 * ② 아직 안 갈라 낸 구간 수. **못 본 것을 안 본 척하지 않는다.** 글로 쓰는 양식은
 *    공고문의 절과 생김새가 같아 규칙으로 못 가른다(plan/11 T-0036). */
export function FormNotes({ data }: { data: NoticeDocuments }) {
  const hint = data.documents.length === 0 ? data.submitHint : null;

  return (
    <>
      {data.documents.length === 0 && (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>양식이 첨부에 없어요</p>
          {hint && hint.length > 0 ? (
            <>
              <p className={styles.emptyBody}>공고문에는 이렇게 적혀 있어요.</p>
              <ul className={styles.quotes}>
                {hint.map((h) => (
                  <li key={h} className={styles.quote}>
                    {h}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className={styles.emptyBody}>공고 원문에서 확인해 주세요.</p>
          )}
          {data.notice.url && (
            <a className={styles.cta} href={data.notice.url}>
              공고 원문 보기
            </a>
          )}
        </div>
      )}

      {(data.undecided ?? 0) > 0 && (
        <p className={styles.undecided}>
          아직 못 읽은 붙임이 <span data-numeric>{data.undecided}</span>개 있어요. 지금은 칸을
          채우는 서식만 읽어요.
        </p>
      )}
    </>
  );
}
