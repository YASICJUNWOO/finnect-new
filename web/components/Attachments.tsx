import { FormCard, FormNotes } from "./FormDocuments";
import type { Attachment } from "@/lib/api";
import type { FormDocument, NoticeDocuments } from "@/lib/documents";
import styles from "./Attachments.module.css";

const PARSE_LABEL: Record<string, string> = {
  ok: "읽었어요",
  empty: "글자가 없어요",
  unsupported: "아직 못 여는 형식이에요",
  failed: "여는 데 실패했어요",
  container: "압축 파일이라 목록만 봤어요",
};

const PARSE_TONE: Record<string, string> = {
  ok: "ok",
  empty: "warn",
  unsupported: "warn",
  failed: "warn",
  container: "warn",
};

/** 첨부 해독 상태를 화면 말로.
 *
 * **다섯을 한 덩어리로 뭉개지 않는다.** 셋을 가른 것이 T-0004 의 존재 이유다 —
 * '안 해봤다'와 '해봤는데 안 됐다'와 '해봤는데 0바이트다'는 다른 사실이다. */
function label(a: Attachment): { text: string; tone: string } {
  if (a.fetch_status && a.fetch_status !== "ok") {
    return { text: "못 받았어요", tone: "warn" };
  }
  if (!a.parse_status) return { text: "아직 안 열어 봤어요", tone: "idle" };
  return {
    text: PARSE_LABEL[a.parse_status] ?? a.parse_status,
    tone: PARSE_TONE[a.parse_status] ?? "warn",
  };
}

/** 목록 한 줄. **파일 하나다.** */
type FileRow = {
  key: string;
  filename: string;
  url: string | null;
  /** 해독 상태. **`null` 은 「모른다」다** — 첨부 목록 없이 부르는 표본 화면이 그렇다 */
  state: { text: string; tone: string } | null;
  isNotice: boolean;
  /** 이름의 확장자와 내용이 다를 때만. 3,354건 중 7건이다 */
  mismatch: { ext: string; detected: string } | null;
  /** 이 파일에서 뽑은 양식 구간. 한 파일에 여럿 든다(실측 최대 14) */
  docs: FormDocument[];
};

/** 구간을 파일에 맞춘다. **주소로 맞추고 없으면 이름으로 떨어진다** —
 * `FormDocument.attachment.url` 과 `Attachment.url` 이 같은 값이다. */
function keyOf(a: { filename: string; url: string | null }): string {
  return a.url ?? `name:${a.filename}`;
}

/** 첨부 목록이 있으면 그것이 목록이고, 없으면 구간이 든 파일만 선다.
 *
 * **첨부를 정본으로 두는 이유는 못 뜯은 파일도 줄을 가져야 해서다.** 구간에서
 * 목록을 만들면 해독 실패한 첨부가 화면에서 사라지고, 그러면 「못 읽었다」를
 * 말할 자리가 없어진다. */
function rowsOf(items: Attachment[], docs: NoticeDocuments | null): FileRow[] {
  const byFile = new Map<string, FormDocument[]>();
  for (const d of docs?.documents ?? []) {
    const k = keyOf(d.attachment);
    const group = byFile.get(k);
    if (group) group.push(d);
    else byFile.set(k, [d]);
  }

  if (items.length > 0) {
    return items.map((a) => ({
      key: String(a.position),
      filename: a.filename,
      url: a.url,
      state: label(a),
      isNotice: a.kind === "공고문",
      mismatch:
        a.detected_ext && a.ext && a.detected_ext !== a.ext
          ? { ext: a.ext, detected: a.detected_ext }
          : null,
      docs: byFile.get(keyOf(a)) ?? [],
    }));
  }

  return [...byFile.entries()].map(([k, group]) => ({
    key: k,
    filename: group[0].attachment.filename,
    url: group[0].attachment.url,
    state: null,
    isNotice: false,
    mismatch: null,
    docs: group,
  }));
}

