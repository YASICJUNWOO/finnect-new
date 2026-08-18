import { ApiError } from "@/lib/api";
import { getProgress } from "@/lib/wiki";

/** 구축 진행을 화면이 물어보는 자리(S1 · SPEC F1-1-9).
 *
 * 서버 컴포넌트가 아니라 라우트 핸들러인 이유는 **화면이 반복해서 묻기 때문이다.**
 * 페이지를 다시 받으면 궤도와 위키까지 통째로 따라오는데 여기 필요한 것은 줄 몇 개다.
 *
 * 얼마나 자주 물을지는 화면이 정한다 — 응답의 `running` 이 false 면 그만 묻는다. */
export const dynamic = "force-dynamic";

export async function GET(_req: Request, ctx: { params: Promise<{ company: string }> }) {
  const { company } = await ctx.params;
  try {
    return Response.json(await getProgress(company));
  } catch (e) {
    console.error("진행 조회 실패", e);
    const status = e instanceof ApiError ? (e.status ?? 502) : 500;
    const detail = e instanceof Error ? e.message : "진행을 못 불러왔어요";
    return Response.json({ detail }, { status });
  }
}
