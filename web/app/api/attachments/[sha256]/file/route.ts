import { BASE, authHeaders } from "@/lib/api";

/** 첨부 원본 바이트를 브라우저에 넘기는 프록시 (미리보기 · rhwp).
 *
 * **직접 부르게 하지 않는 이유가 토큰이다.** `BASE`·`FINNECT_API_TOKEN` 은
 * 서버 전용 env 라 브라우저에 없다(`NEXT_PUBLIC_` 이 아니다). 노출하면 API 토큰이
 * 인터넷에 나가고, 그건 ADR-0035 가 문을 만든 이유를 되돌리는 것이다.
 *
 * **바이트를 그대로 흘린다.** `res.body` 를 넘기므로 8MB 짜리 hwp 도 메모리에
 * 통째로 안 올라온다.
 *
 * **상태 코드를 지어내지 않는다.** API 가 404(안 받아 둔 첨부)·415(못 여는 포맷)·
 * 503(이 서버에 원본이 없다)을 가려서 주는데 여기서 뭉개면 화면이 왜 안 되는지
 * 말할 수 없다. */
export const dynamic = "force-dynamic";

export async function GET(_req: Request, ctx: { params: Promise<{ sha256: string }> }) {
  const { sha256 } = await ctx.params;

  // API 가 다시 검사하지만 여기서도 막는다. **경로에 그대로 들어가는 값이다.**
  if (!/^[0-9a-f]{64}$/.test(sha256)) {
    return Response.json({ detail: "첨부 식별자가 sha256 이 아니에요" }, { status: 400 });
  }

  try {
    const res = await fetch(`${BASE}/api/attachments/${sha256}/file`, {
      headers: authHeaders(),
      cache: "no-store",
    });

    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      return Response.json(
        { detail: detail || "원본을 못 불러왔어요" },
        { status: res.status },
      );
    }

    return new Response(res.body, {
      status: 200,
      headers: {
        "content-type": res.headers.get("content-type") ?? "application/octet-stream",
        // 콘텐츠 주소라 내용이 절대 안 바뀐다. 같은 문서를 두 번 열 때 다시 안 받는다
        "cache-control": "private, max-age=3600, immutable",
      },
    });
  } catch (e) {
    console.error("첨부 원본 프록시 실패", e);
    return Response.json({ detail: "원본을 못 불러왔어요" }, { status: 502 });
  }
}
