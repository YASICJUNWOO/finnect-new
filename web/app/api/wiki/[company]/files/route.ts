import { ApiError } from "@/lib/api";
import { uploadFiles } from "@/lib/wiki";

/** 올리기를 FastAPI 로 넘긴다(S1 · plan/15 T-0061).
 *
 * **브라우저가 API 주소를 모른다**(`next.config.ts`). 그래서 화면은 같은 앱의 이 경로를
 * 치고 여기가 `lib/wiki.ts` 를 통해 밖으로 나간다 — 경계는 여전히 `lib/` 하나다.
 *
 * **서버 액션이 아니라 라우트 핸들러다.** 서버 액션은 본문이 기본 1MB 로 잘리는데
 * 사업계획서와 피치덱이 그걸 우습게 넘는다. 여기는 그 상한이 없다.
 *
 * 파일 본문을 여기서 열어 보지 않는다. `FormData` 를 받은 그대로 넘긴다 —
 * 한 번 더 복사하면 큰 파일에서 메모리가 두 배가 된다. */
export async function POST(req: Request, ctx: { params: Promise<{ company: string }> }) {
  const { company } = await ctx.params;
  try {
    return Response.json(await uploadFiles(company, await req.formData()));
  } catch (e) {
    // **원인을 그대로 옮긴다.** API 가 503 이면 "이 서버는 파일을 못 받아요"이고
    // 그 문장이 사용자에게 무엇을 해야 하는지 말한다(ADR-0034).
    console.error("올리기 실패", e);
    return Response.json({ detail: why(e, "올리다가 잘못됐어요") }, { status: code(e) });
  }
}

function code(e: unknown): number {
  return e instanceof ApiError ? (e.status ?? 502) : 500;
}

function why(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}
