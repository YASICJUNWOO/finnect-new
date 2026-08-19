"use client";

import { useMemo, useState } from "react";
import type { FormDocument, FormItem, NoticeDocuments } from "@/lib/documents";
import styles from "./FormFill.module.css";

/** 신청서를 쓰는 화면(SPEC §5.2 S4 · F6).
 *
 * **아직 초안이 없다.** F6-1 이 "진입하면 이미 써져 있다" 지만 집필기가 0줄이고
 * LLM 제공자도 안 골랐다. 그래서 이 화면은 F6 중 **양식이 있어야만 되는 것들**만
 * 먼저 세운다 — 항목 구조(F6-3) · 작성 지침(F6-4) · 완성도(F6-5) · 직접 수정(F6-10).
 *
 * 나머지(F6-1·2·7·8·9·13)는 **비어 있다고 말하고 비워 둔다.** 예시 초안을 넣으면
 * 지어낸 글이 진짜 초안처럼 보인다.
 *
 * 입력값은 **이 화면에서만 산다.** 저장 모델(`draft` 계열)이 아직 없고,
 * 화면 모양이 정해지기 전에 스키마를 정하면 스키마를 다시 고치게 된다 —
 * `lib/fixtures/documents.ts` 가 T-0039 에서 한 것과 같은 순서다. */

/** 지시문이 이보다 길면 접는다. 실측 최장이 2,031자다. */
const LONG = 180;

/** 칸을 한 번에 이만큼만 보여 준다. 실측 최대가 199개다. */
const FIELDS_SHOWN = 20;

type Answers = Record<string, string>;

/** 항목의 자리를 키로 쓴다. **제목을 키로 쓰지 않는다** — 같은 이름의 칸이
 * 한 양식에 여러 번 나온다(`구분` 711회 · `합계` 169회). */
function keyOf(docId: string, path: number[]): string {
  return `${docId}::${path.join(".")}`;
}

/** `id`·`for` 로 쓸 수 있게 다듬는다. 키 자체는 그대로 둔다. */
function idOf(key: string): string {
  return key.replace(/[^a-zA-Z0-9_-]/g, "-");
}

/** 쓸 자리는 **잎**이다. 가지는 양식의 묶음이라 쓰는 칸이 아니다 —
 * `2 추진배경 및 목표` 아래 `2-1`·`2-2`·`2-3` 이 있으면 쓰는 건 셋뿐이다. */
function leafKeys(items: FormItem[], docId: string, path: number[] = []): string[] {
  return items.flatMap((it, i) => {
    const p = [...path, i];
    return it.children.length > 0 ? leafKeys(it.children, docId, p) : [keyOf(docId, p)];
  });
}

function written(keys: string[], answers: Answers): number {
  return keys.filter((k) => (answers[k] ?? "").trim().length > 0).length;
}

/** F6-5 완성도. **막대를 두지 않는다** — 숫자가 이미 셀 수 있는 값이라
 * 막대가 더 말해 주는 것이 없다. §6 이 뺀 적합도 막대와 혼동될 자리도 안 만든다.
 *
 * "N개 비어 있어요" 를 붙이지 않는다. `총 − 쓴 것` 이라 같은 값을 두 번 말하는 것이고,
 * 처음 들어오면 전부 비어 있어 액센트가 화면을 덮는다(§8.2 의 10%).
 * **F6-6 이 가리켜야 할 "위키가 비어서 못 쓴 자리" 는 초안이 있어야 생긴다** —
 * 지금 빈 것은 아무도 안 썼기 때문이지 위키가 비어서가 아니다. 둘을 섞지 않는다. */
function Progress({ done, total }: { done: number; total: number }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <p className={styles.progress}>
      <span data-numeric>{total}</span>개 중 <span data-numeric>{done}</span>개 썼어요{" "}
      <span className={styles.pct} data-numeric>
        {pct}%
      </span>
    </p>
  );
}

