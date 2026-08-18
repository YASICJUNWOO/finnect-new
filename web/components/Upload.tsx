"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FileProgress, Progress, Upload as UploadResult } from "@/lib/wiki";
import styles from "./Upload.module.css";

/** S1 파일 올리기와 구축 진행(SPEC F1-1-1 · F1-1-9 · plan/15 T-0061).
 *
 * **이 화면의 일 하나는 "던져 놓고 무엇이 채워졌는지 보는 것"이다.** 분류도 이름 바꾸기도
 * 미리보기도 없다(DESIGN.md §8.1-5).
 *
 * ## 줄의 주인공은 진행이 아니라 채운 자리다
 *
 * 진행 칸 다섯은 배관이고, 사용자가 얻는 것은 **파일 하나가 위키의 어느 자리를 채웠나**다.
 * `사업자등록증_스캔.pdf → 우리가 하는 일 · 사업자 정보 · 소재지 · 업종 · 대표자` 다섯 개가
 * 그 파일의 값이고, 저 다섯이 마침 자격 판별의 입력이다(ADR-0032). 그래서 개수가 아니라
 * **이름을 적는다** — "채운 자리 5개"는 아무것도 말하지 않는다.
 *
 * ## 진행을 파일별로 말한다
 *
 * 전체 진행률 하나가 아니다. `SPEC.md` F1-1-8 이 파일별 독립을 요구하고, 실제로 다섯 중
 * 하나가 실패해도 넷으로 위키가 선다. 막대 하나로 뭉치면 그 사실이 사라진다.
 *
 * ## 백분율을 쓰지 않는다
 *
 * 칸 다섯을 점으로 그린다. `DESIGN.md` §6 이 막은 것은 눈금 없는 숫자이고 여기는 눈금이
 * 다섯으로 정해져 있다. 그래도 %로 바꾸지 않는다 — 단계마다 걸리는 시간이 달라서 60%가
 * 시간의 60%를 뜻하지 않는다.
 *
 * ## 계속 물어보는 것을 서버가 멈춘다
 *
 * `running` 이 false 가 되면 그만 묻는다. 파일 상태만 보고 판단하면 `chunked` 에서 영원히
 * 돈다 — 그게 "다음 차례"인지 "추출기가 몰라서 되돌아온 것"인지 행만 봐서는 모른다
 * (`wiki/progress.py`). */
