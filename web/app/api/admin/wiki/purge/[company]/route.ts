import { ApiError } from "@/lib/api";
import { purgeWiki } from "@/lib/admin";

/** 위키 지우기 버튼을 FastAPI 로 넘긴다. `admin/attach/run/route.ts` 와 같은 자리이고
 *  같은 토큰을 쓴다 — 사람이 화면에 입력한 값이라 여기가 그걸 알 이유가 없다.
 *
 *  **409 를 뭉개지 않는다.** "지금 세우고 있어요" 와 "토큰이 틀렸어요" 는 고칠 것이
 *  달라서, 하나로 묶으면 무엇을 해야 할지 모른다. */
export async function POST(req: Request, ctx: { params: Promise<{ company: string }> }) {
  const { company } = await ctx.params;
  const body = (await req.json().catch(() => ({}))) as { token?: string };
  if (!body.token) {
    return Response.json({ detail: "실행 토큰을 입력하세요" }, { status: 400 });
  }
  try {
    return Response.json(await purgeWiki(company, body.token));
  } catch (e) {
    console.error("위키 지우기 실패", e);
    return Response.json({ detail: why(e, "지우다가 잘못됐어요") }, { status: code(e) });
  }
}

function code(e: unknown): number {
  return e instanceof ApiError ? (e.status ?? 502) : 500;
}

function why(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}