/** 양식이 쓴 "무엇을 쓰라". **우리가 고쳐 쓰지 않는다**(DESIGN.md §8). */
function Instruction({ id, text }: { id: string; text: string }) {
  if (text.length <= LONG) {
    return (
      <p id={id} className={styles.instr}>
        {text}
      </p>
    );
  }

  return (
    <details className={styles.instrBox}>
      {/* summary 를 숨기면 다시 접을 수가 없다. 펼친 뒤엔 글자만 바꾼다 */}
      <summary className={styles.instrSummary}>
        <span className={styles.instrClamp}>{text}</span>
        <span className={styles.fold}>접기</span>
      </summary>
      <p id={id} className={styles.instr}>
        {text}
      </p>
    </details>
  );
}

/** 글로 쓰는 항목 하나. 잎이면 쓰는 칸이 붙고, 가지면 자식만 붙는다. */
function Item({
  item,
  docId,
  path,
  answers,
  onChange,
}: {
  item: FormItem;
  docId: string;
  path: number[];
  answers: Answers;
  onChange: (key: string, value: string) => void;
}) {
  const key = keyOf(docId, path);
  const id = idOf(key);
  const leaf = item.children.length === 0;
  const instrId = item.instruction ? `${id}-instr` : undefined;
  const value = answers[key] ?? "";

  return (
    <li className={styles.item}>
      <div className={styles.itemHead}>
        {item.number && (
          <span className={styles.number} data-numeric>
            {item.number}
          </span>
        )}
        {leaf ? (
          <label className={styles.itemTitle} htmlFor={id}>
            {item.title}
          </label>
        ) : (
          <span className={styles.itemTitle}>{item.title}</span>
        )}
        {/* 양식이 준 분량 제한. 실측 0건이라 아직 아무 데도 안 뜬다 */}
        {item.limitText && <span className={styles.limit}>{item.limitText}</span>}
      </div>

      {item.instruction && instrId && <Instruction id={instrId} text={item.instruction} />}

      {leaf && (
        <div className={styles.write}>
          <textarea
            id={id}
            className={styles.textarea}
            value={value}
            aria-describedby={instrId}
            onChange={(e) => onChange(key, e.target.value)}
          />
          {/* F6-14 분량 관리. 양식이 제한을 안 줬으니 **쓴 만큼만** 말한다 */}
          <p className={styles.chars} data-numeric>
            {value.length}자
          </p>
        </div>
      )}

      {item.children.length > 0 && (
        <ol className={styles.children}>
          {item.children.map((c, i) => (
            <Item
              key={keyOf(docId, [...path, i])}
              item={c}
              docId={docId}
              path={[...path, i]}
              answers={answers}
              onChange={onChange}
            />
          ))}
        </ol>
      )}
    </li>
  );
}

/** 칸 채우기 항목 하나. 한 줄짜리라 textarea 를 쓰지 않는다. */
function Field({
  item,
  docId,
  index,
  answers,
  onChange,
}: {
  item: FormItem;
  docId: string;
  index: number;
  answers: Answers;
  onChange: (key: string, value: string) => void;
}) {
  const key = keyOf(docId, [index]);
  const id = idOf(key);

  return (
    <div className={styles.cell}>
      <label className={styles.cellLabel} htmlFor={id}>
        {item.title}
      </label>
      <input
        id={id}
        className={styles.input}
        type="text"
        value={answers[key] ?? ""}
        onChange={(e) => onChange(key, e.target.value)}
      />
    </div>
  );
}

/** 칸 채우기 문서. 실측 최대가 199개라 한 번에 다 펴지 않는다. */
function Fields({
  doc,
  answers,
  onChange,
}: {
  doc: FormDocument;
  answers: Answers;
  onChange: (key: string, value: string) => void;
}) {
  const rest = doc.items.slice(FIELDS_SHOWN);

  return (
    <>
      <div className={styles.grid}>
        {doc.items.slice(0, FIELDS_SHOWN).map((f, i) => (
          <Field
            key={keyOf(doc.id, [i])}
            item={f}
            docId={doc.id}
            index={i}
            answers={answers}
            onChange={onChange}
          />
        ))}
      </div>

      {rest.length > 0 && (
        <details className={styles.more}>
          <summary className={styles.moreSummary}>
            나머지 <span data-numeric>{rest.length}</span>개 쓰기
          </summary>
          <div className={styles.grid}>
            {rest.map((f, i) => (
              <Field
                key={keyOf(doc.id, [FIELDS_SHOWN + i])}
                item={f}
                docId={doc.id}
                index={FIELDS_SHOWN + i}
                answers={answers}
                onChange={onChange}
              />
            ))}
          </div>
        </details>
      )}
    </>
  );
}