export function Upload({ company, initial }: { company: string; initial: Progress }) {
  const [progress, setProgress] = useState(initial);
  const [sending, setSending] = useState(false);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rejected, setRejected] = useState<[string, string][]>([]);
  const [note, setNote] = useState<string | null>(null);
  const router = useRouter();

  const url = `/api/wiki/${encodeURIComponent(company)}`;

  /** 도는 동안만 묻는다. **멈춘 응답을 받고 나서 멈춘다** — `running: true` 를 본 자리에서
   *  끊으면 화면이 영영 도는 중으로 남는다. */
  useEffect(() => {
    if (!progress.running) return;
    let alive = true;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${url}/progress`, { cache: "no-store" });
        if (!res.ok || !alive) return;
        const next = (await res.json()) as Progress;
        if (!alive) return;
        setProgress(next);
        // 끝났으면 위키(S7)가 낡았다. 서버 컴포넌트를 다시 받아 둔다.
        if (!next.running) router.refresh();
      } catch {
        // 한 번 못 물어본 것으로 화면을 죽이지 않는다. 다음 차례에 다시 묻는다.
      }
    }, 1200);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [progress.running, url, router]);

  const send = useCallback(
    async (picked: File[]) => {
      if (!picked.length || sending) return;
      setSending(true);
      setError(null);
      setRejected([]);
      setNote(null);

      const body = new FormData();
      for (const f of picked) body.append("files", f);

      try {
        const res = await fetch(`${url}/files`, { method: "POST", body });
        const data = (await res.json()) as UploadResult & { detail?: string };
        if (!res.ok) {
          setError(data.detail ?? `올리다가 잘못됐어요 (${res.status})`);
          return;
        }
        setProgress(data.progress);
        setRejected(data.rejected);
        setNote(said(data));
      } catch {
        setError("올리다가 끊겼어요. 다시 해 보세요.");
      } finally {
        setSending(false);
      }
    },
    [sending, url],
  );

  const empty = progress.total === 0;

  return (
    <>
      <Drop over={over} setOver={setOver} sending={sending} onFiles={send} />

      {/* 4. 오류(§8.3-4). **사과하지 않고 무엇이 잘못됐는지 적는다.** API 가 준 문장을
        * 그대로 옮긴다 — 503 이면 로컬에서 하라는 말이 거기 있다(ADR-0034) */}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      {note && !error && (
        <p className={styles.note} role="status">
          {note}
        </p>
      )}
      {rejected.length > 0 && (
        /* 저장조차 못 한 것. **조용히 버리지 않는다** */
        <ul className={styles.rejected}>
          {rejected.map(([name, cause]) => (
            <li key={name}>
              <b>{name}</b> — {cause}
            </li>
          ))}
        </ul>
      )}

      {empty ? <Coming progress={progress} /> : <Board progress={progress} company={company} />}
    </>
  );
}

/** 던지는 자리. **끌어다 놓기와 골라 넣기 둘 다 된다** — 하나만 두면 키보드만 쓰는
 *  사람이나 드래그가 어려운 사람이 이 화면을 못 쓴다. */
function Drop({
  over,
  setOver,
  sending,
  onFiles,
}: {
  over: boolean;
  setOver: (v: boolean) => void;
  sending: boolean;
  onFiles: (files: File[]) => void;
}) {
  const input = useRef<HTMLInputElement>(null);

  return (
    <div
      className={styles.drop}
      data-over={over || undefined}
      data-sending={sending || undefined}
      onDragOver={(e) => {
        e.preventDefault();
        if (!sending) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (!sending) onFiles(Array.from(e.dataTransfer.files));
      }}
    >
      <p className={styles.dropLead}>{sending ? "올리는 중이에요" : "여기로 끌어다 놓으세요"}</p>

      <label className={styles.pick}>
        파일 고르기
        <input
          ref={input}
          type="file"
          multiple
          className="srOnly"
          disabled={sending}
          onChange={(e) => {
            onFiles(Array.from(e.target.files ?? []));
            // 같은 파일을 다시 고를 수 있어야 한다. 안 비우면 change 가 안 난다.
            if (input.current) input.current.value = "";
          }}
        />
      </label>

      {/* **무엇을 던지면 되는지 예를 든다.** 확장자 목록을 늘어놓으면 사용자가 자기 파일이
        * 그중 무엇인지 맞춰 봐야 한다. 크기 상한은 걸렸을 때만 말한다 */}
      <p className={styles.dropSub}>사업계획서 · 재무제표 · 사업자등록증 · 회사소개서 · 피치덱</p>
    </div>
  );
}

/** 5. 빈 화면(§7 · §8.3-5). **"데이터 없음"으로 끝내지 않고 무엇이 일어날지 보여 준다.**
 *
 * 번호를 붙인 것은 이것이 **실제로 순서이기 때문이다.** 글자를 읽어야 조각이 나오고
 * 조각이 있어야 사실이 나온다 — 장식이 아니라 의존이다. 파일이 하나라도 생기면 이 자리는
 * 사라진다. 상시로 붙어 있으면 안내가 아니라 껍데기가 된다. */
function Coming({ progress: p }: { progress: Progress }) {
  return (
    <section className={styles.coming} aria-label="이렇게 진행돼요">
      <h2 className={styles.comingTitle}>던지면 이렇게 돼요</h2>
      <ol className={styles.steps}>
        {p.steps.map((s, i) => (
          <li key={s.key} className={styles.step}>
            <span className={styles.stepN} data-numeric aria-hidden>
              {i + 1}
            </span>
            {s.label}
          </li>
        ))}
      </ol>
      <p className={styles.comingEnd} data-numeric>
        그러면 내 사업 위키의 자리 {p.slots}개가 채워져요.
      </p>
    </section>
  );
}

function Board({ progress: p, company }: { progress: Progress; company: string }) {
  const to = company ? `/wiki?company=${encodeURIComponent(company)}` : "/wiki";
  return (
    <section className={styles.board} aria-label="올린 파일">
      <header className={styles.boardHead}>
        <h2 className={styles.boardTitle}>
          올린 파일
          <span className={styles.count} data-numeric>
            {p.total}
          </span>
        </h2>
        <p className={styles.counts}>
          <span data-numeric>
            <b>{p.done}개</b> 읽었어요
          </span>
          {p.moving > 0 && <span data-numeric>{p.moving}개는 하는 중</span>}
          {p.needs_review > 0 && (
            <span className={styles.review} data-numeric>
              {p.needs_review}개는 글자가 안 나왔어요
            </span>
          )}
          {p.stuck > 0 && (
            <span className={styles.stuck} data-numeric>
              {p.stuck}개는 멈췄어요
            </span>
          )}
        </p>
      </header>

      <ul className={styles.files}>
        {p.files.map((f) => (
          <Row key={f.filename} file={f} steps={p.steps.length} places={p.places} />
        ))}
      </ul>

      <div className={styles.footer}>
        {p.filled > 0 && (
          <p className={styles.filled}>
            <span data-numeric>
              자리 {p.slots}개 중 <b>{p.filled}개</b>가 찼어요
            </span>
            {p.conflicts > 0 && (
              <span className={styles.review} data-numeric>
                값이 갈린 곳 {p.conflicts}건
              </span>
            )}
            <Link href={to} className={styles.go}>
              내 사업에서 보기
            </Link>
          </p>
        )}

        {/* **무엇이 뽑았는지 밝힌다.** 스텁이 멈춰 세운 것을 사용자 파일 탓으로 두지 않는다 */}
        {(p.extractor?.startsWith("stub") || p.stuck > 0) && (
          <p className={styles.stub}>
            지금은 시험용 추출기가 사실을 뽑고 있어요. 준비된 예시 파일에서만 돌아서, 다른
            파일은 글자까지만 읽고 멈춰요.
          </p>
        )}
      </div>
    </section>
  );
}

/** 파일 한 줄. 덩어리 넷을 넘지 않는다(§8.1-7) — 이름, 진행 한 마디, 채운 자리, 못 한 이유. */
function Row({
  file: f,
  steps,
  places,
}: {
  file: FileProgress;
  steps: number;
  places: Record<string, string>;
}) {
  return (
    <li className={styles.file} data-tone={toneOf(f)}>
      <p className={styles.name}>
        <span className={styles.filename}>{f.filename}</span>
        <span className={styles.meta} data-numeric>
          {f.ext ?? "모르는 형식"} · {size(f.byte_size)}
          {f.chunk_count ? ` · 조각 ${f.chunk_count}개` : ""}
        </span>
      </p>

      <p className={styles.line}>
        <span className={styles.dots} role="img" aria-label={`${steps}칸 중 ${f.reached}칸`}>
          {Array.from({ length: steps }, (_, i) => (
            <i key={i} className={styles.dot} data-state={dotState(i, f)} />
          ))}
        </span>
        <span className={styles.say}>{f.label}</span>
      </p>

      {/* **이 화면의 요점.** 개수가 아니라 이름이다 — 이 파일이 무엇을 줬는지 말한다 */}
      {f.nodes.length > 0 && (
        <ul className={styles.places} aria-label="이 파일이 채운 자리">
          {f.nodes.map((key) => (
            <li key={key}>{places[key] ?? key}</li>
          ))}
        </ul>
      )}

      {/* 왜 못 했나. **파서가 남긴 말을 고쳐 쓰지 않는다** */}
      {f.detail && <p className={styles.why}>{f.detail}</p>}
    </li>
  );
}

/** 점 하나의 상태. `reached` 는 **끝낸 칸 수**라 그다음 칸이 지금 자리다. */
function dotState(index: number, f: FileProgress): string {
  if (index < f.reached) return "done";
  if (index > f.reached) return "todo";
  if (f.moving) return "now";
  return f.ok ? "done" : "stopped";
}

function toneOf(f: FileProgress): string {
  if (f.moving) return "moving";
  if (f.ok) return "ok";
  // 글자가 안 나온 것과 못 읽은 것은 사용자가 할 일이 다르다. 스캔본은 OCR 이 붙으면
  // 읽히고(확인 필요), 포맷이 없는 것은 안 읽힌다(손대야 한다).
  return f.status === "needs_review" ? "review" : "stuck";
}

function said(r: UploadResult): string {
  const parts: string[] = [];
  if (r.received) parts.push(`${r.received}개를 받았어요`);
  if (r.duplicate) parts.push(`${r.duplicate}개는 이미 올린 파일이에요`);
  return parts.join(" · ") || r.reason || "받은 파일이 없어요";
}

/** 크기. **소수점을 한 자리까지만 쓴다** — 그 아래는 읽는 사람에게 뜻이 없다. */
function size(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  const kb = bytes / 1024;
  return kb < 1024 ? `${Math.round(kb)}KB` : `${(kb / 1024).toFixed(1)}MB`;
}