/** 첨부파일 한 절. **2026-08-24 두 절을 합친 자리다.**
 *
 * 전에는 「내야 할 서류」(뜯은 양식 구간)와 「낼 서류」(첨부 파일 목록 + 해독
 * 상태)가 따로 섰다. 둘은 **같은 파일을 두 번 세는 목록**이었다 — 위 절이 든
 * 구간의 출처가 아래 절의 어느 줄인지 사용자가 눈으로 맞춰야 했고, 한 첨부에
 * 서식이 여럿 든 29% 에서는 그 대응이 1:1 도 아니었다.
 *
 * 지금은 **파일이 바깥이고 구간이 안이다.** 목록의 단위는 첨부 파일 하나이고,
 * 거기서 뽑은 양식 구간이 그 줄 안에 접혀 있다.
 *
 * **두 층은 그대로 갈려 있다**(`lib/documents.ts`) — 층 1 「무슨 서류를 내나」는
 * 공고문에서 나오고(`FormNotes`), 층 2 「그 서류에 뭘 쓰나」는 양식 파일이
 * 첨부에 실려 있어야 나온다. 합친 것은 화면의 절이지 그 구분이 아니다. */
export function Attachments({
  items = [],
  decoded,
  docs = null,
}: {
  items?: Attachment[];
  /** 몇 개를 읽었나. **첨부 목록이 있을 때만 뜻이 있다** */
  decoded?: number;
  /** `null` 은 「양식이 없다」가 아니라 「모른다」다(`lib/api.ts`) */
  docs?: NoticeDocuments | null;
}) {
  const rows = rowsOf(items, docs);
  /* 펴 두는 구간 하나. **파일마다 하나씩 펴지 않는다** — 항목 326개짜리가 둘
     붙는 순간 화면이 소음이 된다(DESIGN.md §8.1-7).

     **그리기 도중에 세지 않고 미리 고른다.** 렌더 중에 바꾸는 값으로 열림을
     정하면 같은 목록이 회차마다 다르게 펴질 수 있다(`react-hooks/immutability`). */
  const openId = rows.find((r) => r.docs.length > 0)?.docs[0]?.id ?? null;

  return (
    <section className={styles.section} aria-labelledby="files-title">
      <div className={styles.head}>
        <h2 id="files-title" className={styles.title}>
          첨부파일
        </h2>
        {/* 못 읽은 것을 안 읽은 척하지 않는다. **모르면 안 적는다** */}
        {items.length > 0 && decoded !== undefined && (
          <p className={styles.summary} data-numeric>
            {items.length}개 중 {decoded}개를 읽었어요
          </p>
        )}
      </div>

      {/* **줄이 없을 때 말이 둘이 되지 않게 한다.** 아래 `FormNotes` 가 「양식이
          첨부에 없어요」 + 공고문 인용으로 같은 사실을 더 잘 말하므로, `docs` 를
          아는 경우에는 이 한 줄을 안 낸다(§10 — 빼도 뜻이 같은 말은 지운다).
          `docs` 가 `null` 이면 저쪽이 아무 말도 안 하니 여기가 말해야 한다. */}
      {rows.length === 0 ? (
        !docs && <p className={styles.none}>이 공고에는 붙은 서류가 없어요.</p>
      ) : (
        <ul className={styles.list}>
          {rows.map((r) => (
            <li key={r.key} className={styles.item}>
              <div className={styles.row}>
                <div className={styles.name}>
                  {r.url ? (
                    <a href={r.url} className={styles.link}>
                      {r.filename}
                    </a>
                  ) : (
                    r.filename
                  )}
                  {r.isNotice && <span className={styles.kind}>공고문</span>}
                </div>
                {r.state && (
                  <div className={styles.state}>
                    <span className={`${styles.badge} ${styles[r.state.tone]}`}>
                      {r.state.text}
                    </span>
                    {r.mismatch && (
                      <span className={styles.mismatch}>
                        이름은 .{r.mismatch.ext}인데 내용은 {r.mismatch.detected}예요
                      </span>
                    )}
                  </div>
                )}
              </div>

              {r.docs.length > 0 && (
                <div className={styles.forms}>
                  {r.docs.map((d) => (
                    <FormCard key={d.id} doc={d} open={d.id === openId} />
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {docs && <FormNotes data={docs} />}
    </section>
  );
}
