import { ApiError } from "@/lib/api";
import { triggerIngest } from "@/lib/admin";

/** 실행 버튼을 FastAPI 로 넘긴다(ADR-0065). `wiki/[company]/files/route.ts` 와 같은
 *  자리다 — 브라우저는 API 주소를 모르고, `x-ingest-trigger-token` 은 사람이 화면에
 *  입력한 값이라 여기가 그걸 대신 알 이유가 없다. 받은 그대로 전달만 한다. */
export async function POST(req: Request, ctx: { params: Promise<{ source: string }> }) {
  const { source } = await ctx.params;
  const body = (await req.json().catch(() => ({}))) as {
    token?: string;
    full?: boolean;
    limit?: number;
  };
  if (!body.token) {
    return Response.json({ detail: "실행 토큰을 입력하세요" }, { status: 400 });
  }
  try {
    return Response.json(
      await triggerIngest(source, { full: body.full, limit: body.limit, token: body.token }),
    );
  } catch (e) {
    // **원인을 그대로 옮긴다.** API 가 503 이면 "이 배포는 실행 토큰이 안 켜져 있어요"이고
    // 401 이면 "토큰이 틀렸어요"다 — 둘을 뭉개면 사용자가 무엇을 고쳐야 할지 모른다.
    console.error("수집 실행 실패", e);
    return Response.json({ detail: why(e, "실행하다가 잘못됐어요") }, { status: code(e) });
  }
}

function code(e: unknown): number {
  return e instanceof ApiError ? (e.status ?? 502) : 500;
}

function why(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}