function Doc({
  doc,
  open,
  answers,
  onChange,
}: {
  doc: FormDocument;
  open: boolean;
  answers: Answers;
  onChange: (key: string, value: string) => void;
}) {
  const keys = useMemo(() => leafKeys(doc.items, doc.id), [doc]);
  const done = written(keys, answers);

  return (
    <details className={styles.doc} open={open}>
      <summary className={styles.docHead}>
        <span className={styles.docTitle}>{doc.title}</span>
        <span className={styles.docMeta} data-numeric>
          {done} / {keys.length}
        </span>
      </summary>

      {doc.attachment.url && (
        <p className={styles.source}>
          <a className={styles.link} href={doc.attachment.url}>
            {doc.attachment.filename}
          </a>
        </p>
      )}

      {doc.kind === "narrative" ? (
        <ol className={styles.items}>
          {doc.items.map((it, i) => (
            <Item
              key={keyOf(doc.id, [i])}
              item={it}
              docId={doc.id}
              path={[i]}
              answers={answers}
              onChange={onChange}
            />
          ))}
        </ol>
      ) : (
        <Fields doc={doc} answers={answers} onChange={onChange} />
      )}
    </details>
  );
}

/** 양식이 첨부에 없으면 **쓸 칸을 만들 수 없다.** 공고 셋 중 하나가 여기다.
 * "데이터 없음" 으로 끝내지 않는다(DESIGN.md §7-5). */
function Empty({ hint, url }: { hint: string[] | null; url: string | null }) {
  return (
    <div className={styles.empty}>
      <p className={styles.emptyTitle}>쓸 양식이 없어요</p>
      <p className={styles.emptyBody}>
        {hint && hint.length > 0
          ? "양식 파일이 첨부에 없어요. 공고문에는 이렇게 적혀 있어요."
          : "양식 파일이 첨부에 없어요. 공고 원문에서 확인해 주세요."}
      </p>
      {hint && hint.length > 0 && (
        <ul className={styles.quotes}>
          {hint.map((h) => (
            <li key={h} className={styles.quote}>
              {h}
            </li>
          ))}
        </ul>
      )}
      {url && (
        <a className={styles.cta} href={url}>
          공고 원문 보기
        </a>
      )}
    </div>
  );
}

export function FormFill({ data }: { data: NoticeDocuments }) {
  const [answers, setAnswers] = useState<Answers>({});
  const { documents } = data;

  const allKeys = useMemo(
    () => documents.flatMap((d) => leafKeys(d.items, d.id)),
    [documents],
  );
  const done = written(allKeys, answers);

  function onChange(key: string, value: string) {
    setAnswers((a) => ({ ...a, [key]: value }));
  }

  if (documents.length === 0) {
    return (
      <section className={styles.section} aria-labelledby="fill-title">
        <h2 id="fill-title" className={styles.title}>
          신청서 쓰기
        </h2>
        <Empty hint={data.submitHint} url={data.notice.url} />
      </section>
    );
  }

  return (
    <section className={styles.section} aria-labelledby="fill-title">
      <div className={styles.head}>
        <h2 id="fill-title" className={styles.title}>
          신청서 쓰기
        </h2>
        <Progress done={done} total={allKeys.length} />
      </div>

      {/* **아직 없는 것을 있는 척하지 않는다.** 초안이 없어서 칸이 빈 것이지,
          위키가 비어서 못 쓴 것이 아니다. 둘을 섞으면 F6-6 이 뜻을 잃는다. */}
      <p className={styles.notice}>
        초안은 아직 없어요. 지금은 직접 쓰는 칸만 있고, 쓴 내용은 새로고침하면 사라져요.
      </p>

      <div className={styles.docs}>
        {documents.map((d, i) => (
          <Doc key={d.id} doc={d} open={i === 0} answers={answers} onChange={onChange} />
        ))}
      </div>

      {(data.undecided ?? 0) > 0 && (
        <p className={styles.undecided}>
          아직 못 읽은 붙임이 <span data-numeric>{data.undecided}</span>개 있어요. 거기 있는
          항목은 여기 안 떠요.
        </p>
      )}
    </section>
  );
}
